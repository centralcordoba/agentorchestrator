"""Registro de agentes: definición, dependencias, herramientas y esquema de salida."""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping

from .enums import AgentId, AttachmentKind

AGENT_ORDER: tuple[AgentId, ...] = (
    AgentId.ORCHESTRATOR,
    AgentId.CODE,
    AgentId.TESTS,
    AgentId.KIUWAN,
    AgentId.SQL,
    AgentId.UIUX,
    AgentId.PRIVACY,
    AgentId.VTR,
    AgentId.VERDICT,
)

ALL_AGENTS: tuple[AgentId, ...] = AGENT_ORDER + (AgentId.CHAT,)

# El orden de ejecución se deriva de `depends_on` en `domain/orchestration.py`.


def _schema(properties: Mapping[str, Any], required: tuple[str, ...]) -> Mapping[str, Any]:
    """Esquema JSON de objeto cerrado, en solo lectura."""
    return MappingProxyType(
        {
            "type": "object",
            "properties": MappingProxyType(dict(properties)),
            "required": list(required),
            "additionalProperties": False,
        }
    )


_FINDINGS_SCHEMA: Mapping[str, Any] = MappingProxyType(
    {
        "type": "array",
        "items": {
            "type": "object",
            "properties": {
                "severity": {"enum": ["critica", "alta", "media", "baja", "info"]},
                "title": {"type": "string"},
                "detail": {"type": "string"},
                "file": {"type": "string"},
                "line": {"type": "integer"},
                "suggestion": {"type": "string"},
                "safeguard": {"enum": ["acceso", "auditoria", "integridad", "autenticacion", "transmision"]},
            },
            "required": ["severity", "title", "detail"],
            "additionalProperties": False,
        },
    }
)


@dataclass(frozen=True, slots=True)
class AgentDefinition:
    """Lo que un agente es. Inmutable y fuera del alcance del control de cambios de prompts."""

    id: AgentId
    label: str
    short: str
    role: str
    optional: bool
    depends_on: tuple[AgentId, ...]
    tools: tuple[str, ...]
    output_schema: Mapping[str, Any]
    requires_attachment: AttachmentKind | None = None
    processes_phi: bool = True

    def allows_tool(self, tool: str) -> bool:
        return tool in self.tools


