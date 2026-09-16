"""Contenido de ejemplo para el proveedor `mock` en modo demo."""
from __future__ import annotations

import hashlib
from typing import Any

NOTE = "Ejemplo del proveedor simulado: no es un análisis real."

#: Archivos por tipo de cambio, para que Código, SQL, Tests y Kiuwan hablen de lo mismo.
FILES = [
    ("src/pagos/conciliacion.py", "modificado", 48, 12),
    ("src/pagos/vistas.py", "modificado", 21, 4),
    ("src/portal/pagos.tsx", "modificado", 63, 9),
    ("sql/2026_09_conciliacion.sql", "nuevo", 37, 0),
    ("tests/test_conciliacion.py", "nuevo", 54, 0),
]

SYMBOLS = {
    "src/pagos/conciliacion.py": ["conciliar_pago", "PagoFueraDeHorario"],
    "src/pagos/vistas.py": ["detalle_pago"],
    "src/portal/pagos.tsx": ["PagosTable", "EstadoChip"],
    "sql/2026_09_conciliacion.sql": ["idx_pagos_fecha"],
    "tests/test_conciliacion.py": ["test_pago_fuera_de_horario"],
}


def seed(text: str) -> int:
    """Número estable a partir del requerimiento: la misma demo da siempre lo mismo."""
    return int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:8], 16)


def pick(values: list[Any], text: str, offset: int = 0) -> Any:
    return values[(seed(text) + offset) % len(values)]


def change_map() -> list[dict[str, Any]]:
    return [
        {
            "file": path,
            "change": change,
            "added": added,
            "removed": removed,
            "symbols": SYMBOLS.get(path, []),
            "criteria": [0] if "conciliacion" in path else [],
        }
        for path, change, added, removed in FILES
    ]


def code_findings(text: str) -> list[dict[str, Any]]:
    todos = [
        {
            "severity": "alta",
            "title": "La conciliación no contempla el cambio de día",
            "detail": (
                "Al comparar la fecha del pago con la del cierre se usa la hora local sin zona; "
                f"un pago a las 23:58 se concilia al día siguiente. {NOTE}"
            ),
            "file": "src/pagos/conciliacion.py",
            "line": 88,
            "suggestion": "Comparar en UTC y guardar la zona con la que llegó el pago.",
        },
        {
            "severity": "media",
            "title": "Excepción capturada y descartada",
            "detail": f"El `except Exception: pass` esconde fallos de la pasarela. {NOTE}",
            "file": "src/pagos/vistas.py",
            "line": 41,
            "suggestion": "Registrar el error y devolver un estado de fallo explícito.",
        },
        {
            "severity": "baja",
            "title": "Nombre poco claro en la vista",
            "detail": f"`x1` se usa para el importe conciliado. {NOTE}",
            "file": "src/portal/pagos.tsx",
            "line": 132,
            "suggestion": "Renombrar a `importeConciliado`.",
        },
    ]
    return todos[: 2 + (seed(text) % 2)]


def tests_report(text: str) -> dict[str, Any]:
    falla = seed(text) % 3 == 0
    pruebas = [
        {
            "name": "test_pago_fuera_de_horario_se_concilia_el_mismo_dia",
            "file": "tests/test_conciliacion.py",
            "kind": "unitario",
            "criterion": 0,
            "status": "fallo" if falla else "paso",
            "duration_ms": 120,
            "code": "def test_pago_fuera_de_horario_se_concilia_el_mismo_dia(): ...",
            **(
                {"failure_reason": "esperaba 2026-09-15 y llegó 2026-09-16"}
                if falla
                else {}
            ),
        },
        {
            "name": "test_importe_conciliado_coincide_con_la_pasarela",
            "file": "tests/test_conciliacion.py",
            "kind": "unitario",
            "criterion": 1,
            "status": "paso",
            "duration_ms": 96,
            "code": "def test_importe_conciliado_coincide_con_la_pasarela(): ...",
        },
        {
            "name": "test_portal_muestra_el_estado",
            "file": "tests/test_portal_pagos.py",
            "kind": "integracion",
            "criterion": 1,
            "status": "paso",
            "duration_ms": 410,
            "code": "def test_portal_muestra_el_estado(): ...",
        },
    ]
    findings = (
        [
            {
                "severity": "alta",
                "title": "Una prueba del criterio 1 falla",
                "detail": f"El pago fuera de horario se concilia al día siguiente. {NOTE}",
                "file": "tests/test_conciliacion.py",
                "line": 18,
            }
        ]
        if falla
        else []
    )
    return {
        "framework": "pytest",
        "command": "pytest tests/ -q",
        "tests": pruebas,
        "coverage": 72 + (seed(text) % 15),
        "findings": findings,
    }


def kiuwan_report(text: str, file_name: str) -> dict[str, Any]:
    defectos = [
        {
            "rule_id": "OPT.PYTHON.SEC.HardcodedCredentials",
            "rule": "Credencial en el código",
            "severity": "critica",
            "category": "Seguridad",
            "file": "src/pagos/conciliacion.py",
            "line": 12,
            "false_positive": True,
            "note": f"Es una constante de prueba, confirmado con el agente de Código. {NOTE}",
        },
        {
            "rule_id": "OPT.PYTHON.ERR.BroadExcept",
            "rule": "Captura de excepción demasiado amplia",
            "severity": "media",
            "category": "Fiabilidad",
            "file": "src/pagos/vistas.py",
            "line": 41,
            "false_positive": False,
            "note": f"Coincide con un hallazgo del agente de Código. {NOTE}",
        },
        {
            "rule_id": "OPT.SQL.PERF.MissingIndex",
            "rule": "Consulta sin índice",
            "severity": "alta",
            "category": "Rendimiento",
            "file": "sql/2026_09_conciliacion.sql",
            "line": 24,
            "false_positive": False,
            "note": f"La tabla de pagos supera el millón de filas. {NOTE}",
        },
    ]
    return {
        "file_name": file_name,
        "rows": 1240,
        "defects": defectos,
        "findings": [
            {
                "severity": "alta",
                "title": "Consulta de conciliación sin índice",
                "detail": f"Kiuwan la marca y el script la introduce en este cambio. {NOTE}",
                "file": "sql/2026_09_conciliacion.sql",
                "line": 24,
            }
        ],
    }


