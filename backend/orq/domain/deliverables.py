"""Entregables: un informe por agente más el dictamen."""
from __future__ import annotations

from dataclasses import dataclass, field

from .enums import AgentId, SafeguardId, Severity, Verdict
from .findings import ChangeMapEntry, Finding


@dataclass(frozen=True, slots=True)
class CodeReport:
    summary: str
    stack: str = ""
    change_map: tuple[ChangeMapEntry, ...] = ()
    findings: tuple[Finding, ...] = ()


@dataclass(frozen=True, slots=True)
class GeneratedTest:
    name: str
    file: str
    status: str  # "paso" | "fallo"
    kind: str = "unitario"
    criterion: int | None = None
    duration_ms: int = 0
    code: str = ""
    failure_reason: str = ""


@dataclass(frozen=True, slots=True)
class TestsReport:
    framework: str
    command: str = ""
    tests: tuple[GeneratedTest, ...] = ()
    coverage: float = 0.0
    findings: tuple[Finding, ...] = ()

    @property
    def failed(self) -> tuple[GeneratedTest, ...]:
        return tuple(t for t in self.tests if t.status == "fallo")


@dataclass(frozen=True, slots=True)
class KiuwanDefect:
    rule_id: str
    severity: Severity
    file: str
    rule: str = ""
    category: str = ""
    line: int | None = None
    false_positive: bool = False
    note: str = ""


@dataclass(frozen=True, slots=True)
class KiuwanReport:
    file_name: str = ""
    rows: int = 0
    defects: tuple[KiuwanDefect, ...] = ()
    findings: tuple[Finding, ...] = ()


@dataclass(frozen=True, slots=True)
class SqlScript:
    file: str
    statements: int = 0
    kind: str = ""


@dataclass(frozen=True, slots=True)
class SqlReport:
    engine: str = ""
    scripts: tuple[SqlScript, ...] = ()
    findings: tuple[Finding, ...] = ()


@dataclass(frozen=True, slots=True)
class UiScenario:
    name: str
    status: str  # "paso" | "fallo"
    browser: str = ""
    duration_ms: int = 0
    steps: tuple[str, ...] = ()
    a11y_issues: int = 0
    failure_reason: str = ""


@dataclass(frozen=True, slots=True)
class UiuxReport:
    base_url: str = ""
    scenarios: tuple[UiScenario, ...] = ()
    findings: tuple[Finding, ...] = ()


@dataclass(frozen=True, slots=True)
class PhiDetection:
    """Detección de PHI. `masked` nunca contiene el valor real del identificador."""

    identifier: str
    file: str
    where: str
    line: int | None = None
    masked: str = ""
    url: str = ""


@dataclass(frozen=True, slots=True)
class SafeguardCheck:
    id: SafeguardId
    status: str  # "cumple" | "riesgo" | "sin_evidencia" | "no_aplica"
    evidence: str = ""


@dataclass(frozen=True, slots=True)
class PrivacyReport:
    detections: tuple[PhiDetection, ...] = ()
    safeguards: tuple[SafeguardCheck, ...] = ()
    minimum_necessary: str = ""
    findings: tuple[Finding, ...] = ()


@dataclass(frozen=True, slots=True)
class VtrSection:
    title: str
    status: str  # "completa" | "parcial" | "vacia"
    content: str = ""
    sources: tuple[AgentId, ...] = ()


@dataclass(frozen=True, slots=True)
class VtrReport:
    template_name: str = ""
    output_name: str = ""
    sections: tuple[VtrSection, ...] = ()


@dataclass(frozen=True, slots=True)
class VerdictReport:
    verdict: Verdict
    confidence: float
    rationale: str
    guardrails: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Deliverables:
    """Lo producido por una ejecución. `None` = el agente no se ejecutó."""

    code: CodeReport | None = None
    tests: TestsReport | None = None
    kiuwan: KiuwanReport | None = None
    sql: SqlReport | None = None
    uiux: UiuxReport | None = None
    privacy: PrivacyReport | None = None
    vtr: VtrReport | None = None
    verdict: VerdictReport | None = None
    #: Agentes que no llegaron a producir informe, con el motivo.
    missing: dict[AgentId, str] = field(default_factory=dict)

    @property
    def findings(self) -> tuple[Finding, ...]:
        reports = (self.code, self.tests, self.kiuwan, self.sql, self.uiux, self.privacy)
        return tuple(f for report in reports if report is not None for f in report.findings)
