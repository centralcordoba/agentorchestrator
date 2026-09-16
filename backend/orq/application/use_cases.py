"""Casos de uso. Cada uno recibe sus puertos por constructor y no sabe de FastAPI."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime

from ..domain.agents import AGENTS, ALL_AGENTS
from ..domain.audit import AuditAction
from ..domain.deliverables import Deliverables
from ..domain.enums import AgentId, AgentRunStatus, AttachmentKind, PhiClassification, RunStatus
from ..domain.errors import DomainError, NotFoundError, PlanBlockedError
from ..domain.plan import Plan, PlanWarning
from ..domain.planning import locked_reason, merge_suggestions, plan_warnings, suggest_plan
from ..domain.privacy import scan_typed_text
from ..domain.profiles import AgentProfile
from ..domain.requirement import Attachment, Requirement
from ..domain.run import Run, TraceEvent
from ..domain.secrets import ORGANIZATION, NewSecret, SecretKind, SecretMetadata
from .deliverables import build_deliverables
from .ports import (
    AgentGateway,
    AgentRequest,
    AuditLog,
    Clock,
    IdGenerator,
    PlanRepository,
    ProfileRepository,
    RepoConnector,
    RequirementRepository,
    RunRepository,
    SecretVault,
)
from .run_supervisor import RunSupervisor

log = logging.getLogger(__name__)


async def _record(audit: "AuditLog | None", **entry) -> None:
    """Anota la acción si hay registro de auditoría configurado.

    Un fallo al auditar no puede tumbar la operación del usuario, pero sí tiene que verse
    en el log.
    """
    if audit is None:
        return
    try:
        await audit.append(**entry)
    except Exception:  # pragma: no cover - depende de la base
        log.exception("no se pudo registrar en auditoría: %s", entry.get("action"))


@dataclass(frozen=True, slots=True)
class NewAttachment:
    kind: AttachmentKind
    name: str
    detail: str = ""


@dataclass(frozen=True, slots=True)
class CreateRequirementCommand:
    title: str
    description: str
    owner: str
    acceptance_criteria: tuple[str, ...] = ()
    phi: PhiClassification = PhiClassification.DESCONOCIDO
    attachments: tuple[NewAttachment, ...] = ()


@dataclass(frozen=True, slots=True)
class AddAttachmentCommand:
    requirement_id: str
    kind: AttachmentKind
    name: str
    detail: str = ""
    added_by: str = ""


@dataclass(frozen=True, slots=True)
class ConnectRepoCommand:
    """Conectar el repositorio del cambio. La credencial la pone el servidor, nunca el cliente."""

    requirement_id: str
    url: str
    branch: str = ""
    base: str = ""
    last_commits: int = 0
    by: str = ""


@dataclass(frozen=True, slots=True)
class SaveSecretCommand:
    """Guardar o rotar un secreto. Entra el valor; no vuelve a salir nunca."""

    kind: SecretKind
    name: str
    value: str
    scope: str = ORGANIZATION
    username: str = ""
    expires_at: datetime | None = None
    by: str = ""


@dataclass(frozen=True, slots=True)
class ClassifyPhiCommand:
    requirement_id: str
    phi: PhiClassification
    by: str


@dataclass(frozen=True, slots=True)
class UpdatePlanCommand:
    requirement_id: str
    enabled_agents: tuple[AgentId, ...]
    by: str


@dataclass(frozen=True, slots=True)
class StartRunCommand:
    requirement_id: str
    started_by: str
    enabled_agents: tuple[AgentId, ...] | None = None
    wait: bool = False


@dataclass(frozen=True, slots=True)
class PlanView:
    plan: Plan
    warnings: tuple[PlanWarning, ...] = ()

    @property
    def blocked(self) -> bool:
        return any(w.blocks for w in self.warnings)


@dataclass(frozen=True, slots=True)
class RunView:
    run: Run
    deliverables: Deliverables
    events: tuple[TraceEvent, ...] = field(default=())


class CreateRequirement:
    def __init__(
        self,
        *,
        requirements: RequirementRepository,
        clock: Clock,
        ids: IdGenerator,
        audit: AuditLog | None = None,
    ) -> None:
        self._requirements = requirements
        self._clock = clock
        self._ids = ids
        self._audit = audit

    async def __call__(self, command: CreateRequirementCommand) -> Requirement:
        now = self._clock.now()
        attachments: list[Attachment] = []
        for new in command.attachments:
            attachments.append(
                Attachment(
                    id=await self._ids.new_id("ATT"),
                    kind=new.kind,
                    name=new.name,
                    detail=new.detail,
                    added_by=command.owner,
                    added_at=now,
                )
            )
        requirement = Requirement(
            id=await self._ids.new_id("REQ"),
            title=command.title.strip(),
            description=command.description.strip(),
            owner=command.owner.strip(),
            created_at=now,
            acceptance_criteria=tuple(c.strip() for c in command.acceptance_criteria if c.strip()),
            phi=command.phi,
            phi_set_by=command.owner if command.phi is not PhiClassification.DESCONOCIDO else "",
            attachments=tuple(attachments),
        )
        await self._requirements.add(requirement)
        await _record(
            self._audit,
            at=now,
            actor=requirement.owner,
            action=AuditAction.REQUERIMIENTO_CREADO,
            target=requirement.id,
            detail=f"{len(requirement.attachments)} adjunto(s), PHI «{requirement.phi.value}»",
        )
        # No bloquea: solo deja constancia de los tipos encontrados, nunca del valor.
        typed = scan_typed_text(
            " ".join((requirement.title, requirement.description, *requirement.acceptance_criteria))
        )
        if typed:
            await _record(
                self._audit,
                at=now,
                actor=requirement.owner,
                action=AuditAction.PHI_DETECTADA,
                target=requirement.id,
                detail="tipos en el texto: " + ", ".join(t.value for t in typed),
            )
        if requirement.phi is not PhiClassification.DESCONOCIDO:
            await _record(
                self._audit,
                at=now,
                actor=requirement.owner,
                action=AuditAction.CLASIFICACION_PHI,
                target=requirement.id,
                detail=requirement.phi.value,
            )
        return requirement


class GetRequirement:
    def __init__(self, *, requirements: RequirementRepository) -> None:
        self._requirements = requirements

    async def __call__(self, requirement_id: str) -> Requirement:
        requirement = await self._requirements.get(requirement_id)
        if requirement is None:
            raise NotFoundError(f"No existe el requerimiento {requirement_id}.")
        return requirement


class ListRequirements:
    def __init__(self, *, requirements: RequirementRepository) -> None:
        self._requirements = requirements

    async def __call__(self) -> list[Requirement]:
        return await self._requirements.list()


class SuggestPlan:
    """Sugiere el plan y lo guarda. La persona puede cambiarlo después.

    La base son las reglas deterministas. Con `assisted=True` se le pide además al Orquestador
    que revise la propuesta: puede cambiar la sugerencia y el motivo de un agente opcional, pero
    no puede saltarse lo obligatorio ni decidir por el usuario. Si el agente falla, se devuelve
    el plan determinista en vez de quedarse sin plan.
    """

    def __init__(
        self,
        *,
        requirements: RequirementRepository,
        plans: PlanRepository,
        clock: Clock,
        gateway: AgentGateway | None = None,
        profiles: ProfileRepository | None = None,
        audit: AuditLog | None = None,
    ) -> None:
        self._requirements = requirements
        self._plans = plans
        self._clock = clock
        self._gateway = gateway
        self._profiles = profiles
        self._audit = audit

    async def __call__(self, requirement_id: str, *, assisted: bool = False) -> PlanView:
        requirement = await GetRequirement(requirements=self._requirements)(requirement_id)
        plan = suggest_plan(requirement, now=self._clock.now())

        if assisted:
            plan = await self._assist(requirement, plan)

        await self._plans.save(requirement_id, plan)
        await _record(
            self._audit,
            at=self._clock.now(),
            actor=requirement.owner,
            action=AuditAction.PLAN_SUGERIDO,
            target=requirement_id,
            detail=(
                f"{len(plan.enabled_agents)} agente(s) activos"
                + (" · revisado por el orquestador" if assisted else "")
            ),
        )
        return PlanView(plan=plan, warnings=plan_warnings(requirement, plan))

    async def _assist(self, requirement: Requirement, plan: Plan) -> Plan:
        if self._gateway is None or self._profiles is None:
            return plan
        profile = (await self._profiles.effective(requirement.id))[AgentId.ORCHESTRATOR]
        request = AgentRequest(
            run_id=f"plan:{requirement.id}",
            agent_id=AgentId.ORCHESTRATOR,
            profile=profile.snapshot(),
            system_prompt=profile.system_prompt,
            task_prompt=profile.task_prompt,
            context={
                "requirement_id": requirement.id,
                "title": requirement.title,
                "description": requirement.description,
                "acceptance_criteria": list(requirement.acceptance_criteria),
                "phi": requirement.phi.value,
                "attachments": [
                    {"kind": a.kind.value, "name": a.name, "detail": a.detail}
                    for a in requirement.attachments
                ],
                "plan": [
                    {"agent": i.agent_id.value, "suggested": i.suggested, "reason": i.reason}
                    for i in plan.items
                ],
            },
            phi=requirement.phi,
        )
        try:
            result = await self._gateway.run_agent(request)
        except Exception as exc:  # sin plan asistido se sigue con el determinista
            log.warning("el orquestador no pudo revisar el plan de %s: %s", requirement.id, exc)
            return plan
        items = result.output.get("items")
        if not isinstance(items, list):
            return plan
        return merge_suggestions(requirement, plan, [i for i in items if isinstance(i, dict)])


class GetPlan:
    def __init__(self, *, requirements: RequirementRepository, plans: PlanRepository) -> None:
        self._requirements = requirements
        self._plans = plans

    async def __call__(self, requirement_id: str) -> PlanView:
        requirement = await GetRequirement(requirements=self._requirements)(requirement_id)
        plan = await self._plans.get(requirement_id)
        if plan is None:
            raise NotFoundError(f"El requerimiento {requirement_id} todavía no tiene plan.")
        return PlanView(plan=plan, warnings=plan_warnings(requirement, plan))


class AddAttachment:
    """Añade un adjunto al requerimiento.

    De momento guarda el nombre y el tipo: el archivo de verdad, con su cifrado y su
    retención, es ORQ-19. Lo que sí hace ya es cambiar lo que el plan puede proponer.
    """

    def __init__(
        self,
        *,
        requirements: RequirementRepository,
        clock: Clock,
        ids: IdGenerator,
        audit: AuditLog | None = None,
    ) -> None:
        self._requirements = requirements
        self._clock = clock
        self._ids = ids
        self._audit = audit

    async def __call__(self, command: AddAttachmentCommand) -> Requirement:
        requirement = await GetRequirement(requirements=self._requirements)(
            command.requirement_id
        )
        now = self._clock.now()
        attachment = Attachment(
            id=await self._ids.new_id("ATT"),
            kind=command.kind,
            name=command.name,
            detail=command.detail,
            added_by=command.added_by or requirement.owner,
            added_at=now,
        )
        updated = requirement.with_attachment(attachment)
        await self._requirements.save(updated)
        await _record(
            self._audit,
            at=now,
            actor=attachment.added_by,
            action=AuditAction.AJUSTE_LOCAL,
            target=requirement.id,
            detail=f"adjunto {command.kind.value}",
        )
        return updated


class ConnectRepo:
    """Conecta el repositorio del cambio y fija el `head_sha` de la revisión.

    Todo ocurre en el servidor: la credencial sale de la configuración (bóveda en ORQ-18) y **no
    aparece en la respuesta**, que solo lleva la ficha pública del repositorio. Reconectar
    sustituye la ficha; las ejecuciones ya hechas conservan el commit que revisaron.
    """

    def __init__(
        self,
        *,
        requirements: RequirementRepository,
        repos: RepoConnector,
        clock: Clock,
        ids: IdGenerator,
        audit: AuditLog | None = None,
    ) -> None:
        self._requirements = requirements
        self._repos = repos
        self._clock = clock
        self._ids = ids
        self._audit = audit

    async def __call__(self, command: ConnectRepoCommand) -> Requirement:
        requirement = await GetRequirement(requirements=self._requirements)(
            command.requirement_id
        )
        if not command.url.strip():
            raise DomainError("Hace falta la URL del repositorio.")

        info = await self._repos.connect(
            url=command.url.strip(),
            branch=command.branch.strip(),
            base=command.base.strip(),
            last_commits=command.last_commits,
        )
        now = self._clock.now()
        actor = command.by or requirement.owner
        attachment = Attachment(
            id=await self._ids.new_id("ATT"),
            kind=AttachmentKind.REPO,
            name=info.full_name or info.name,
            detail=info.range_label,
            added_by=actor,
            added_at=now,
            repo=info,
        )
        updated = requirement.with_repo(attachment)
        await self._requirements.save(updated)
        await _record(
            self._audit,
            at=now,
            actor=actor,
            action=AuditAction.REPOSITORIO_CONECTADO,
            target=requirement.id,
            detail=(
                f"{info.full_name or info.name} · {info.range_label} · "
                f"{info.head_sha[:12]} · {len(info.files)} archivo(s)"
            ),
        )
        return updated


class SaveSecret:
    """Guarda o rota un secreto.

    Devuelve **metadatos**, que no tienen campo para el valor: el endpoint no puede filtrarlo
    aunque quiera. Guardar dos veces el mismo (tipo, nombre, ámbito) es rotar, no duplicar, y
    levanta una revocación anterior.
    """

    def __init__(self, *, vault: SecretVault, clock: Clock, audit: AuditLog | None = None) -> None:
        self._vault = vault
        self._clock = clock
        self._audit = audit

    async def __call__(self, command: SaveSecretCommand) -> SecretMetadata:
        now = self._clock.now()
        # Para saber si es una rotación se miran los **metadatos**, no `reveal`: pedir el valor
        # contaría como un uso, y guardar un secreto no es usarlo.
        nombre = command.name.strip().lower()
        anterior = any(
            m.kind is command.kind and m.name == nombre and m.scope == command.scope
            for m in await self._vault.list(scope=command.scope)
        )
        metadata = await self._vault.save(
            NewSecret(
                kind=command.kind,
                name=command.name,
                value=command.value,
                scope=command.scope,
                username=command.username,
                expires_at=command.expires_at,
                created_by=command.by,
            ),
            at=now,
        )
        await _record(
            self._audit,
            at=now,
            actor=command.by,
            action=AuditAction.SECRETO_GUARDADO,
            target=metadata.id,
            detail=(
                f"{'rotado' if anterior else 'guardado'} · "
                f"{metadata.kind.value} · {metadata.name} · "
                f"{'organización' if not metadata.scope else metadata.scope} · {metadata.hint}"
            ),
        )
        return metadata


class ListSecrets:
    """Qué hay guardado. Solo metadatos: no existe un caso de uso que devuelva valores."""

    def __init__(self, *, vault: SecretVault, clock: Clock) -> None:
        self._vault = vault
        self._clock = clock

    async def __call__(self, *, scope: str | None = None) -> list[SecretMetadata]:
        return await self._vault.list(scope=scope)


class RevokeSecret:
    """Revoca un secreto. Deja de funcionar de inmediato y su valor se borra de la base."""

    def __init__(self, *, vault: SecretVault, clock: Clock, audit: AuditLog | None = None) -> None:
        self._vault = vault
        self._clock = clock
        self._audit = audit

    async def __call__(self, secret_id: str, *, by: str) -> SecretMetadata:
        now = self._clock.now()
        metadata = await self._vault.revoke(secret_id, at=now, by=by)
        await _record(
            self._audit,
            at=now,
            actor=by,
            action=AuditAction.SECRETO_REVOCADO,
            target=metadata.id,
            detail=f"{metadata.kind.value} · {metadata.name} · {metadata.hint}",
        )
        return metadata


class ClassifyPhi:
    """Clasifica el requerimiento. Con PHI, el agente de Privacidad pasa a ser obligatorio."""

    def __init__(
        self,
        *,
        requirements: RequirementRepository,
        plans: PlanRepository,
        clock: Clock,
        audit: AuditLog | None = None,
    ) -> None:
        self._requirements = requirements
        self._plans = plans
        self._clock = clock
        self._audit = audit

    async def __call__(self, command: ClassifyPhiCommand) -> Requirement:
        requirement = await GetRequirement(requirements=self._requirements)(
            command.requirement_id
        )
        updated = requirement.classified_as(command.phi, by=command.by)
        await self._requirements.save(updated)
        await _record(
            self._audit,
            at=self._clock.now(),
            actor=command.by,
            action=AuditAction.CLASIFICACION_PHI,
            target=updated.id,
            detail=command.phi.value,
        )
        return updated


class UpdatePlan:
    """Aplica lo que la persona activó o desactivó.

    El orquestador sugiere; aquí manda el usuario. Lo único que no puede es desactivar lo
    obligatorio: eso lo impide el propio dominio.
    """

    def __init__(
        self,
        *,
        requirements: RequirementRepository,
        plans: PlanRepository,
        clock: Clock,
        audit: AuditLog | None = None,
    ) -> None:
        self._requirements = requirements
        self._plans = plans
        self._clock = clock
        self._audit = audit

    async def __call__(self, command: UpdatePlanCommand) -> PlanView:
        requirement = await GetRequirement(requirements=self._requirements)(
            command.requirement_id
        )
        plan = await self._plans.get(command.requirement_id)
        if plan is None:
            raise NotFoundError(
                f"El requerimiento {command.requirement_id} todavía no tiene plan."
            )

        requested = set(command.enabled_agents)
        for item in plan.items:
            if locked_reason(requirement, item.agent_id) is not None:
                continue  # obligatorio: no se toca
            plan = plan.toggled(
                item.agent_id, enabled=item.agent_id in requested, by=command.by
            )

        await self._plans.save(command.requirement_id, plan)
        await _record(
            self._audit,
            at=self._clock.now(),
            actor=command.by,
            action=AuditAction.AJUSTE_LOCAL,
            target=command.requirement_id,
            detail=f"plan con {len(plan.enabled_agents)} agente(s)",
        )
        return PlanView(plan=plan, warnings=plan_warnings(requirement, plan))


class StartRun:
    """Congela los perfiles, valida el plan y lanza la revisión en segundo plano."""

    def __init__(
        self,
        *,
        requirements: RequirementRepository,
        plans: PlanRepository,
        runs: RunRepository,
        profiles: ProfileRepository,
        supervisor: RunSupervisor,
        clock: Clock,
        ids: IdGenerator,
        audit: AuditLog | None = None,
    ) -> None:
        self._requirements = requirements
        self._plans = plans
        self._runs = runs
        self._profiles = profiles
        self._supervisor = supervisor
        self._clock = clock
        self._ids = ids
        self._audit = audit

    async def __call__(self, command: StartRunCommand) -> Run:
        requirement = await GetRequirement(requirements=self._requirements)(command.requirement_id)
        plan = await self._plans.get(command.requirement_id)
        if plan is None:
            plan = suggest_plan(requirement, now=self._clock.now())
            await self._plans.save(command.requirement_id, plan)

        if command.enabled_agents is not None:
            requested = set(command.enabled_agents)
            for item in plan.items:
                plan = plan.toggled(
                    item.agent_id, enabled=item.agent_id in requested, by=command.started_by
                )

        warnings = plan_warnings(requirement, plan)
        blocking = [w.text for w in warnings if w.blocks]
        if blocking:
            raise PlanBlockedError(blocking)
        await self._plans.save(command.requirement_id, plan)

        enabled = tuple(
            agent_id
            for agent_id in ALL_AGENTS
            if agent_id is not AgentId.CHAT
            and (plan.is_enabled(agent_id) or not AGENTS[agent_id].optional)
        )

        effective = await self._profiles.effective(command.requirement_id)
        run = Run(
            id=await self._ids.new_id("RUN"),
            requirement_id=requirement.id,
            started_by=command.started_by,
            started_at=self._clock.now(),
            enabled_agents=enabled,
            profiles={agent_id: effective[agent_id].snapshot() for agent_id in enabled},
        )
        await self._runs.add(run)
        await _record(
            self._audit,
            at=run.started_at,
            actor=command.started_by,
            action=AuditAction.EJECUCION_INICIADA,
            target=run.id,
            detail=f"{requirement.id} · {len(enabled)} agente(s)",
        )
        self._supervisor.start(
            requirement=requirement, plan=plan, run=run, profiles=effective
        )
        if command.wait:
            await self._supervisor.wait(run.id)
        return run


class CancelRun:
    """Detiene una ejecución en curso."""

    def __init__(
        self,
        *,
        runs: RunRepository,
        supervisor: RunSupervisor,
        clock: Clock,
        audit: AuditLog | None = None,
    ) -> None:
        self._runs = runs
        self._supervisor = supervisor
        self._clock = clock
        self._audit = audit

    async def __call__(self, run_id: str, *, by: str) -> Run:
        run = await self._runs.get(run_id)
        if run is None:
            raise NotFoundError(f"No existe la ejecución {run_id}.")
        if run.is_finished:
            raise DomainError(f"La ejecución {run_id} ya terminó ({run.status.value}).")

        await _record(
            self._audit,
            at=self._clock.now(),
            actor=by,
            action=AuditAction.EJECUCION_CANCELADA,
            target=run_id,
            detail=run.requirement_id,
        )
        if self._supervisor.cancel(run_id):
            await self._supervisor.wait(run_id, timeout=30)
            return (await self._runs.get(run_id)) or run

        # Quedó en curso pero no se está ejecutando aquí: caída anterior del servicio.
        now = self._clock.now()
        for execution in run.executions.values():
            if execution.status in (AgentRunStatus.TRABAJANDO, AgentRunStatus.PENDIENTE):
                execution.status = AgentRunStatus.OMITIDO
                execution.reason = f"Cancelada por {by}."
                execution.finished_at = now
        run.status = RunStatus.CANCELADA
        run.cancelled_at = now
        run.finished_at = now
        await self._runs.save(run)
        return run


class ResumeInterruptedRuns:
    """Recupera las ejecuciones que quedaron a medias por una caída del servicio.

    Lo ya completado se conserva; solo se reanuda lo pendiente, y con los perfiles **congelados**
    en la ejecución, no con los de hoy. Si el prompt de esa versión ya no está, la ejecución se
    marca como fallida con el motivo en vez de continuar con otra configuración.
    """

    def __init__(
        self,
        *,
        requirements: RequirementRepository,
        plans: PlanRepository,
        runs: RunRepository,
        profiles: ProfileRepository,
        supervisor: RunSupervisor,
        clock: Clock,
        audit: AuditLog | None = None,
    ) -> None:
        self._requirements = requirements
        self._plans = plans
        self._runs = runs
        self._profiles = profiles
        self._supervisor = supervisor
        self._clock = clock
        self._audit = audit

    async def __call__(self, *, wait: bool = False) -> list[Run]:
        resumed: list[Run] = []
        for run in await self._runs.list_unfinished():
            if self._supervisor.is_running(run.id):
                continue
            try:
                requirement, plan, profiles = await self._recover(run)
            except DomainError as error:
                await self._abandon(run, str(error))
                continue

            for execution in run.executions.values():
                if execution.status is AgentRunStatus.TRABAJANDO:
                    execution.status = AgentRunStatus.PENDIENTE
                    execution.reason = "Reanudada tras una interrupción."
            await self._runs.save(run)

            await _record(
                self._audit,
                at=self._clock.now(),
                actor="sistema",
                action=AuditAction.EJECUCION_REANUDADA,
                target=run.id,
                detail=run.requirement_id,
            )
            self._supervisor.start(
                requirement=requirement, plan=plan, run=run, profiles=profiles
            )
            if wait:
                await self._supervisor.wait(run.id)
            resumed.append(run)
        return resumed

    async def _recover(self, run: Run) -> tuple[Requirement, Plan, dict[AgentId, AgentProfile]]:
        requirement = await self._requirements.get(run.requirement_id)
        if requirement is None:
            raise DomainError(f"El requerimiento {run.requirement_id} ya no existe.")
        plan = await self._plans.get(run.requirement_id)
        if plan is None:
            raise DomainError("La ejecución no conserva su plan.")
        current = await self._profiles.effective(run.requirement_id)
        profiles = {
            agent_id: current[agent_id].restored(snapshot)
            for agent_id, snapshot in run.profiles.items()
        }
        return requirement, plan, profiles

    async def _abandon(self, run: Run, reason: str) -> None:
        run.status = RunStatus.FALLIDA
        run.error = f"No se pudo reanudar: {reason}"
        run.finished_at = self._clock.now()
        for execution in run.executions.values():
            if execution.status in (AgentRunStatus.TRABAJANDO, AgentRunStatus.PENDIENTE):
                execution.status = AgentRunStatus.OMITIDO
                execution.reason = run.error
        await self._runs.save(run)


class GetRun:
    def __init__(self, *, runs: RunRepository) -> None:
        self._runs = runs

    async def __call__(self, run_id: str, *, with_events: bool = False) -> RunView:
        run = await self._runs.get(run_id)
        if run is None:
            raise NotFoundError(f"No existe la ejecución {run_id}.")
        events = tuple(await self._runs.events(run_id)) if with_events else ()
        return RunView(run=run, deliverables=build_deliverables(run), events=events)


class ListRuns:
    def __init__(self, *, runs: RunRepository) -> None:
        self._runs = runs

    async def __call__(self, requirement_id: str) -> list[Run]:
        return await self._runs.list_for_requirement(requirement_id)


class GetDeliverables:
    def __init__(self, *, runs: RunRepository) -> None:
        self._runs = runs

    async def __call__(self, run_id: str) -> Deliverables:
        return (await GetRun(runs=self._runs)(run_id)).deliverables


class ListProfiles:
    def __init__(self, *, profiles: ProfileRepository) -> None:
        self._profiles = profiles

    async def __call__(self, requirement_id: str | None = None) -> dict[AgentId, AgentProfile]:
        if requirement_id is None:
            return await self._profiles.defaults()
        return await self._profiles.effective(requirement_id)


__all__ = [
    "AddAttachment",
    "AddAttachmentCommand",
    "CancelRun",
    "ClassifyPhi",
    "ClassifyPhiCommand",
    "CreateRequirement",
    "CreateRequirementCommand",
    "GetDeliverables",
    "GetPlan",
    "GetRequirement",
    "GetRun",
    "ListProfiles",
    "ListRequirements",
    "ListRuns",
    "NewAttachment",
    "PlanView",
    "ResumeInterruptedRuns",
    "RunView",
    "StartRun",
    "StartRunCommand",
    "SuggestPlan",
    "UpdatePlan",
    "UpdatePlanCommand",
]
