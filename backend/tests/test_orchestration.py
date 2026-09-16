"""Motor de orquestación: paralelismo, cancelación, reanudación y plan asistido."""
from __future__ import annotations

import asyncio

import pytest

from orq.api.container import Container
from orq.application.ports import AgentRequest, AgentResult
from orq.application.use_cases import CreateRequirementCommand, NewAttachment, StartRunCommand
from orq.domain.enums import (
    AgentId,
    AgentRunStatus,
    AttachmentKind,
    PhiClassification,
    RunStatus,
    TraceEventType,
)
from orq.domain.errors import DomainError, NotFoundError
from orq.domain.run import Run, Usage
from orq.infrastructure.ai.gateway import AIGateway

from .conftest import START, make_container, run_async

ATTACHMENTS = (AttachmentKind.REPO, AttachmentKind.VTR_TEMPLATE, AttachmentKind.KIUWAN_CSV)


async def _create(container: Container, *, phi: PhiClassification = PhiClassification.NO) -> str:
    requirement = await container.create_requirement()(
        CreateRequirementCommand(
            title="Conciliación de pagos del portal",
            description="Ajustar la pantalla de pagos y la consulta de la tabla.",
            owner="ana",
            acceptance_criteria=("El pago se concilia el mismo día",),
            phi=phi,
            attachments=tuple(NewAttachment(kind=k, name=f"adjunto-{k.value}") for k in ATTACHMENTS),
        )
    )
    return requirement.id


class _TracingGateway:
    """Mide cuántos agentes corren a la vez y en qué orden."""

    def __init__(self, delay: float = 0.02) -> None:
        self._real = AIGateway()
        self._delay = delay
        self.active = 0
        self.max_active = 0
        self.timeline: list[tuple[str, AgentId]] = []

    async def run_agent(self, request: AgentRequest) -> AgentResult:
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        self.timeline.append(("inicio", request.agent_id))
        try:
            await asyncio.sleep(self._delay)
            return await self._real.run_agent(request)
        finally:
            self.active -= 1
            self.timeline.append(("fin", request.agent_id))


def test_middle_stage_runs_in_parallel_and_vtr_waits(settings) -> None:
    gateway = _TracingGateway()
    container = make_container(settings, gateway=gateway)
    requirement_id = run_async(_create(container))

    run = run_async(
        container.start_run()(
            StartRunCommand(requirement_id=requirement_id, started_by="ana", wait=True)
        )
    )
    assert run.status is RunStatus.COMPLETADA

    middle = {AgentId.TESTS, AgentId.KIUWAN, AgentId.SQL, AgentId.UIUX, AgentId.PRIVACY}
    enabled_middle = middle & set(run.enabled_agents)
    assert gateway.max_active == len(enabled_middle)  # la etapa intermedia va entera en paralelo

    def moment(kind: str, agent: AgentId) -> int:
        return gateway.timeline.index((kind, agent))

    # El VTR no arranca hasta que el último de la etapa intermedia termina.
    assert moment("inicio", AgentId.VTR) > max(moment("fin", a) for a in enabled_middle)
    # Y el dictamen es el último de todos.
    assert moment("inicio", AgentId.VERDICT) > moment("fin", AgentId.VTR)
    # El agente Código va antes que sus dependientes.
    assert moment("fin", AgentId.CODE) < min(moment("inicio", a) for a in enabled_middle)


class _SlowGateway:
    """Se queda colgado en un agente hasta que lo cancelan."""

    def __init__(self, stall_on: AgentId) -> None:
        self._real = AIGateway()
        self._stall_on = stall_on
        self.started = asyncio.Event()
        self.cancelled_calls = 0

    async def run_agent(self, request: AgentRequest) -> AgentResult:
        if request.agent_id is self._stall_on:
            self.started.set()
            try:
                await asyncio.sleep(30)
            except asyncio.CancelledError:
                self.cancelled_calls += 1
                raise
        return await self._real.run_agent(request)


def test_cancelling_stops_the_call_and_leaves_no_agent_working(settings) -> None:
    gateway = _SlowGateway(stall_on=AgentId.CODE)
    container = make_container(settings, gateway=gateway)

    async def scenario() -> Run:
        requirement_id = await _create(container)
        run = await container.start_run()(
            StartRunCommand(requirement_id=requirement_id, started_by="ana")
        )
        assert run.status is RunStatus.EN_CURSO  # devuelve de inmediato
        await asyncio.wait_for(gateway.started.wait(), timeout=5)
        return await container.cancel_run()(run.id, by="ana")

    run = run_async(scenario())

    assert run.status is RunStatus.CANCELADA
    assert run.cancelled_at is not None
    assert gateway.cancelled_calls == 1  # la llamada en curso se cortó de verdad
    # Ningún agente se queda colgado en «trabajando».
    assert not [e for e in run.executions.values() if e.status is AgentRunStatus.TRABAJANDO]
    assert run.execution(AgentId.CODE).status is AgentRunStatus.OMITIDO
    assert run.execution(AgentId.VERDICT).status is AgentRunStatus.OMITIDO

    events = [e.type for e in run_async(container.runs.events(run.id))]
    assert TraceEventType.RUN_CANCELLED in events
    assert TraceEventType.RUN_COMPLETED not in events


