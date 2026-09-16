"""Sugerencia de plan y avisos previos a la ejecución."""
from __future__ import annotations

import re
from dataclasses import replace
from datetime import datetime

from .agents import AGENTS, PLANNABLE
from .enums import AgentId, AttachmentKind, FileStatus, PhiClassification, WarningLevel
from .plan import Plan, PlanItem, PlanWarning
from .requirement import Requirement

UI_WORDS = ("pantalla", "formulario", "portal", "web", "interfaz", "botón", "vista", "frontend", "ui")
SQL_WORDS = ("base de datos", "tabla", "consulta", "sql", "migración", "reporte", "índice", "procedimiento")

SQL_FILE = re.compile(r"\.sql$", re.IGNORECASE)
FRONTEND_FILE = re.compile(r"\.(tsx|jsx|vue|svelte|html|css|scss|less)$", re.IGNORECASE)

ATTACHMENT_LABELS: dict[AttachmentKind, str] = {
    AttachmentKind.REPO: "Repositorio git",
    AttachmentKind.VTR_TEMPLATE: "Plantilla VTR",
    AttachmentKind.KIUWAN_CSV: "CSV Kiuwan",
    AttachmentKind.SQL: "Script SQL",
}

# Límite de palabra propio: \b no entiende las tildes del español.
_EDGES = "a-záéíóúüñ"


def _mentions(requirement: Requirement, words: tuple[str, ...]) -> str | None:
    text = " ".join(
        (requirement.title, requirement.description, " ".join(requirement.acceptance_criteria))
    ).lower()
    for word in words:
        if re.search(rf"(^|[^{_EDGES}]){re.escape(word)}($|[^{_EDGES}])", text):
            return word
    return None


def _changed_files(requirement: Requirement, pattern: re.Pattern[str]) -> list[str]:
    repo = requirement.repo
    if repo is None:
        return []
    return [f.path for f in repo.files if pattern.search(f.path) and f.status is not FileStatus.REMOVED]


def suggest_plan(requirement: Requirement, *, now: datetime) -> Plan:
    """Propone qué agentes intervienen. Todo lo propuesto queda activado y es revisable."""
    items: list[PlanItem] = []
    for agent_id in PLANNABLE:
        suggested, reason = _suggest(requirement, agent_id)
        items.append(PlanItem(agent_id=agent_id, suggested=suggested, enabled=suggested, reason=reason))
    return Plan(items=tuple(items), suggested_at=now)


def _suggest(requirement: Requirement, agent_id: AgentId) -> tuple[bool, str]:
    has_repo = requirement.has_attachment(AttachmentKind.REPO)
    repo = requirement.repo

    if agent_id is AgentId.CODE:
        if not has_repo:
            return False, "No hay repositorio adjunto."
        if repo is not None:
            return True, f"Repositorio conectado: {len(repo.files)} archivo(s) cambiados en {repo.range_label or repo.branch}."
        return True, "Hay un repositorio con rama adjunta: se revisa el diff."

    if agent_id is AgentId.TESTS:
        if not has_repo:
            return False, "Sin repositorio no hay código que probar."
        return True, "Hay código nuevo: se generarán y ejecutarán pruebas locales."

    if agent_id is AgentId.KIUWAN:
        if requirement.has_attachment(AttachmentKind.KIUWAN_CSV):
            return True, "Se adjuntó un CSV de Kiuwan."
        return False, "No se adjuntó el CSV de Kiuwan."

    if agent_id is AgentId.SQL:
        sql_files = _changed_files(requirement, SQL_FILE)
        if sql_files:
            return True, f"El diff incluye {len(sql_files)} script(s) SQL: {', '.join(sql_files[:2])}."
        if requirement.has_attachment(AttachmentKind.SQL):
            return True, "Se adjuntaron scripts SQL."
        word = _mentions(requirement, SQL_WORDS)
        if word:
            return True, f"El requerimiento menciona «{word}»: probablemente hay consultas."
        return False, "No hay scripts SQL ni menciones a base de datos."

    if agent_id is AgentId.UIUX:
        ui_files = _changed_files(requirement, FRONTEND_FILE)
        if ui_files:
            return True, f"El diff modifica {len(ui_files)} archivo(s) de interfaz: {', '.join(ui_files[:2])}."
        word = _mentions(requirement, UI_WORDS)
        if repo is not None and not word:
            return False, "El diff no toca archivos de interfaz y el requerimiento no menciona pantallas."
        if word:
            return True, f"El requerimiento menciona «{word}»: se probarán las pantallas con Playwright."
        return False, "El requerimiento no menciona pantallas."

    if agent_id is AgentId.PRIVACY:
        if requirement.phi is PhiClassification.SI:
            return True, "Obligatorio: el requerimiento está clasificado con PHI."
        if requirement.phi is PhiClassification.DESCONOCIDO:
            return True, "Obligatorio mientras no se confirme que el requerimiento no toca PHI."
        return False, "Clasificado sin PHI."

    if agent_id is AgentId.VTR:
        if requirement.has_attachment(AttachmentKind.VTR_TEMPLATE):
            return True, "Hay plantilla VTR: se generará el documento."
        return True, "El VTR es obligatorio. Falta adjuntar la plantilla modelo."

    return False, ""


