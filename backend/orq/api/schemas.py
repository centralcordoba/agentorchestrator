"""Contrato público de la API."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Generic, Sequence, TypeVar

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from ..domain.audit import AuditEntry
from ..domain.deliverables import Deliverables
from ..domain.enums import AgentId
from ..domain.plan import Plan, PlanWarning
from ..domain.profiles import AgentProfile
from ..domain.requirement import Attachment, RepoInfo, Requirement
from ..domain.run import AgentExecution, LLMCall, Run, TraceEvent, Usage
from ..domain.identity import ROLE_LABELS, User
from ..domain.secrets import KIND_LABELS, SecretMetadata


class Schema(BaseModel):
    """Base de todos los modelos: nombres en camelCase y aceptando también snake_case."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, from_attributes=True)


T = TypeVar("T")


class Page(Schema, Generic[T]):
    """Página de una lista que crece: requerimientos, ejecuciones, auditoría."""

    items: list[T]
    total: int
    limit: int
    offset: int

    @property
    def has_more(self) -> bool:
        return self.offset + len(self.items) < self.total


class ApiError(Schema):
    """Forma única de todos los errores. La UI la traduce a un mensaje por `code`."""

    code: str = Field(description="Identificador estable del error, p. ej. NotFoundError")
    message: str = Field(description="Mensaje en español, ya legible")
    detail: dict[str, Any] | None = Field(default=None, description="Datos extra del error")


ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    400: {"model": ApiError, "description": "Petición inválida"},
    402: {"model": ApiError, "description": "Presupuesto de la ejecución agotado"},
    403: {"model": ApiError, "description": "Prohibido por política (PHI, BAA, herramienta)"},
    404: {"model": ApiError, "description": "No existe"},
    409: {"model": ApiError, "description": "Conflicto: el plan está bloqueado"},
    422: {"model": ApiError, "description": "La petición no tiene el formato esperado"},
    500: {"model": ApiError, "description": "Error interno"},
    502: {"model": ApiError, "description": "Fallo del proveedor de IA"},
}


class RepoFileOut(Schema):
    path: str
    status: str
    additions: int = 0
    deletions: int = 0
    has_patch: bool = False


class RepoCommitOut(Schema):
    sha: str
    message: str = ""
    author: str = ""
    date: str = ""
    url: str = ""


class RepoOut(Schema):
    provider: str
    owner: str
    name: str
    full_name: str
    html_url: str
    default_branch: str
    branch: str
    base: str
    head_sha: str
    description: str = ""
    range_label: str = ""
    compare_url: str = ""
    ahead_by: int = 0
    files_truncated: bool = False
    languages: dict[str, int] = Field(default_factory=dict)
    commits: list[RepoCommitOut] = Field(default_factory=list)
    files: list[RepoFileOut] = Field(default_factory=list)
    fetched_at: datetime | None = None

    @classmethod
    def from_domain(cls, repo: RepoInfo) -> "RepoOut":
        return cls(
            provider=repo.provider,
            owner=repo.owner,
            name=repo.name,
            full_name=repo.full_name,
            html_url=repo.html_url,
            default_branch=repo.default_branch,
            branch=repo.branch,
            base=repo.base,
            head_sha=repo.head_sha,
            description=repo.description,
            range_label=repo.range_label,
            compare_url=repo.compare_url,
            ahead_by=repo.ahead_by,
            files_truncated=repo.files_truncated,
            languages=dict(repo.languages),
            commits=[
                RepoCommitOut(
                    sha=c.sha, message=c.message, author=c.author, date=c.date, url=c.url
                )
                for c in repo.commits
            ],
            files=[
                RepoFileOut(
                    path=f.path,
                    status=f.status.value,
                    additions=f.additions,
                    deletions=f.deletions,
                    has_patch=f.has_patch,
                )
                for f in repo.files
            ],
            fetched_at=repo.fetched_at,
        )


class AttachmentOut(Schema):
    id: str
    kind: str
    name: str
    detail: str = ""
    added_by: str
    added_at: datetime
    repo: RepoOut | None = None

    @classmethod
    def from_domain(cls, attachment: Attachment) -> "AttachmentOut":
        return cls(
            id=attachment.id,
            kind=attachment.kind.value,
            name=attachment.name,
            detail=attachment.detail,
            added_by=attachment.added_by,
            added_at=attachment.added_at,
            repo=RepoOut.from_domain(attachment.repo) if attachment.repo else None,
        )