def test_cancelling_a_finished_run_is_an_error(container: Container) -> None:
    requirement_id = run_async(_create(container))
    run = run_async(
        container.start_run()(
            StartRunCommand(requirement_id=requirement_id, started_by="ana", wait=True)
        )
    )
    with pytest.raises(DomainError):
        run_async(container.cancel_run()(run.id, by="ana"))
    with pytest.raises(NotFoundError):
        run_async(container.cancel_run()("RUN-999", by="ana"))


class _CountingGateway:
    """Cuenta qué agentes se ejecutaron y con qué prompt."""

    def __init__(self) -> None:
        self._real = AIGateway()
        self.seen: list[AgentId] = []
        self.prompts: dict[AgentId, str] = {}

    async def run_agent(self, request: AgentRequest) -> AgentResult:
        self.seen.append(request.agent_id)
        self.prompts[request.agent_id] = request.system_prompt
        return await self._real.run_agent(request)


def _interrupted_run(container: Container, requirement_id: str) -> Run:
    """Deja una ejecución como la habría dejado una caída: a medias y sin terminar."""
    profiles = run_async(container.profiles.effective(requirement_id))
    enabled = (AgentId.ORCHESTRATOR, AgentId.CODE, AgentId.PRIVACY, AgentId.VERDICT)
    run = Run(
        id="RUN-CAIDA",
        requirement_id=requirement_id,
        started_by="ana",
        started_at=START,
        enabled_agents=enabled,
        profiles={a: profiles[a].snapshot() for a in enabled},
    )
    orchestrator = run.execution(AgentId.ORCHESTRATOR)
    orchestrator.status = AgentRunStatus.COMPLETADO
    orchestrator.output = {"items": []}
    code = run.execution(AgentId.CODE)
    code.status = AgentRunStatus.TRABAJANDO  # se quedó a mitad
    run_async(container.runs.add(run))
    return run


def test_resume_keeps_finished_work_and_only_redoes_what_was_pending(settings) -> None:
    gateway = _CountingGateway()
    container = make_container(settings, gateway=gateway)
    requirement_id = run_async(_create(container))
    run_async(container.suggest_plan()(requirement_id))
    run = _interrupted_run(container, requirement_id)

    resumed = run_async(container.resume_runs()(wait=True))

    assert [r.id for r in resumed] == [run.id]
    assert run.status is RunStatus.COMPLETADA
    # El Orquestador ya había terminado: no se repite.
    assert AgentId.ORCHESTRATOR not in gateway.seen
    assert run.execution(AgentId.ORCHESTRATOR).output == {"items": []}
    # Lo que quedó a medias y lo pendiente sí se ejecuta.
    assert set(gateway.seen) == {AgentId.CODE, AgentId.PRIVACY, AgentId.VERDICT}


def test_resume_uses_the_frozen_prompt_not_the_current_one(settings) -> None:
    gateway = _CountingGateway()
    container = make_container(settings, gateway=gateway)
    requirement_id = run_async(_create(container))
    run_async(container.suggest_plan()(requirement_id))
    run = _interrupted_run(container, requirement_id)

    # Entre la caída y la reanudación, alguien cambia el prompt por defecto.
    profiles = run_async(container.profiles.defaults())
    run_async(
        container.profiles.save_default(
            profiles[AgentId.CODE].with_prompt(
                system_prompt="PROMPT NUEVO",
                task_prompt="tarea nueva",
                author="ana",
                note="cambio posterior",
                at=START,
            )
        )
    )

    run_async(container.resume_runs()(wait=True))

    assert gateway.prompts[AgentId.CODE] != "PROMPT NUEVO"
    assert run.profile(AgentId.CODE).prompt_version == 1


def test_resume_gives_up_when_the_frozen_version_is_gone(settings) -> None:
    container = make_container(settings)
    requirement_id = run_async(_create(container))
    run_async(container.suggest_plan()(requirement_id))
    run = _interrupted_run(container, requirement_id)

    # Se pierde el historial del prompt congelado: reanudar falsearía el resultado.
    profiles = run_async(container.profiles.defaults())
    broken = profiles[AgentId.CODE]
    object.__setattr__(broken, "versions", ())
    run_async(container.profiles.save_default(broken))

    resumed = run_async(container.resume_runs()(wait=True))

    assert resumed == []
    assert run.status is RunStatus.FALLIDA
    assert "no se pudo reanudar" in run.error.lower()
    assert not [e for e in run.executions.values() if e.status is AgentRunStatus.TRABAJANDO]


