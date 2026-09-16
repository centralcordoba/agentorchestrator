"""Reglas deterministas sobre el diff: lo que se puede afirmar sin preguntar a un modelo."""
from __future__ import annotations

import re
from dataclasses import dataclass

from .diff import FileDiff, added_lines
from .enums import AgentId, FileStatus, Severity
from .findings import Finding


@dataclass(frozen=True, slots=True)
class CodeRule:
    id: str
    severity: Severity
    source: AgentId  # CODE o SQL: el dictamen los cuenta por separado
    title: str
    detail: str
    pattern: re.Pattern[str]
    #: Solo se aplica a archivos cuyo nombre encaja.
    only: re.Pattern[str] | None = None
    suggestion: str = ""


RULES: tuple[CodeRule, ...] = (
    CodeRule(
        "SEC-SECRET",
        Severity.CRITICA,
        AgentId.CODE,
        "Posible credencial escrita en el código",
        "Se añade un valor literal asignado a una variable con nombre de secreto.",
        re.compile(
            r"\b(?:password|passwd|pwd|secret|api[_-]?key|access[_-]?token|client[_-]?secret)\b"
            r"\s*[:=]\s*[\"'][^\"'\s]{8,}[\"']",
            re.IGNORECASE,
        ),
        suggestion="Mover el valor a variables de entorno o a un gestor de secretos.",
    ),
    CodeRule(
        "SEC-SQLCONCAT",
        Severity.ALTA,
        AgentId.CODE,
        "Consulta SQL construida concatenando texto",
        "La sentencia se arma uniendo cadenas con variables: riesgo de inyección SQL.",
        re.compile(
            r"\b(?:SELECT|INSERT|UPDATE|DELETE)\b[^;\n]*[\"'`]\s*\+\s*[\w.(]",
            re.IGNORECASE,
        ),
        suggestion="Usar consultas parametrizadas.",
    ),
    CodeRule(
        "SEC-EVAL",
        Severity.ALTA,
        AgentId.CODE,
        "Uso de eval",
        "eval ejecuta código arbitrario construido en tiempo de ejecución.",
        re.compile(r"(^|[^.\w])eval\s*\("),
        only=re.compile(r"\.(?:js|jsx|ts|tsx|py|php|rb)$", re.IGNORECASE),
    ),
    CodeRule(
        "REL-EMPTYCATCH",
        Severity.MEDIA,
        AgentId.CODE,
        "Bloque catch vacío",
        "El error se captura y se descarta sin registrarlo.",
        re.compile(r"catch\s*(?:\([^)]*\))?\s*\{\s*\}"),
        suggestion="Registrar el error o propagarlo.",
    ),
    CodeRule(
        "SQL-DELETE-NOWHERE",
        Severity.ALTA,
        AgentId.SQL,
        "DELETE sin WHERE",
        "Borra todas las filas de la tabla.",
        re.compile(r"\bDELETE\s+FROM\s+[\w.\"]+\s*;", re.IGNORECASE),
    ),
    CodeRule(
        "SQL-DROP",
        Severity.MEDIA,
        AgentId.SQL,
        "Sentencia DROP",
        "Operación destructiva: comprobar que existe script de rollback.",
        re.compile(r"\bDROP\s+(?:TABLE|COLUMN|INDEX|VIEW)\b", re.IGNORECASE),
    ),
    CodeRule(
        "SQL-SELECTSTAR",
        Severity.BAJA,
        AgentId.SQL,
        "SELECT *",
        "Traer todas las columnas complica el mantenimiento y puede degradar el rendimiento.",
        re.compile(r"\bSELECT\s+\*\s+FROM\b", re.IGNORECASE),
    ),
    CodeRule(
        "DBG-LOG",
        Severity.BAJA,
        AgentId.CODE,
        "Traza de depuración añadida",
        "Se añaden salidas por consola que suelen quedar olvidadas.",
        re.compile(r"\b(?:console\.log|System\.out\.println|var_dump|debugger;)"),
        only=re.compile(r"\.(?:js|jsx|ts|tsx|java|php|vue|svelte)$", re.IGNORECASE),
    ),
    CodeRule(
        "MNT-TODO",
        Severity.INFO,
        AgentId.CODE,
        "TODO/FIXME añadido",
        "Queda trabajo pendiente marcado en el código.",
        re.compile(r"\b(?:TODO|FIXME|HACK|XXX)\b"),
    ),
)

TEST_FILE = re.compile(
    r"(^|/)(?:test|tests|__tests__|spec)/|[._-](?:test|spec)\.[a-z]+$|Tests?\.(?:java|cs|kt)$",
    re.IGNORECASE,
)
MANIFEST = re.compile(
    r"(^|/)(?:package\.json|pom\.xml|build\.gradle(?:\.kts)?|requirements\.txt|pyproject\.toml"
    r"|go\.mod|Cargo\.toml|composer\.json|Gemfile|[\w.-]+\.csproj)$"
)
SOURCE = re.compile(
    r"\.(?:js|jsx|ts|tsx|java|kt|cs|py|go|rb|php|vue|svelte|scala|swift)$", re.IGNORECASE
)
SQL_FILE = re.compile(r"\.sql$", re.IGNORECASE)
SQL_WORDS = re.compile(r"\b(?:SELECT|DELETE|DROP)\b")