class RequirementOut(Schema):
    id: str
    title: str
    description: str
    owner: str
    created_at: datetime
    acceptance_criteria: list[str] = Field(default_factory=list)
    phi: str
    phi_set_by: str = ""
    handles_phi: bool
    attachments: list[AttachmentOut] = Field(default_factory=list)

    @classmethod
    def from_domain(cls, requirement: Requirement) -> "RequirementOut":
        return cls(
            id=requirement.id,
            title=requirement.title,
            description=requirement.description,
            owner=requirement.owner,
            created_at=requirement.created_at,
            acceptance_criteria=list(requirement.acceptance_criteria),
            phi=requirement.phi.value,
            phi_set_by=requirement.phi_set_by,
            handles_phi=requirement.handles_phi,
            attachments=[AttachmentOut.from_domain(a) for a in requirement.attachments],
        )


class PlanItemOut(Schema):
    agent_id: str
    suggested: bool
    enabled: bool
    reason: str = ""
    source: str = "regla"


class PlanWarningOut(Schema):
    agent_id: str
    level: str
    text: str
    blocks: bool


class PlanOut(Schema):
    items: list[PlanItemOut]
    suggested_at: datetime
    overridden_by: str = ""
    enabled_agents: list[str] = Field(default_factory=list)

    @classmethod
    def from_domain(cls, plan: Plan) -> "PlanOut":
        return cls(
            items=[
                PlanItemOut(
                    agent_id=i.agent_id.value,
                    suggested=i.suggested,
                    enabled=i.enabled,
                    reason=i.reason,
                    source=i.source,
                )
                for i in plan.items
            ],
            suggested_at=plan.suggested_at,
            overridden_by=plan.overridden_by,
            enabled_agents=[a.value for a in plan.enabled_agents],
        )


class PlanViewOut(Schema):
    plan: PlanOut
    warnings: list[PlanWarningOut] = Field(default_factory=list)
    blocked: bool

    @classmethod
    def from_domain(cls, plan: Plan, warnings: Sequence[PlanWarning]) -> "PlanViewOut":
        return cls(
            plan=PlanOut.from_domain(plan),
            warnings=[
                PlanWarningOut(
                    agent_id=w.agent_id.value, level=w.level.value, text=w.text, blocks=w.blocks
                )
                for w in warnings
            ],
            blocked=any(w.blocks for w in warnings),
        )


class UsageOut(Schema):
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0

    @classmethod
    def from_domain(cls, usage: Usage) -> "UsageOut":
        return cls(
            tokens_in=usage.tokens_in, tokens_out=usage.tokens_out, cost_usd=usage.cost_usd
        )


class ProfileSnapshotOut(Schema):
    """Lo que se congeló al arrancar la ejecución. No cambia nunca."""

    provider: str
    model: str
    prompt_version: int
    temperature: float = 0.0
    max_steps: int = 4


class LLMCallOut(Schema):
    """Metadatos de una llamada al modelo. Sin contenido: podría llevar PHI."""

    agent_id: str
    provider: str
    model: str
    prompt_version: int
    usage: UsageOut
    duration_ms: int
    attempts: int = 1
    tools_used: list[str] = Field(default_factory=list)
    tools_rejected: list[str] = Field(default_factory=list)
    at: datetime | None = None
    error: str = ""

    @classmethod
    def from_domain(cls, call: LLMCall) -> "LLMCallOut":
        return cls(
            agent_id=call.agent_id.value,
            provider=call.provider.value,
            model=call.model,
            prompt_version=call.prompt_version,
            usage=UsageOut.from_domain(call.usage),
            duration_ms=call.duration_ms,
            attempts=call.attempts,
            tools_used=list(call.tools_used),
            tools_rejected=list(call.tools_rejected),
            at=call.at,
            error=call.error,
        )


