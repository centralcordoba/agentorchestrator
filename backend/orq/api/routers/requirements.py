"""Requerimientos: alta, consulta, plan y lanzamiento de la revisión."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import Field

from ...application.deliverables import build_deliverables
from ...application.use_cases import (
    AddAttachmentCommand,
    ClassifyPhiCommand,
    ConnectRepoCommand,
    CreateRequirementCommand,
    NewAttachment,
    StartRunCommand,
    UpdatePlanCommand,
)
from ...domain.enums import AgentId, AgentRunStatus, AttachmentKind, PhiClassification
from ...domain.run import Run
from ..container import Container
from ...domain.identity import Permission
from ..deps import current_user, get_container, requires
from ..schemas import (
    ERROR_RESPONSES,
    PlanViewOut,
    RequirementOut,
    RequirementSummaryOut,
    RunOut,
    RunSummaryOut,
    Schema,
)

router = APIRouter(prefix="/requirements", tags=["requerimientos"], responses=ERROR_RESPONSES)


class AttachmentIn(Schema):
    kind: AttachmentKind
    name: str
    detail: str = ""


class CreateRequirementIn(Schema):
    """El responsable no viene aquí: es el usuario autenticado (ORQ-5)."""

    title: str = Field(min_length=1)
    description: str = ""
    acceptance_criteria: list[str] = Field(default_factory=list)
    phi: PhiClassification = PhiClassification.DESCONOCIDO
    attachments: list[AttachmentIn] = Field(default_factory=list)


class ClassifyPhiIn(Schema):
    phi: PhiClassification


class ConnectRepoIn(Schema):
    """Repositorio a revisar. **La credencial no viaja aquí**: la pone el servidor (ORQ-18)."""

    url: str = Field(min_length=1, description="URL de clonado (HTTPS o SSH)")
    branch: str = Field("", description="Rama del desarrollo. Vacío = la rama por defecto")
    base: str = Field("", description="Rama o commit base. Vacío = últimos «lastCommits» commits")
    last_commits: int = Field(
        1, ge=1, le=50, description="Cuántos commits atrás comparar si no se da base"
    )


class UpdatePlanIn(Schema):
    #: Agentes que quedan activos. Los obligatorios no se pueden quitar.
    enabled_agents: list[AgentId]


class StartRunIn(Schema):
    #: Agentes que quedan activos. Ausente = los del plan guardado.
    enabled_agents: list[AgentId] | None = None


class RequirementPage(Schema):
    items: list[RequirementSummaryOut]
    total: int
    limit: int
    offset: int


class RunPage(Schema):
    items: list[RunOut]
    total: int
    limit: int
    offset: int


@router.post("", status_code=201, response_model=RequirementOut)
async def create(
    body: CreateRequirementIn,
    user=Depends(requires(Permission.CREAR_REQUERIMIENTO)),
    container: Container = Depends(get_container),
) -> RequirementOut:
    command = CreateRequirementCommand(
        title=body.title,
        description=body.description,
        owner=user.email,
        acceptance_criteria=tuple(body.acceptance_criteria),
        phi=body.phi,
        attachments=tuple(
            NewAttachment(kind=a.kind, name=a.name, detail=a.detail) for a in body.attachments
        ),
    )
    return RequirementOut.from_domain(await container.create_requirement()(command))


def _summarize(run: Run) -> RunSummaryOut:
    completed = [
        e for e in run.executions.values() if e.status is AgentRunStatus.COMPLETADO
    ]
    verdict = build_deliverables(run).verdict
    return RunSummaryOut(
        id=run.id,
        status=run.status.value,
        started_at=run.started_at,
        finished_at=run.finished_at,
        total_agents=len(run.enabled_agents),
        completed_agents=len(completed),
        verdict=verdict.verdict.value if verdict else None,
    )


@router.get("", response_model=RequirementPage)
async def index(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user=Depends(current_user),
    container: Container = Depends(get_container),
) -> RequirementPage:
    """Lista paginada con lo que la tabla necesita: última ejecución y agentes planificados.

    Se consulta la última ejecución y el plan de cada requerimiento de la página (una consulta
    por fila). Con páginas de 50 es asumible; si el Monitor lo nota, se agrupa en una sola
    consulta (ORQ-29).
    """
    requirements = await container.requirements.list(limit=limit, offset=offset)
    items: list[RequirementSummaryOut] = []
    for requirement in requirements:
        runs = await container.runs.list_for_requirement(requirement.id, limit=1)
        plan = await container.plans.get(requirement.id)
        items.append(
            RequirementSummaryOut(
                **RequirementOut.from_domain(requirement).model_dump(),
                last_run=_summarize(runs[0]) if runs else None,
                planned_agents=[a.value for a in plan.enabled_agents] if plan else [],
            )
        )
    return RequirementPage(
        items=items,
        total=await container.requirements.count(),
        limit=limit,
        offset=offset,
    )


@router.get("/{requirement_id}", response_model=RequirementOut)
async def detail(
    requirement_id: str,
    user=Depends(current_user),
    container: Container = Depends(get_container),
) -> RequirementOut:
    return RequirementOut.from_domain(await container.get_requirement()(requirement_id))


@router.post("/{requirement_id}/attachments", status_code=201, response_model=RequirementOut)
async def add_attachment(
    requirement_id: str,
    body: AttachmentIn,
    user=Depends(requires(Permission.CREAR_REQUERIMIENTO)),
    container: Container = Depends(get_container),
) -> RequirementOut:
    """Adjunta un repositorio o un archivo al requerimiento.

    Guarda el tipo y el nombre; el archivo en sí, cifrado y con retención, es ORQ-19.
    """
    requirement = await container.add_attachment()(
        AddAttachmentCommand(
            requirement_id=requirement_id,
            kind=body.kind,
            name=body.name,
            detail=body.detail,
            added_by=user.email,
        )
    )
    return RequirementOut.from_domain(requirement)


@router.post("/{requirement_id}/repo", response_model=RequirementOut)
async def connect_repo(
    requirement_id: str,
    body: ConnectRepoIn,
    user=Depends(requires(Permission.CREAR_REQUERIMIENTO)),
    container: Container = Depends(get_container),
) -> RequirementOut:
    """Conecta el repositorio del cambio y fija el commit que se va a revisar.

    El clonado y la credencial se quedan en el servidor: la respuesta solo lleva la ficha pública
    del repositorio (rama, rango, commits y archivos del cambio).
    """
    requirement = await container.connect_repo()(
        ConnectRepoCommand(
            requirement_id=requirement_id,
            url=body.url,
            branch=body.branch,
            base=body.base,
            last_commits=body.last_commits,
            by=user.email,
        )
    )
    return RequirementOut.from_domain(requirement)


@router.put("/{requirement_id}/phi", response_model=RequirementOut)
async def classify_phi(
    requirement_id: str,
    body: ClassifyPhiIn,
    user=Depends(requires(Permission.CREAR_REQUERIMIENTO)),
    container: Container = Depends(get_container),
) -> RequirementOut:
    """Clasifica el requerimiento. Con PHI, Privacidad pasa a ser obligatorio."""
    requirement = await container.classify_phi()(
        ClassifyPhiCommand(requirement_id=requirement_id, phi=body.phi, by=user.email)
    )
    return RequirementOut.from_domain(requirement)


@router.put("/{requirement_id}/plan", response_model=PlanViewOut)
async def update_plan(
    requirement_id: str,
    body: UpdatePlanIn,
    user=Depends(requires(Permission.EJECUTAR)),
    container: Container = Depends(get_container),
) -> PlanViewOut:
    """Aplica lo que la persona activó o desactivó. Lo obligatorio no se puede quitar."""
    view = await container.update_plan()(
        UpdatePlanCommand(
            requirement_id=requirement_id,
            enabled_agents=tuple(body.enabled_agents),
            by=user.email,
        )
    )
    return PlanViewOut.from_domain(view.plan, view.warnings)


@router.post("/{requirement_id}/plan", response_model=PlanViewOut)
async def suggest_plan(
    requirement_id: str,
    assisted: bool = Query(
        False, description="Pedir además al Orquestador que revise la propuesta"
    ),
    user=Depends(requires(Permission.EJECUTAR)),
    container: Container = Depends(get_container),
) -> PlanViewOut:
    """Sugiere el plan con las reglas deterministas. El usuario decide después.

    Con `assisted=true` el Orquestador revisa la propuesta; no puede saltarse lo obligatorio.
    """
    view = await container.suggest_plan()(requirement_id, assisted=assisted)
    return PlanViewOut.from_domain(view.plan, view.warnings)


@router.get("/{requirement_id}/plan", response_model=PlanViewOut)
async def get_plan(
    requirement_id: str,
    user=Depends(current_user),
    container: Container = Depends(get_container),
) -> PlanViewOut:
    view = await container.get_plan()(requirement_id)
    return PlanViewOut.from_domain(view.plan, view.warnings)


@router.post("/{requirement_id}/runs", status_code=201, response_model=RunOut)
async def start_run(
    requirement_id: str,
    body: StartRunIn,
    user=Depends(requires(Permission.EJECUTAR)),
    container: Container = Depends(get_container),
) -> RunOut:
    """Lanza la revisión y devuelve de inmediato: la ejecución sigue en segundo plano."""
    command = StartRunCommand(
        requirement_id=requirement_id,
        started_by=user.email,
        enabled_agents=tuple(body.enabled_agents) if body.enabled_agents is not None else None,
    )
    return RunOut.from_domain(await container.start_run()(command))


@router.get("/{requirement_id}/runs", response_model=RunPage)
async def list_runs(
    requirement_id: str,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user=Depends(current_user),
    container: Container = Depends(get_container),
) -> RunPage:
    runs = await container.runs.list_for_requirement(requirement_id, limit=limit, offset=offset)
    return RunPage(
        items=[RunOut.from_domain(r) for r in runs],
        total=await container.runs.count_for_requirement(requirement_id),
        limit=limit,
        offset=offset,
    )