#: A partir de aquí un archivo es difícil de revisar con garantías.
BIG_CHANGE = 400


def analyze_diff(
    files: tuple[FileDiff, ...],
    *,
    blob_url: "BlobUrl | None" = None,
    criteria_count: int = 0,
) -> tuple[Finding, ...]:
    """Hallazgos deterministas del cambio. `blob_url` construye el enlace al proveedor."""
    findings: list[Finding] = []
    link = blob_url or (lambda path, line=None: "")
    seq = 0

    def nuevo(**kwargs: object) -> None:
        nonlocal seq
        seq += 1
        findings.append(Finding(id=f"R{seq}", **kwargs))  # type: ignore[arg-type]

    for file in files:
        if file.status is FileStatus.REMOVED:
            continue
        es_sql = bool(SQL_FILE.search(file.path))

        if file.has_patch:
            lineas = added_lines(file.patch)
            for rule in RULES:
                if rule.only is not None and not rule.only.search(file.path):
                    continue
                # Una regla de SQL fuera de un .sql solo aplica si el diff trae SQL de verdad.
                if rule.source is AgentId.SQL and not es_sql and not SQL_WORDS.search(file.patch):
                    continue
                hits = [l for l in lineas if rule.pattern.search(l.text)]
                if not hits:
                    continue
                extra = f" ({len(hits)} líneas en este archivo)" if len(hits) > 1 else ""
                nuevo(
                    severity=rule.severity,
                    source=rule.source,
                    title=rule.title,
                    detail=f"{rule.detail}{extra} Línea: «{hits[0].text.strip()[:120]}»",
                    file=file.path,
                    line=hits[0].line,
                    url=link(file.path, hits[0].line),
                    suggestion=rule.suggestion,
                )

        if file.size > BIG_CHANGE:
            nuevo(
                severity=Severity.MEDIA,
                source=AgentId.CODE,
                title="Cambio muy grande en un archivo",
                detail=f"+{file.additions} −{file.deletions} líneas: difícil de revisar con garantías.",
                file=file.path,
                url=link(file.path),
                suggestion="Dividir el cambio en commits o peticiones de fusión más pequeñas.",
            )
        elif not file.has_patch and SOURCE.search(file.path):
            nuevo(
                severity=Severity.INFO,
                source=AgentId.CODE,
                title="Diff no disponible",
                detail=(
                    "El archivo es binario o demasiado grande para el diff, así que no se analizó."
                    if file.binary
                    else "No hay diff de este archivo, así que no se analizó."
                ),
                file=file.path,
                url=link(file.path),
            )

    vivos = [f for f in files if f.status is not FileStatus.REMOVED]
    codigo = [f for f in vivos if SOURCE.search(f.path) and not TEST_FILE.search(f.path)]
    pruebas = [f for f in files if TEST_FILE.search(f.path)]
    if codigo and not pruebas:
        nuevo(
            severity=Severity.MEDIA,
            source=AgentId.CODE,
            title="Cambio de código sin pruebas",
            detail=(
                f"Se modifican {len(codigo)} archivo(s) de código y ningún archivo de pruebas."
            ),
            suggestion="Añadir o actualizar pruebas que cubran el cambio.",
        )

    manifiestos = [f for f in files if MANIFEST.search(f.path)]
    if manifiestos:
        nuevo(
            severity=Severity.INFO,
            source=AgentId.CODE,
            title="Dependencias modificadas",
            detail=(
                f"Cambian {', '.join(m.path for m in manifiestos)}: revisar licencias y "
                "vulnerabilidades de las nuevas versiones."
            ),
            file=manifiestos[0].path,
            url=link(manifiestos[0].path),
        )

    return tuple(findings)


class BlobUrl:
    """Construye el enlace a un archivo y línea del proveedor, fijado en el `head_sha`.

    Es una clase y no una función suelta para que quede explícito que el `head_sha` se fija una
    vez por ejecución: un enlace a `main` dejaría de señalar la línea revisada en cuanto alguien
    empujara otro commit.
    """

    #: Cómo construye cada proveedor la URL de un archivo en un commit.
    TEMPLATES: dict[str, str] = {
        "github": "{base}/blob/{sha}/{path}",
        "azure": "{base}?path=/{path}&version=GC{sha}",
        "gitlab": "{base}/-/blob/{sha}/{path}",
    }
    ANCHORS: dict[str, str] = {"github": "#L{line}", "azure": "&line={line}", "gitlab": "#L{line}"}

    def __init__(self, provider: str, html_url: str, head_sha: str) -> None:
        self._provider = provider if provider in self.TEMPLATES else ""
        self._base = html_url.rstrip("/")
        self._sha = head_sha

    def __call__(self, path: str, line: int | None = None) -> str:
        if not self._provider or not self._base or not self._sha:
            return ""
        url = self.TEMPLATES[self._provider].format(base=self._base, sha=self._sha, path=path)
        if line:
            url += self.ANCHORS[self._provider].format(line=line)
        return url