class AgentExecutionOut(Schema):
    agent_id: str
    status: str
    reason: str = ""
    error: str = ""
    started_at: datetime | None = None
    finished_at: datetime | None = None
    usage: UsageOut
    calls: list[LLMCallOut] = Field(default_factory=list)

    @classmethod
    def from_domain(cls, execution: AgentExecution) -> "AgentExecutionOut":
        return cls(
            agent_id=execution.agent_id.value,
            status=execution.status.value,
            reason=execution.reason,
            error=execution.error,
            started_at=execution.started_at,
            finished_at=execution.finished_at,
            usage=UsageOut.from_domain(execution.usage),
            calls=[LLMCallOut.from_domain(c) for c in execution.calls],
        )


class RunOut(Schema):
    id: str
    requirement_id: str
    started_by: str
    started_at: datetime
    status: str
    finished_at: datetime | None = None
    cancelled_at: datetime | None = None
    error: str = ""
    enabled_agents: list[str] = Field(default_factory=list)
    profiles: dict[str, ProfileSnapshotOut] = Field(default_factory=dict)
    executions: dict[str, AgentExecutionOut] = Field(default_factory=dict)
    usage: UsageOut

    @classmethod
    def from_domain(cls, run: Run) -> "RunOut":
        return cls(
            id=run.id,
            requirement_id=run.requirement_id,
            started_by=run.started_by,
            started_at=run.started_at,
            status=run.status.value,
            finished_at=run.finished_at,
            cancelled_at=run.cancelled_at,
            error=run.error,
            enabled_agents=[a.value for a in run.enabled_agents],
            profiles={
                agent.value: ProfileSnapshotOut(
                    provider=p.provider.value,
                    model=p.model,
                    prompt_version=p.prompt_version,
                    temperature=p.temperature,
                    max_steps=p.max_steps,
                )
                for agent, p in run.profiles.items()
            },
            executions={
                agent.value: AgentExecutionOut.from_domain(e)
                for agent, e in run.executions.items()
            },
            usage=UsageOut.from_domain(run.usage),
        )


class RunSummaryOut(Schema):
    """Resumen de una ejecución para las listas: lo justo para pintar una fila."""

    id: str
    status: str
    started_at: datetime
    finished_at: datetime | None = None
    total_agents: int = 0
    completed_agents: int = 0
    verdict: str | None = None


class RequirementSummaryOut(RequirementOut):
    """Requerimiento con lo que necesita la lista: última ejecución y agentes planificados."""

    last_run: RunSummaryOut | None = None
    planned_agents: list[str] = Field(default_factory=list)


class TraceEventOut(Schema):
    seq: int
    run_id: str
    at: datetime
    type: str
    agent: str | None = None
    to: str | None = None
    title: str = ""
    detail: str = ""
    data: dict[str, Any] = Field(default_factory=dict)
    usage: UsageOut | None = None

    @classmethod
    def from_domain(cls, event: TraceEvent) -> "TraceEventOut":
        return cls(
            seq=event.seq,
            run_id=event.run_id,
            at=event.at,
            type=event.type.value,
            agent=event.agent.value if event.agent else None,
            to=event.to.value if event.to else None,
            title=event.title,
            detail=event.detail,
            data=event.data,
            usage=UsageOut.from_domain(event.usage) if event.usage else None,
        )


class FindingOut(Schema):
    id: str
    severity: str
    title: str
    detail: str
    source: str
    file: str = ""
    line: int | None = None
    url: str = ""
    suggestion: str = ""
    safeguard: str | None = None


class ChangeMapEntryOut(Schema):
    file: str
    change: str
    added: int = 0
    removed: int = 0
    symbols: list[str] = Field(default_factory=list)
    criteria: list[int] = Field(default_factory=list)


class CodeReportOut(Schema):
    summary: str
    stack: str = ""
    change_map: list[ChangeMapEntryOut] = Field(default_factory=list)
    findings: list[FindingOut] = Field(default_factory=list)


class GeneratedTestOut(Schema):
    name: str
    file: str
    status: str
    kind: str = "unitario"
    criterion: int | None = None
    duration_ms: int = 0
    code: str = ""
    failure_reason: str = ""


class TestsReportOut(Schema):
    framework: str
    command: str = ""
    tests: list[GeneratedTestOut] = Field(default_factory=list)
    coverage: float = 0.0
    findings: list[FindingOut] = Field(default_factory=list)


