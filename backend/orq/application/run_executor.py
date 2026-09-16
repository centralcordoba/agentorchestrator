"""Ejecución de una revisión: recorre el grafo de dependencias y deja la traza."""
from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import Any, Callable

from ..domain.agents import AGENTS
from ..domain.enums import AgentId, AgentRunStatus, RunStatus, TraceEventType, Verdict
from ..domain.orchestration import execution_waves, missing_dependencies
from ..domain.plan import Plan
from ..domain.policies import apply_phi_guardrail, check_agent_provider
from ..domain.privacy import redact
from ..domain.profiles import AgentProfile
from ..domain.requirement import Requirement
from ..domain.run import Run, TraceEvent, Usage
from .ports import (
    AgentGateway,
    AgentRequest,
    Clock,
    EventPublisher,
    RepoAnalysis,
    RepoAnalyzer,
    RunRepository,
)

log = logging.getLogger(__name__)

CANCELLED_REASON = "Ejecución cancelada."


class RunExecutor:
    def __init__(
        self,
        *,
        runs: RunRepository,
        events: EventPublisher,
        clock: Clock,
        gateway: AgentGateway,
        repos: RepoAnalyzer | None = None,
        scrub: Callable[[str], str] | None = None,
    ) -> None:
        self._runs = runs
        self._events = events
        self._clock = clock
        self._gateway = gateway
        self._repos = repos
        self._scrub = scrub or (lambda text: text)
        self._analyses: dict[str, RepoAnalysis] = {}
        self._emit_locks: dict[str, asyncio.Lock] = {}

    async def execute(
        self,
        *,
        requirement: Requirement,
        plan: Plan,
        run: Run,
        profiles: dict[AgentId, AgentProfile],
        cancellation: asyncio.Event | None = None,
    ) -> Run:
        try:
            return await self._execute(
                requirement=requirement,
                plan=plan,
                run=run,
                profiles=profiles,
                cancellation=cancellation,
            )
        finally:
            self._emit_locks.pop(run.id, None)
            self._analyses.pop(run.id, None)
            # La copia de trabajo con código del cliente se borra pase lo que pase: termine bien,
            # falle o la cancelen (ORQ-22).
            if self._repos is not None:
                with contextlib.suppress(Exception):
                    await self._repos.release(run.id)

    async def _execute(
        self,
        *,
        requirement: Requirement,
        plan: Plan,
        run: Run,
        profiles: dict[AgentId, AgentProfile],
        cancellation: asyncio.Event | None = None,
    ) -> Run:
        resuming = any(
            e.status is AgentRunStatus.COMPLETADO for e in run.executions.values()
        )
        await self._prepare_repo(requirement, run)
        await self._emit(
            run,
            TraceEventType.RUN_STARTED,
            title=("Revisión reanudada" if resuming else f"Revisión de {requirement.id}"),
            detail=f"{len(run.enabled_agents)} agente(s) activos",
        )

        for wave in execution_waves(run.enabled_agents):
            todo = [a for a in wave if run.execution(a).status is not AgentRunStatus.COMPLETADO]
            if not todo:
                continue
            if cancellation is not None and cancellation.is_set():
                return await self._finish_cancelled(run)

            finished = await self._run_wave(requirement, plan, run, profiles, todo, cancellation)
            await self._runs.save(run)
            if not finished:
                return await self._finish_cancelled(run)

        run.status = RunStatus.COMPLETADA
        run.finished_at = self._clock.now()
        usage = run.usage
        # Primero se guarda el estado y después se anuncia: quien reciba `run_completed` y vaya a
        # leer la ejecución tiene que encontrarla ya terminada. Al revés, el canal en vivo cerraba
        # diciendo «en_curso» sobre una revisión que acababa de terminar.
        await self._runs.save(run)
        await self._emit(
            run,
            TraceEventType.RUN_COMPLETED,
            title="Revisión completada",
            detail=f"{usage.tokens_in + usage.tokens_out} tokens · {usage.cost_usd:.4f} USD",
            usage=usage,
        )
        return run

    async def _prepare_repo(self, requirement: Requirement, run: Run) -> None:
        """Calcula el diff y las reglas deterministas una sola vez para toda la ejecución.

        Si el repositorio no responde, la ejecución sigue: los agentes trabajan con lo que haya y
        la traza dice qué faltó. Quedarse sin revisión por un fallo de red sería peor.
        """
        repo = requirement.repo
        if repo is None or self._repos is None:
            return
        try:
            analysis = await self._repos.analyze(
                run_id=run.id, repo=repo, criteria=requirement.acceptance_criteria
            )
        except Exception as error:  # el detalle ya viene limpio de credenciales
            log.warning("no se pudo analizar el repositorio de %s: %s", requirement.id, error)
            await self._emit(
                run,
                TraceEventType.AGENT_DEGRADED,
                agent=AgentId.CODE,
                title="Sin diff del repositorio",
                detail=str(error),
            )
            return

        self._analyses[run.id] = analysis
        await self._emit(
            run,
            TraceEventType.TOOL_CALLED,
            agent=AgentId.CODE,
            title="git_diff",
            detail=(
                f"{analysis.files} archivo(s) en el cambio · {len(analysis.findings)} hallazgo(s) "
                f"por reglas, sin modelo"
                + (" · diff recortado por tamaño" if analysis.truncated else "")
            ),
            data={"files": analysis.files, "head_sha": repo.head_sha, "truncated": analysis.truncated},
        )

    async def _ground_code_output(
        self, run: Run, output: dict[str, Any]
    ) -> dict[str, Any]:
        """Ancla la salida del agente Código en la evidencia del diff.

        Dos cosas, y las dos vienen de la regla del proyecto de no presentar datos inventados
        como reales:

        - El mapa del cambio **se sustituye** por el real. Es un hecho del repositorio, no una
          opinión del modelo, y todos los demás agentes lo consumen.
        - Un hallazgo del modelo que señala un archivo **que no está en el cambio se descarta**.
          Un modelo puede citar de memoria una ruta plausible que no existe; si eso llegara al
          dictamen, estaríamos rechazando un cambio por un archivo inventado. Se descarta y
          queda dicho en la traza, no en silencio.
        """
        analysis = self._analyses.get(run.id)
        if analysis is None or analysis.empty:
            return output

        del_cambio = {entry.file for entry in analysis.change_map}
        del_modelo = output.get("findings")
        del_modelo = list(del_modelo) if isinstance(del_modelo, list) else []
        verificados = [
            f
            for f in del_modelo
            if not isinstance(f, dict) or not f.get("file") or f.get("file") in del_cambio
        ]
        descartados = len(del_modelo) - len(verificados)
        if descartados:
            await self._emit(
                run,
                TraceEventType.GUARDRAIL_APPLIED,
                agent=AgentId.CODE,
                title=f"{descartados} hallazgo(s) descartado(s)",
                detail=(
                    "Señalaban archivos que no están en el cambio revisado, así que no se pueden "
                    "comprobar contra el commit."
                ),
                data={"discarded": descartados, "kept": len(verificados)},
            )

        grounded = dict(output)
        grounded["change_map"] = _change_map_rows(analysis)
        grounded["findings"] = verificados + [
            {
                "severity": f.severity.value,
                "title": f.title,
                "detail": f.detail,
                "file": f.file,
                "line": f.line,
                "suggestion": f.suggestion,
                "url": f.url,
            }
            for f in analysis.findings
        ]
        return grounded

    async def _run_wave(
        self,
        requirement: Requirement,
        plan: Plan,
        run: Run,
        profiles: dict[AgentId, AgentProfile],
        wave: list[AgentId],
        cancellation: asyncio.Event | None,
    ) -> bool:
        """Ejecuta una oleada en paralelo. Devuelve `False` si la cancelaron a mitad."""
        work = asyncio.gather(
            *(self._run_agent(requirement, plan, run, profiles[agent_id]) for agent_id in wave)
        )
        if cancellation is None:
            await work
            return True

        waiter = asyncio.ensure_future(cancellation.wait())
        done, _ = await asyncio.wait({work, waiter}, return_when=asyncio.FIRST_COMPLETED)

        if work in done:
            waiter.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await waiter
            await work
            return True

        work.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await work
        return False

    async def _finish_cancelled(self, run: Run) -> Run:
        """Cierra una ejecución cancelada sin dejar agentes colgados en «trabajando»."""
        now = self._clock.now()
        for execution in run.executions.values():
            if execution.status in (AgentRunStatus.TRABAJANDO, AgentRunStatus.PENDIENTE):
                execution.status = AgentRunStatus.OMITIDO
                execution.reason = CANCELLED_REASON
                execution.finished_at = now
        for agent_id in run.enabled_agents:
            execution = run.execution(agent_id)
            if execution.status is AgentRunStatus.PENDIENTE:
                execution.status = AgentRunStatus.OMITIDO
                execution.reason = CANCELLED_REASON

        run.status = RunStatus.CANCELADA
        run.cancelled_at = now
        run.finished_at = now
        await self._runs.save(run)
        await self._emit(run, TraceEventType.RUN_CANCELLED, title="Revisión cancelada")
        return run

    async def _run_agent(
        self, requirement: Requirement, plan: Plan, run: Run, profile: AgentProfile
    ) -> None:
        agent_id = profile.agent_id
        execution = run.execution(agent_id)
        definition = AGENTS[agent_id]

        blocked = check_agent_provider(agent_id, profile.provider, requirement.phi)
        if blocked:
            execution.status = AgentRunStatus.OMITIDO
            execution.reason = blocked
            await self._emit(
                run,
                TraceEventType.GUARDRAIL_APPLIED,
                agent=agent_id,
                title="Bloqueado por política de PHI",
                detail=blocked,
            )
            await self._emit(
                run, TraceEventType.AGENT_SKIPPED, agent=agent_id, title=definition.label, detail=blocked
            )
            return

        execution.status = AgentRunStatus.TRABAJANDO
        execution.started_at = self._clock.now()
        await self._emit(
            run, TraceEventType.AGENT_STARTED, agent=agent_id, title=definition.label, detail=definition.role
        )

        context, degraded = self._context(requirement, plan, run, agent_id)
        if degraded:
            await self._emit(
                run,
                TraceEventType.AGENT_DEGRADED,
                agent=agent_id,
                title="Trabaja con menos contexto",
                detail="Sin resultado de: " + ", ".join(AGENTS[d].label for d in degraded),
            )

        request = AgentRequest(
            run_id=run.id,
            agent_id=agent_id,
            profile=run.profile(agent_id),
            system_prompt=profile.system_prompt,
            task_prompt=profile.task_prompt,
            context=context,
            phi=requirement.phi,
        )

        try:
            result = await self._gateway.run_agent(request)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # el fallo de un agente no tumba la ejecución
            log.warning("agente %s falló en %s: %s", agent_id.value, run.id, exc)
            execution.status = AgentRunStatus.FALLIDO
            execution.error = str(exc)
            execution.finished_at = self._clock.now()
            await self._emit(
                run,
                TraceEventType.AGENT_FAILED,
                agent=agent_id,
                title=f"{definition.label}: sin resultado",
                detail=str(exc),
            )
            return

        await self._emit(
            run,
            TraceEventType.LLM_CALL,
            agent=agent_id,
            title=f"{request.profile.provider.value} · {request.profile.model}",
            detail=f"{result.steps} paso(s)",
            usage=result.usage,
        )
        for tool in result.tools_used:
            await self._emit(run, TraceEventType.TOOL_CALLED, agent=agent_id, title=tool)
        if result.redactions:
            total = sum(result.redactions.values())
            await self._emit(
                run,
                TraceEventType.PHI_REDACTED,
                agent=agent_id,
                title=f"{total} identificador(es) sustituido(s) antes de enviar",
                detail=", ".join(
                    f"{identifier.value}×{count}"
                    for identifier, count in sorted(
                        result.redactions.items(), key=lambda pair: pair[0].value
                    )
                ),
                data={
                    "counts": {k.value: v for k, v in result.redactions.items()},
                    "total": total,
                },
            )

        output = result.output
        if agent_id is AgentId.CODE:
            output = await self._ground_code_output(run, output)
        if agent_id is AgentId.VERDICT:
            output = await self._guard_verdict(run, requirement, output)

        execution.status = AgentRunStatus.COMPLETADO
        execution.output = output
        execution.usage = result.usage
        execution.calls = result.calls
        execution.finished_at = self._clock.now()
        await self._emit(
            run,
            TraceEventType.AGENT_COMPLETED,
            agent=agent_id,
            title=definition.label,
            detail=_summary_of(output),
            usage=result.usage,
        )

    async def _guard_verdict(
        self, run: Run, requirement: Requirement, output: dict[str, Any]
    ) -> dict[str, Any]:
        """El dictamen no puede aprobar sin informe de Privacidad si hay PHI."""
        try:
            verdict = Verdict(output["verdict"])
        except (KeyError, ValueError):
            return output

        privacy_done = run.execution(AgentId.PRIVACY).status is AgentRunStatus.COMPLETADO
        corrected, guardrail = apply_phi_guardrail(
            verdict, phi=requirement.phi, privacy_executed=privacy_done
        )
        if guardrail is None:
            return output

        await self._emit(
            run,
            TraceEventType.GUARDRAIL_APPLIED,
            agent=AgentId.VERDICT,
            title=f"Dictamen corregido a {corrected.value}",
            detail=guardrail,
        )
        guardrails = list(output.get("guardrails") or [])
        guardrails.append(guardrail)
        return {**output, "verdict": corrected.value, "guardrails": guardrails}

    def _context(
        self, requirement: Requirement, plan: Plan, run: Run, agent_id: AgentId
    ) -> tuple[dict[str, Any], tuple[AgentId, ...]]:
        """Contexto del agente y dependencias que no produjeron resultado.

        Solo datos que existen: nada inventado. Si falta una dependencia, el agente lo sabe.
        """
        completed = frozenset(
            a
            for a, execution in run.executions.items()
            if execution.status is AgentRunStatus.COMPLETADO
        )
        degraded = missing_dependencies(agent_id, completed)

        context: dict[str, Any] = {
            "requirement_id": requirement.id,
            "title": requirement.title,
            "description": requirement.description,
            "acceptance_criteria": list(requirement.acceptance_criteria),
            "phi": requirement.phi.value,
            "attachments": [
                {"kind": a.kind.value, "name": a.name, "detail": a.detail} for a in requirement.attachments
            ],
        }
        repo = requirement.repo
        if repo is not None:
            context["repo"] = {
                "full_name": repo.full_name,
                "branch": repo.branch,
                "base": repo.base,
                "head_sha": repo.head_sha,
                "files": [{"path": f.path, "status": f.status.value} for f in repo.files],
            }
        # El agente Código recibe lo que ya encontraron las reglas para que no lo repita.
        analysis = self._analyses.get(run.id)
        if agent_id is AgentId.CODE and analysis is not None and not analysis.empty:
            context["change_map"] = _change_map_rows(analysis)
            context["rule_findings"] = [
                {
                    "severity": f.severity.value,
                    "title": f.title,
                    "file": f.file,
                    "line": f.line,
                }
                for f in analysis.findings
            ]
            context["rule_findings_note"] = (
                "Hallazgos ya encontrados por reglas deterministas sobre el diff. No los repitas: "
                "confirma, descarta o añade lo que las reglas no ven."
            )
        if agent_id is AgentId.ORCHESTRATOR:
            context["plan"] = [
                {"agent": i.agent_id.value, "suggested": i.suggested, "reason": i.reason} for i in plan.items
            ]
        if AgentId.CODE in AGENTS[agent_id].depends_on:
            code_output = run.execution(AgentId.CODE).output
            context["change_map"] = (code_output or {}).get("change_map", [])
        if agent_id in (AgentId.VTR, AgentId.VERDICT):
            context["agent_outputs"] = {
                other.value: execution.output
                for other, execution in run.executions.items()
                if execution.output is not None and other is not agent_id
            }
            context["missing_agents"] = {
                other.value: execution.reason or execution.error or "Sin resultado."
                for other, execution in run.executions.items()
                if execution.status in (AgentRunStatus.FALLIDO, AgentRunStatus.OMITIDO)
            }
        if degraded:
            context["degraded"] = [d.value for d in degraded]
        return context, degraded

    async def _emit(
        self,
        run: Run,
        type: TraceEventType,
        *,
        agent: AgentId | None = None,
        title: str = "",
        detail: str = "",
        usage: Usage | None = None,
        data: dict[str, Any] | None = None,
    ) -> None:
        # Numerar, guardar y publicar van juntos. Los agentes de una oleada emiten a la vez, y sin
        # el candado uno podía reservar el número 11 y publicarlo después del 12 de otro: el
        # espectador, que descarta lo que llega con número anterior al último recibido, perdía ese
        # evento y el agente se quedaba «en espera» en pantalla aunque hubiera terminado.
        lock = self._emit_locks.setdefault(run.id, asyncio.Lock())
        async with lock:
            event = TraceEvent(
                seq=await self._runs.next_seq(run.id),
                run_id=run.id,
                at=self._clock.now(),
                type=type,
                agent=agent,
                title=self._scrub(title),
                detail=self._scrub(detail),
                data=data or {},
                usage=usage,
            )
            await self._runs.append_event(event)
            await self._events.publish(event)


def _change_map_rows(analysis: RepoAnalysis) -> list[dict[str, Any]]:
    """Mapa del cambio en la forma que declara el esquema del agente Código."""
    return [
        {
            "file": entry.file,
            "change": entry.change,
            "added": entry.added,
            "removed": entry.removed,
            "symbols": list(entry.symbols),
            "criteria": list(entry.criteria),
        }
        for entry in analysis.change_map
    ]


def _summary_of(output: dict[str, Any]) -> str:
    """Resumen corto para la traza, sin volcar la salida completa.

    Pasa por el redactor aunque el modelo solo haya visto contenido ya redactado: la traza se
    guarda, se reproduce y se enseña en pantalla, y es justo donde no puede aparecer un valor.
    """
    for key in ("summary", "rationale", "answer", "minimum_necessary"):
        value = output.get(key)
        if isinstance(value, str) and value:
            return redact(value[:200]).text
    for key in ("findings", "defects", "tests", "scenarios", "sections", "items", "detections"):
        value = output.get(key)
        if isinstance(value, list):
            return f"{len(value)} {key}"
    return ""


__all__ = ["RunExecutor", "CANCELLED_REASON"]