def sql_report() -> dict[str, Any]:
    return {
        "engine": "PostgreSQL 16",
        "scripts": [
            {"file": "sql/2026_09_conciliacion.sql", "statements": 4, "kind": "migración"}
        ],
        "findings": [
            {
                "severity": "media",
                "title": "La migración no trae script de vuelta atrás",
                "detail": f"Si falla en producción no hay forma de revertirla. {NOTE}",
                "file": "sql/2026_09_conciliacion.sql",
                "line": 1,
                "suggestion": "Añadir el `DROP INDEX` correspondiente en un script de rollback.",
            }
        ],
    }


def uiux_report() -> dict[str, Any]:
    return {
        "base_url": "https://pre.portal-pacientes.local",
        "scenarios": [
            {
                "name": "Un pago fuera de horario aparece conciliado el mismo día",
                "browser": "chromium",
                "status": "paso",
                "duration_ms": 3820,
                "steps": [
                    "Entrar con un usuario administrativo",
                    "Abrir Pagos y filtrar por ayer",
                    "Comprobar el estado del pago de las 23:58",
                ],
                "a11y_issues": 0,
            },
            {
                "name": "El estado se entiende sin depender del color",
                "browser": "chromium",
                "status": "fallo",
                "duration_ms": 2110,
                "steps": ["Abrir Pagos", "Revisar la columna Estado con el simulador de daltonismo"],
                "a11y_issues": 2,
                "failure_reason": "El estado solo se distingue por color: falta icono o texto.",
            },
        ],
        "findings": [
            {
                "severity": "media",
                "title": "El estado del pago se distingue solo por color",
                "detail": f"Incumple WCAG 1.4.1 en la tabla de pagos. {NOTE}",
                "file": "src/portal/pagos.tsx",
                "line": 118,
                "suggestion": "Añadir icono y texto junto al color.",
            }
        ],
    }


def privacy_report(phi: str) -> dict[str, Any]:
    con_phi = phi != "no"
    detecciones = (
        [
            {
                "identifier": "historia_clinica",
                "file": "src/pagos/conciliacion.py",
                "line": 64,
                "where": "log",
                "masked": "***",
            },
            {
                "identifier": "nombre",
                "file": "tests/test_conciliacion.py",
                "line": 22,
                "where": "datos_prueba",
                "masked": "***",
            },
        ]
        if con_phi
        else []
    )
    salvaguardas = [
        ("acceso", "cumple" if con_phi else "no_aplica", "El endpoint exige rol administrativo."),
        ("auditoria", "riesgo" if con_phi else "no_aplica", "La consulta de pagos no deja registro de quién la hizo."),
        ("integridad", "cumple", "La migración conserva la clave primaria."),
        ("autenticacion", "cumple", "Sesión con doble factor en el portal."),
        ("transmision", "sin_evidencia", "No se pudo comprobar el TLS del servicio interno."),
    ]
    findings = (
        [
            {
                "severity": "critica",
                "title": "Identificador de paciente escrito en el log",
                "detail": f"La traza de conciliación registra el número de historia. {NOTE}",
                "file": "src/pagos/conciliacion.py",
                "line": 64,
                "safeguard": "auditoria",
                "suggestion": "Registrar solo el identificador interno del pago.",
            }
        ]
        if con_phi
        else []
    )
    return {
        "detections": detecciones,
        "safeguards": [
            {"id": i, "status": s, "evidence": f"{e} {NOTE}"} for i, s, e in salvaguardas
        ],
        "minimum_necessary": (
            f"La vista devuelve el nombre completo cuando bastaría el identificador. {NOTE}"
            if con_phi
            else f"El cambio no maneja datos de paciente. {NOTE}"
        ),
        "findings": findings,
    }


def vtr_report(template: str, sources: list[str]) -> dict[str, Any]:
    secciones = [
        ("1. Objeto del cambio", "completa", "Corregir la conciliación de pagos fuera de horario y reflejar el estado real en el portal."),
        ("2. Alcance técnico", "completa", "5 archivos modificados: lógica de conciliación, vista del portal y una migración de base de datos."),
        ("3. Pruebas realizadas", "completa", "3 pruebas automáticas sobre los criterios de aceptación."),
        ("4. Análisis de calidad", "completa", "3 defectos de Kiuwan, uno descartado como falso positivo."),
        ("5. Privacidad y cumplimiento", "parcial", "Se detectó un identificador de paciente en un log; la salvaguarda de transmisión quedó sin evidencia."),
        ("6. Riesgos y plan de vuelta atrás", "parcial", "La migración no trae script de rollback."),
    ]
    return {
        "template_name": template or "VTR-modelo-v3.docx",
        "output_name": "VTR-REQ-conciliacion-pagos.docx",
        "sections": [
            {"title": t, "status": s, "content": f"{c} {NOTE}", "sources": sources[:3]}
            for t, s, c in secciones
        ],
    }