class KiuwanDefectOut(Schema):
    rule_id: str
    severity: str
    file: str
    rule: str = ""
    category: str = ""
    line: int | None = None
    false_positive: bool = False
    note: str = ""


class KiuwanReportOut(Schema):
    file_name: str = ""
    rows: int = 0
    defects: list[KiuwanDefectOut] = Field(default_factory=list)
    findings: list[FindingOut] = Field(default_factory=list)


class SqlScriptOut(Schema):
    file: str
    statements: int = 0
    kind: str = ""


class SqlReportOut(Schema):
    engine: str = ""
    scripts: list[SqlScriptOut] = Field(default_factory=list)
    findings: list[FindingOut] = Field(default_factory=list)


class UiScenarioOut(Schema):
    name: str
    status: str
    browser: str = ""
    duration_ms: int = 0
    steps: list[str] = Field(default_factory=list)
    a11y_issues: int = 0
    failure_reason: str = ""


class UiuxReportOut(Schema):
    base_url: str = ""
    scenarios: list[UiScenarioOut] = Field(default_factory=list)
    findings: list[FindingOut] = Field(default_factory=list)


class PhiDetectionOut(Schema):
    """Detección de PHI: tipo, archivo y línea. **Nunca el valor.**"""

    identifier: str
    file: str
    where: str
    line: int | None = None
    masked: str = ""
    url: str = ""


class SafeguardCheckOut(Schema):
    id: str
    status: str
    evidence: str = ""


class PrivacyReportOut(Schema):
    detections: list[PhiDetectionOut] = Field(default_factory=list)
    safeguards: list[SafeguardCheckOut] = Field(default_factory=list)
    minimum_necessary: str = ""
    findings: list[FindingOut] = Field(default_factory=list)


class VtrSectionOut(Schema):
    title: str
    status: str
    content: str = ""
    sources: list[str] = Field(default_factory=list)


class VtrReportOut(Schema):
    template_name: str = ""
    output_name: str = ""
    sections: list[VtrSectionOut] = Field(default_factory=list)


class VerdictReportOut(Schema):
    verdict: str
    confidence: float
    rationale: str
    guardrails: list[str] = Field(default_factory=list)


