"""Hallazgos y mapa del cambio: el vocabulario común entre agentes."""
from __future__ import annotations

from dataclasses import dataclass

from .enums import AgentId, SafeguardId, Severity

#: Orden de gravedad, de más a menos. Lo usan el dictamen y los recuentos.
SEVERITY_ORDER: tuple[Severity, ...] = (
    Severity.CRITICA,
    Severity.ALTA,
    Severity.MEDIA,
    Severity.BAJA,
    Severity.INFO,
)


@dataclass(frozen=True, slots=True)
class Finding:
    """Un hallazgo. Si apunta a código, `file` y `line` deben existir en el `head_sha`."""

    id: str
    severity: Severity
    title: str
    detail: str
    source: AgentId
    file: str = ""
    line: int | None = None
    url: str = ""
    suggestion: str = ""
    #: Salvaguarda técnica de HIPAA afectada (solo agente de Privacidad).
    safeguard: SafeguardId | None = None

    @property
    def rank(self) -> int:
        return SEVERITY_ORDER.index(self.severity)


@dataclass(frozen=True, slots=True)
class ChangeMapEntry:
    file: str
    change: str  # "nuevo" | "modificado" | "eliminado"
    added: int = 0
    removed: int = 0
    symbols: tuple[str, ...] = ()
    #: Índices de los criterios de aceptación que cubre el archivo.
    criteria: tuple[int, ...] = ()


def count_by_severity(findings: tuple[Finding, ...]) -> dict[Severity, int]:
    counts = {severity: 0 for severity in SEVERITY_ORDER}
    for finding in findings:
        counts[finding.severity] += 1
    return counts


def dedupe(findings: tuple[Finding, ...]) -> tuple[Finding, ...]:
    """Quita repetidos por (archivo, línea, título), conservando el más grave."""
    best: dict[tuple[str, int | None, str], Finding] = {}
    for finding in findings:
        key = (finding.file, finding.line, finding.title.strip().lower())
        current = best.get(key)
        if current is None or finding.rank < current.rank:
            best[key] = finding
    return tuple(sorted(best.values(), key=lambda f: (f.rank, f.file, f.line or 0)))