_DEFINITIONS: tuple[AgentDefinition, ...] = (
    AgentDefinition(
        id=AgentId.ORCHESTRATOR,
        label="Orquestador",
        short="ORQ",
        role="Interpreta el requerimiento, sugiere qué agentes usar y coordina la ejecución.",
        optional=False,
        depends_on=(),
        tools=("list_attachments", "detect_file_types", "plan_stages"),
        output_schema=_schema(
            {
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "agent": {"enum": [a.value for a in AGENT_ORDER]},
                            "suggested": {"type": "boolean"},
                            "reason": {"type": "string"},
                        },
                        "required": ["agent", "suggested", "reason"],
                        "additionalProperties": False,
                    },
                }
            },
            ("items",),
        ),
        processes_phi=False,
    ),
    AgentDefinition(
        id=AgentId.CODE,
        label="Código",
        short="COD",
        role="Revisa el diff del repositorio contra el requerimiento y produce el mapa del cambio.",
        optional=True,
        depends_on=(),
        tools=("git_diff", "list_files", "read_file", "search_code"),
        output_schema=_schema(
            {
                "summary": {"type": "string"},
                "stack": {"type": "string"},
                "change_map": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "file": {"type": "string"},
                            "change": {"enum": ["nuevo", "modificado", "eliminado"]},
                            "added": {"type": "integer"},
                            "removed": {"type": "integer"},
                            "symbols": {"type": "array", "items": {"type": "string"}},
                            "criteria": {"type": "array", "items": {"type": "integer"}},
                        },
                        "required": ["file", "change"],
                        "additionalProperties": False,
                    },
                },
                "findings": _FINDINGS_SCHEMA,
            },
            ("summary", "change_map", "findings"),
        ),
        requires_attachment=AttachmentKind.REPO,
    ),
    AgentDefinition(
        id=AgentId.TESTS,
        label="Tests",
        short="TST",
        role="Genera pruebas pequeñas a partir del mapa del cambio y de los criterios, y las ejecuta.",
        optional=True,
        depends_on=(AgentId.CODE,),
        tools=("read_change_map", "read_file", "write_test", "run_tests"),
        output_schema=_schema(
            {
                "framework": {"type": "string"},
                "command": {"type": "string"},
                "tests": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "file": {"type": "string"},
                            "kind": {"enum": ["unitario", "integracion"]},
                            "criterion": {"type": "integer"},
                            "status": {"enum": ["paso", "fallo"]},
                            "duration_ms": {"type": "integer"},
                            "code": {"type": "string"},
                            "failure_reason": {"type": "string"},
                        },
                        "required": ["name", "file", "status"],
                        "additionalProperties": False,
                    },
                },
                "coverage": {"type": "number"},
                "findings": _FINDINGS_SCHEMA,
            },
            ("framework", "tests", "findings"),
        ),
        requires_attachment=AttachmentKind.REPO,
    ),
    AgentDefinition(
        id=AgentId.KIUWAN,
        label="Kiuwan",
        short="KIU",
        role="Analiza el CSV de Kiuwan adjunto, prioriza defectos y detecta falsos positivos.",
        optional=True,
        depends_on=(AgentId.CODE,),
        tools=("parse_kiuwan_csv", "group_defects", "ask_code_agent"),
        output_schema=_schema(
            {
                "file_name": {"type": "string"},
                "rows": {"type": "integer"},
                "defects": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "rule_id": {"type": "string"},
                            "rule": {"type": "string"},
                            "severity": {"enum": ["critica", "alta", "media", "baja", "info"]},
                            "category": {"type": "string"},
                            "file": {"type": "string"},
                            "line": {"type": "integer"},
                            "false_positive": {"type": "boolean"},
                            "note": {"type": "string"},
                        },
                        "required": ["rule_id", "severity", "file"],
                        "additionalProperties": False,
                    },
                },
                "findings": _FINDINGS_SCHEMA,
            },
            ("defects", "findings"),
        ),
        requires_attachment=AttachmentKind.KIUWAN_CSV,
    ),
    AgentDefinition(
        id=AgentId.SQL,
        label="SQL",
        short="SQL",
        role="Revisa scripts y consultas: rendimiento, seguridad y reversibilidad.",
        optional=True,
        depends_on=(AgentId.CODE,),
        tools=("parse_sql", "lint_sql", "explain_plan_hint"),
        output_schema=_schema(
            {
                "engine": {"type": "string"},
                "scripts": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "file": {"type": "string"},
                            "statements": {"type": "integer"},
                            "kind": {"type": "string"},
                        },
                        "required": ["file"],
                        "additionalProperties": False,
                    },
                },
                "findings": _FINDINGS_SCHEMA,
            },
            ("scripts", "findings"),
        ),
    ),
    AgentDefinition(
        id=AgentId.UIUX,
        label="UI/UX",
        short="UIX",
        role="Diseña y ejecuta escenarios Playwright sobre las pantallas afectadas.",
        optional=True,
        depends_on=(AgentId.CODE,),
        tools=("playwright_run", "axe_scan", "screenshot"),
        output_schema=_schema(
            {
                "base_url": {"type": "string"},
                "scenarios": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "browser": {"type": "string"},
                            "status": {"enum": ["paso", "fallo"]},
                            "duration_ms": {"type": "integer"},
                            "steps": {"type": "array", "items": {"type": "string"}},
                            "a11y_issues": {"type": "integer"},
                            "failure_reason": {"type": "string"},
                        },
                        "required": ["name", "status"],
                        "additionalProperties": False,
                    },
                },
                "findings": _FINDINGS_SCHEMA,
            },
            ("scenarios", "findings"),
        ),
    ),
    AgentDefinition(
        id=AgentId.PRIVACY,
        label="Privacidad HIPAA",
        short="PHI",
        role=(
            "Busca PHI en código, datos de prueba, logs y SQL, y evalúa las salvaguardas "
            "técnicas de 45 CFR 164.312 que toca el cambio."
        ),
        optional=True,
        depends_on=(AgentId.CODE,),
        tools=("scan_phi_identifiers", "map_hipaa_safeguards", "check_minimum_necessary"),
        output_schema=_schema(
            {
                "detections": {
                    "type": "array",
                    "items": {
                        # Nunca el valor del identificador: solo tipo, archivo y línea.
                        "type": "object",
                        "properties": {
                            "identifier": {"type": "string"},
                            "file": {"type": "string"},
                            "line": {"type": "integer"},
                            "where": {
                                "enum": ["datos_prueba", "log", "sql", "codigo", "url", "almacenamiento_local"]
                            },
                            "masked": {"type": "string"},
                        },
                        "required": ["identifier", "file", "where"],
                        "additionalProperties": False,
                    },
                },
                "safeguards": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"enum": ["acceso", "auditoria", "integridad", "autenticacion", "transmision"]},
                            "status": {"enum": ["cumple", "riesgo", "sin_evidencia", "no_aplica"]},
                            "evidence": {"type": "string"},
                        },
                        "required": ["id", "status", "evidence"],
                        "additionalProperties": False,
                    },
                },
                "minimum_necessary": {"type": "string"},
                "findings": _FINDINGS_SCHEMA,
            },
            ("detections", "safeguards", "findings"),
        ),
    ),
    AgentDefinition(
        id=AgentId.VTR,
        label="VTR",
        short="VTR",
        role="Genera el documento VTR a partir de la plantilla modelo y de lo producido por los demás.",
        optional=True,
        depends_on=(AgentId.CODE, AgentId.TESTS),
        tools=("read_vtr_template", "fill_section", "render_docx"),
        output_schema=_schema(
            {
                "template_name": {"type": "string"},
                "output_name": {"type": "string"},
                "sections": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "status": {"enum": ["completa", "parcial", "vacia"]},
                            "content": {"type": "string"},
                            "sources": {"type": "array", "items": {"type": "string"}},
                        },
                        "required": ["title", "status", "content"],
                        "additionalProperties": False,
                    },
                },
            },
            ("sections",),
        ),
        requires_attachment=AttachmentKind.VTR_TEMPLATE,
    ),
    AgentDefinition(
        id=AgentId.VERDICT,
        label="Dictamen",
        short="DIC",
        role="Consolida hallazgos, elimina duplicados, aplica umbrales y emite el dictamen final.",
        optional=False,
        depends_on=(),
        tools=("dedupe_findings", "count_by_severity", "apply_thresholds"),
        output_schema=_schema(
            {
                "verdict": {"enum": ["APROBADO", "APROBADO_CON_OBSERVACIONES", "RECHAZADO"]},
                "confidence": {"type": "number"},
                "rationale": {"type": "string"},
                "guardrails": {"type": "array", "items": {"type": "string"}},
            },
            ("verdict", "confidence", "rationale"),
        ),
        processes_phi=False,
    ),
    AgentDefinition(
        id=AgentId.CHAT,
        label="Asistente de consulta",
        short="CHAT",
        role="Responde preguntas sobre una revisión ya ejecutada citando la evidencia. Solo lee.",
        optional=True,
        depends_on=(),
        # Solo herramientas de lectura: el asistente no firma ni aprueba (ORQ-27).
        tools=("get_findings", "get_trace", "get_diff_file", "get_vtr_section"),
        output_schema=_schema(
            {
                "answer": {"type": "string"},
                "citations": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "kind": {"type": "string"},
                            "label": {"type": "string"},
                            "ref": {"type": "string"},
                        },
                        "required": ["label"],
                        "additionalProperties": False,
                    },
                },
                "fallback": {"type": "boolean"},
            },
            ("answer", "citations"),
        ),
    ),
)

AGENTS: Mapping[AgentId, AgentDefinition] = MappingProxyType({d.id: d for d in _DEFINITIONS})

PLANNABLE: tuple[AgentId, ...] = tuple(a for a in AGENT_ORDER if AGENTS[a].optional)


def definition(agent_id: AgentId) -> AgentDefinition:
    return AGENTS[agent_id]