class DeliverablesOut(Schema):
    """Un informe por agente. `null` = ese agente no se ejecutó (y `missing` dice por qué)."""

    code: CodeReportOut | None = None
    tests: TestsReportOut | None = None
    kiuwan: KiuwanReportOut | None = None
    sql: SqlReportOut | None = None
    uiux: UiuxReportOut | None = None
    privacy: PrivacyReportOut | None = None
    vtr: VtrReportOut | None = None
    verdict: VerdictReportOut | None = None
    missing: dict[str, str] = Field(default_factory=dict)
    findings: list[FindingOut] = Field(default_factory=list)

    @classmethod
    def from_domain(cls, deliverables: Deliverables) -> "DeliverablesOut":
        def findings(items) -> list[FindingOut]:
            return [
                FindingOut(
                    id=f.id,
                    severity=f.severity.value,
                    title=f.title,
                    detail=f.detail,
                    source=f.source.value,
                    file=f.file,
                    line=f.line,
                    url=f.url,
                    suggestion=f.suggestion,
                    safeguard=f.safeguard.value if f.safeguard else None,
                )
                for f in items
            ]

        code = deliverables.code
        tests = deliverables.tests
        kiuwan = deliverables.kiuwan
        sql = deliverables.sql
        uiux = deliverables.uiux
        privacy = deliverables.privacy
        vtr = deliverables.vtr
        verdict = deliverables.verdict

        return cls(
            code=(
                CodeReportOut(
                    summary=code.summary,
                    stack=code.stack,
                    change_map=[
                        ChangeMapEntryOut(
                            file=e.file,
                            change=e.change,
                            added=e.added,
                            removed=e.removed,
                            symbols=list(e.symbols),
                            criteria=list(e.criteria),
                        )
                        for e in code.change_map
                    ],
                    findings=findings(code.findings),
                )
                if code
                else None
            ),
            tests=(
                TestsReportOut(
                    framework=tests.framework,
                    command=tests.command,
                    tests=[
                        GeneratedTestOut(
                            name=t.name,
                            file=t.file,
                            status=t.status,
                            kind=t.kind,
                            criterion=t.criterion,
                            duration_ms=t.duration_ms,
                            code=t.code,
                            failure_reason=t.failure_reason,
                        )
                        for t in tests.tests
                    ],
                    coverage=tests.coverage,
                    findings=findings(tests.findings),
                )
                if tests
                else None
            ),
            kiuwan=(
                KiuwanReportOut(
                    file_name=kiuwan.file_name,
                    rows=kiuwan.rows,
                    defects=[
                        KiuwanDefectOut(
                            rule_id=d.rule_id,
                            severity=d.severity.value,
                            file=d.file,
                            rule=d.rule,
                            category=d.category,
                            line=d.line,
                            false_positive=d.false_positive,
                            note=d.note,
                        )
                        for d in kiuwan.defects
                    ],
                    findings=findings(kiuwan.findings),
                )
                if kiuwan
                else None
            ),
            sql=(
                SqlReportOut(
                    engine=sql.engine,
                    scripts=[
                        SqlScriptOut(file=s.file, statements=s.statements, kind=s.kind)
                        for s in sql.scripts
                    ],
                    findings=findings(sql.findings),
                )
                if sql
                else None
            ),
            uiux=(
                UiuxReportOut(
                    base_url=uiux.base_url,
                    scenarios=[
                        UiScenarioOut(
                            name=s.name,
                            status=s.status,
                            browser=s.browser,
                            duration_ms=s.duration_ms,
                            steps=list(s.steps),
                            a11y_issues=s.a11y_issues,
                            failure_reason=s.failure_reason,
                        )
                        for s in uiux.scenarios
                    ],
                    findings=findings(uiux.findings),
                )
                if uiux
                else None
            ),
            privacy=(
                PrivacyReportOut(
                    detections=[
                        PhiDetectionOut(
                            identifier=d.identifier,
                            file=d.file,
                            where=d.where,
                            line=d.line,
                            masked=d.masked,
                            url=d.url,
                        )
                        for d in privacy.detections
                    ],
                    safeguards=[
                        SafeguardCheckOut(id=s.id.value, status=s.status, evidence=s.evidence)
                        for s in privacy.safeguards
                    ],
                    minimum_necessary=privacy.minimum_necessary,
                    findings=findings(privacy.findings),
                )
                if privacy
                else None
            ),
            vtr=(
                VtrReportOut(
                    template_name=vtr.template_name,
                    output_name=vtr.output_name,
                    sections=[
                        VtrSectionOut(
                            title=s.title,
                            status=s.status,
                            content=s.content,
                            sources=[a.value for a in s.sources],
                        )
                        for s in vtr.sections
                    ],
                )
                if vtr
                else None
            ),
            verdict=(
                VerdictReportOut(
                    verdict=verdict.verdict.value,
                    confidence=verdict.confidence,
                    rationale=verdict.rationale,
                    guardrails=list(verdict.guardrails),
                )
                if verdict
                else None
            ),
            missing={agent.value: reason for agent, reason in deliverables.missing.items()},
            findings=findings(deliverables.findings),
        )


class RunDetailOut(Schema):
    run: RunOut
    deliverables: DeliverablesOut
    events: list[TraceEventOut] | None = None


class AgentDefinitionOut(Schema):
    id: str
    label: str
    short: str
    role: str
    optional: bool
    depends_on: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    #: Esquema JSON de la salida. **No editable**: de él dependen los guardarraíles.
    output_schema: dict[str, Any]
    requires_attachment: str | None = None
    processes_phi: bool = True


class AgentCatalogOut(Schema):
    order: list[str]
    all: list[str]
    agents: dict[str, AgentDefinitionOut]


class ModelInfoOut(Schema):
    id: str
    label: str
    in_per_m: float
    out_per_m: float


class ProviderCatalogOut(Schema):
    #: `null` = no aplica (mock). `false` = sin BAA: no puede procesar PHI.
    baa: bool | None = None
    models: list[ModelInfoOut] = Field(default_factory=list)


class ModelCatalogOut(Schema):
    providers: dict[str, ProviderCatalogOut]


class PromptVersionOut(Schema):
    version: int
    saved_at: datetime
    author: str
    note: str
    system_prompt: str
    task_prompt: str