def merge_suggestions(
    requirement: Requirement, plan: Plan, items: list[dict[str, object]]
) -> Plan:
    """Aplica sobre el plan determinista lo que propuso el Orquestador.

    El agente **sugiere**: puede cambiar la propuesta y el motivo de un agente opcional, pero no
    puede saltarse las reglas del dominio. Lo que no toca se queda como estaba, y cada elemento
    recuerda de dónde salió.
    """
    proposals: dict[AgentId, dict[str, object]] = {}
    for row in items:
        try:
            agent_id = AgentId(str(row.get("agent", "")))
        except ValueError:
            continue
        if agent_id in PLANNABLE:
            proposals[agent_id] = row

    merged: list[PlanItem] = []
    for item in plan.items:
        proposal = proposals.get(item.agent_id)
        locked = locked_reason(requirement, item.agent_id)
        if proposal is None or locked is not None:
            # Obligatorio por política: la sugerencia del modelo no lo desactiva.
            merged.append(item)
            continue
        suggested = bool(proposal.get("suggested", item.suggested))
        reason = str(proposal.get("reason") or item.reason)
        merged.append(
            PlanItem(
                agent_id=item.agent_id,
                suggested=suggested,
                enabled=suggested,
                reason=reason,
                source="orquestador",
            )
        )
    return replace(plan, items=tuple(merged))


def plan_warnings(requirement: Requirement, plan: Plan) -> tuple[PlanWarning, ...]:
    """Bloqueos (adjunto faltante, política obligatoria) y avisos (dependencia desactivada)."""
    enabled = set(plan.enabled_agents)
    warnings: list[PlanWarning] = []

    if requirement.handles_phi and AgentId.PRIVACY not in enabled:
        warnings.append(
            PlanWarning(
                agent_id=AgentId.PRIVACY,
                level=WarningLevel.BLOQUEO,
                text="Privacidad HIPAA es obligatorio para requerimientos con PHI (o sin clasificar).",
            )
        )

    for agent_id in plan.enabled_agents:
        definition = AGENTS[agent_id]
        kind = definition.requires_attachment
        if kind is not None and not requirement.has_attachment(kind):
            warnings.append(
                PlanWarning(
                    agent_id=agent_id,
                    level=WarningLevel.BLOQUEO,
                    text=f"{definition.label} necesita un adjunto de tipo «{ATTACHMENT_LABELS[kind]}».",
                )
            )
        for dependency in definition.depends_on:
            if dependency not in enabled:
                warnings.append(
                    PlanWarning(
                        agent_id=agent_id,
                        level=WarningLevel.AVISO,
                        text=(
                            f"{definition.label} funciona mejor con {AGENTS[dependency].label} activo; "
                            "trabajará con menos contexto."
                        ),
                    )
                )
    return tuple(warnings)


def locked_reason(requirement: Requirement, agent_id: AgentId) -> str | None:
    """Motivo por el que un agente no se puede desactivar en este requerimiento."""
    if agent_id is AgentId.PRIVACY and requirement.handles_phi:
        if requirement.phi is PhiClassification.SI:
            return "Obligatorio: requerimiento con PHI"
        return "Obligatorio hasta clasificar el requerimiento"
    if not AGENTS[agent_id].optional:
        return f"{AGENTS[agent_id].label} siempre interviene"
    return None