class _FailingCodeGateway:
    def __init__(self) -> None:
        self._real = AIGateway()
        self.degraded: list[AgentId] = []

    async def run_agent(self, request: AgentRequest) -> AgentResult:
        if request.agent_id is AgentId.CODE:
            raise RuntimeError("el repositorio no responde")
        if request.context.get("degraded"):
            self.degraded.append(request.agent_id)
        return await self._real.run_agent(request)


def test_dependents_know_what_context_they_are_missing(settings) -> None:
    gateway = _FailingCodeGateway()
    container = make_container(settings, gateway=gateway)
    requirement_id = run_async(_create(container))

    run = run_async(
        container.start_run()(
            StartRunCommand(requirement_id=requirement_id, started_by="ana", wait=True)
        )
    )

    assert run.status is RunStatus.COMPLETADA
    assert run.execution(AgentId.CODE).status is AgentRunStatus.FALLIDO
    # Los dependientes siguen, pero saben que trabajan con menos contexto.
    assert AgentId.TESTS in gateway.degraded
    events = [
        e for e in run_async(container.runs.events(run.id))
        if e.type is TraceEventType.AGENT_DEGRADED
    ]
    assert events and any(e.agent is AgentId.TESTS for e in events)


class _PlanningGateway:
    """Orquestador que propone desactivar UI/UX y Privacidad."""

    def __init__(self) -> None:
        self.called = False

    async def run_agent(self, request: AgentRequest) -> AgentResult:
        self.called = True
        assert request.agent_id is AgentId.ORCHESTRATOR
        return AgentResult(
            agent_id=AgentId.ORCHESTRATOR,
            output={
                "items": [
                    {"agent": "uiux", "suggested": False, "reason": "El cambio no toca pantallas."},
                    {"agent": "privacy", "suggested": False, "reason": "No hace falta."},
                ]
            },
            usage=Usage(),
        )


def test_assisted_plan_refines_the_deterministic_one(settings) -> None:
    gateway = _PlanningGateway()
    container = make_container(settings, gateway=gateway)
    requirement_id = run_async(_create(container, phi=PhiClassification.SI))

    view = run_async(container.suggest_plan()(requirement_id, assisted=True))

    assert gateway.called
    uiux = view.plan.item(AgentId.UIUX)
    assert uiux is not None and uiux.enabled is False and uiux.source == "orquestador"
    # Privacidad es obligatorio con PHI: la sugerencia del modelo no lo desactiva.
    privacy = view.plan.item(AgentId.PRIVACY)
    assert privacy is not None and privacy.enabled is True and privacy.source == "regla"
    assert view.blocked is False


class _BrokenPlanningGateway:
    async def run_agent(self, request: AgentRequest) -> AgentResult:
        raise RuntimeError("el proveedor no responde")


def test_assisted_plan_falls_back_to_the_rules(settings) -> None:
    container = make_container(settings, gateway=_BrokenPlanningGateway())
    requirement_id = run_async(_create(container))

    view = run_async(container.suggest_plan()(requirement_id, assisted=True))

    assert all(item.source == "regla" for item in view.plan.items)
    assert view.plan.item(AgentId.CODE) is not None


class _UnevenGateway:
    """Cada agente tarda algo distinto, para que las corrutinas de una oleada se entrelacen."""

    def __init__(self) -> None:
        self._real = AIGateway()
        self._delays = {AgentId.TESTS: 0.03, AgentId.KIUWAN: 0.01, AgentId.SQL: 0.02}

    async def run_agent(self, request: AgentRequest) -> AgentResult:
        await asyncio.sleep(self._delays.get(request.agent_id, 0.005))
        return await self._real.run_agent(request)


def test_the_trace_reaches_the_bus_in_order(settings) -> None:
    """La traza se publica en el mismo orden en que se numera.

    El espectador descarta lo que llega con un número anterior al último recibido, así que un
    evento publicado fuera de orden se perdería y su agente se quedaría «en espera» en pantalla
    aunque hubiera terminado. Guardar el evento tarda (en PostgreSQL es una inserción), y ahí es
    donde los agentes de una misma oleada se entrelazaban.
    """
    container = make_container(settings, gateway=_UnevenGateway())
    requirement_id = run_async(_create(container))

    publicados: list[int] = []
    original_publish = container.events.publish
    original_append = container.runs.append_event

    async def publish(event):  # type: ignore[no-untyped-def]
        publicados.append(event.seq)
        await original_publish(event)

    async def append_event(event):  # type: ignore[no-untyped-def]
        await asyncio.sleep(0.002)  # guardar no es instantáneo: es donde se colaban los demás
        await original_append(event)

    container.events.publish = publish  # type: ignore[method-assign]
    container.runs.append_event = append_event  # type: ignore[method-assign]

    run = run_async(
        container.start_run()(
            StartRunCommand(requirement_id=requirement_id, started_by="ana", wait=True)
        )
    )

    assert run.status is RunStatus.COMPLETADA
    assert len(publicados) > 10
    assert publicados == sorted(publicados), f"traza publicada desordenada: {publicados}"