class AgentProfileOut(Schema):
    agent_id: str
    provider: str
    model: str
    system_prompt: str
    task_prompt: str
    temperature: float
    max_steps: int
    prompt_version: int
    versions: list[PromptVersionOut] = Field(default_factory=list)

    @classmethod
    def from_domain(cls, profile: AgentProfile) -> "AgentProfileOut":
        return cls(
            agent_id=profile.agent_id.value,
            provider=profile.provider.value,
            model=profile.model,
            system_prompt=profile.system_prompt,
            task_prompt=profile.task_prompt,
            temperature=profile.temperature,
            max_steps=profile.max_steps,
            prompt_version=profile.prompt_version,
            versions=[
                PromptVersionOut(
                    version=v.version,
                    saved_at=v.saved_at,
                    author=v.author,
                    note=v.note,
                    system_prompt=v.system_prompt,
                    task_prompt=v.task_prompt,
                )
                for v in profile.versions
            ],
        )


class AuditEntryOut(Schema):
    seq: int
    at: datetime
    actor: str
    action: str
    target: str
    detail: str = ""
    prev_hash: str
    hash: str

    @classmethod
    def from_domain(cls, entry: AuditEntry) -> "AuditEntryOut":
        return cls(
            seq=entry.seq,
            at=entry.at,
            actor=entry.actor,
            action=entry.action.value,
            target=entry.target,
            detail=entry.detail,
            prev_hash=entry.prev_hash,
            hash=entry.hash,
        )


class AuditVerificationOut(Schema):
    entries: int
    valid: bool
    broken_at: int | None = None


class HealthOut(Schema):
    status: str
    version: str
    database: str
    config: dict[str, Any]


class SecretOut(Schema):
    """Un secreto, tal y como se puede enseñar.

    **No tiene campo para el valor, y es deliberado**: se construye desde `SecretMetadata`, que
    tampoco lo tiene, así que ninguna ruta puede devolverlo por descuido. `hint` son los cuatro
    últimos caracteres, lo justo para distinguir dos tokens sin reconstruir ninguno.
    """

    id: str
    kind: str
    kind_label: str
    name: str
    scope: str
    status: str
    hint: str = ""
    username: str = ""
    created_by: str
    created_at: datetime
    updated_at: datetime
    expires_at: datetime | None = None
    revoked_at: datetime | None = None
    revoked_by: str = ""
    last_used_at: datetime | None = None
    uses: int = 0

    @classmethod
    def from_domain(cls, secret: SecretMetadata, *, now: datetime) -> "SecretOut":
        return cls(
            id=secret.id,
            kind=secret.kind.value,
            kind_label=KIND_LABELS.get(secret.kind, secret.kind.value),
            name=secret.name,
            scope=secret.scope,
            status=secret.status(now),
            hint=secret.hint,
            username=secret.username,
            created_by=secret.created_by,
            created_at=secret.created_at,
            updated_at=secret.updated_at,
            expires_at=secret.expires_at,
            revoked_at=secret.revoked_at,
            revoked_by=secret.revoked_by,
            last_used_at=secret.last_used_at,
            uses=secret.uses,
        )


class UserOut(Schema):
    """Una persona. **Sin contraseña ni hash**: `User` del dominio tampoco los tiene."""

    id: str
    email: str
    name: str
    initials: str
    role: str
    role_label: str
    provider: str
    active: bool
    permissions: list[str]
    created_at: datetime
    last_login_at: datetime | None = None
    must_change_password: bool = False
    locked: bool = False

    @classmethod
    def from_domain(cls, user: User, *, now: datetime | None = None) -> "UserOut":
        momento = now or datetime.now(timezone.utc)
        return cls(
            id=user.id,
            email=user.email,
            name=user.name,
            initials=user.initials,
            role=user.role.value,
            role_label=ROLE_LABELS.get(user.role, user.role.value),
            provider=user.provider.value,
            active=user.active,
            permissions=sorted(p.value for p in user.permissions),
            created_at=user.created_at,
            last_login_at=user.last_login_at,
            must_change_password=user.must_change_password,
            locked=user.is_locked(momento),
        )


def agent_key(agent_id: AgentId) -> str:
    return agent_id.value
