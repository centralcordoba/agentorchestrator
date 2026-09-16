"""Serialización a JSON con nombres en camelCase, como los espera el frontend."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import fields, is_dataclass
from datetime import datetime
from enum import Enum
from typing import Any

from ..application.use_cases import PlanView, RunView
from ..domain.deliverables import Deliverables
from ..domain.plan import Plan, PlanWarning
from ..domain.requirement import Requirement
from ..domain.run import Run, TraceEvent


def camel(name: str) -> str:
    head, *rest = name.split("_")
    return head + "".join(part.title() for part in rest)


def jsonify(value: Any) -> Any:
    """Convierte dataclasses, enums, fechas y tuplas a tipos JSON, con claves en camelCase."""
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if is_dataclass(value) and not isinstance(value, type):
        return {camel(f.name): jsonify(getattr(value, f.name)) for f in fields(value)}
    # `Mapping` y no `dict`: los esquemas de los agentes son `MappingProxyType` de solo lectura.
    if isinstance(value, Mapping):
        return {(camel(k) if isinstance(k, str) else jsonify(k)): jsonify(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [jsonify(v) for v in value]
    return value


def requirement_json(requirement: Requirement) -> dict[str, Any]:
    data = jsonify(requirement)
    data["handlesPhi"] = requirement.handles_phi
    return data


def plan_json(plan: Plan) -> dict[str, Any]:
    return jsonify(plan)


def warning_json(warning: PlanWarning) -> dict[str, Any]:
    return jsonify(warning)


def plan_view_json(view: PlanView) -> dict[str, Any]:
    return {
        "plan": plan_json(view.plan),
        "warnings": [warning_json(w) for w in view.warnings],
        "blocked": view.blocked,
    }


def event_json(event: TraceEvent) -> dict[str, Any]:
    return jsonify(event)


def run_json(run: Run) -> dict[str, Any]:
    data = jsonify(run)
    # `profiles` y `executions` están indexados por agente: la clave es el identificador, no camelCase.
    data["profiles"] = {agent.value: jsonify(profile) for agent, profile in run.profiles.items()}
    data["executions"] = {
        agent.value: jsonify(execution) for agent, execution in run.executions.items()
    }
    data["usage"] = jsonify(run.usage)
    return data


def deliverables_json(deliverables: Deliverables) -> dict[str, Any]:
    data = jsonify(deliverables)
    data["missing"] = {agent.value: reason for agent, reason in deliverables.missing.items()}
    data["findings"] = [jsonify(f) for f in deliverables.findings]
    return data


def run_view_json(view: RunView, *, with_events: bool = False) -> dict[str, Any]:
    data = {
        "run": run_json(view.run),
        "deliverables": deliverables_json(view.deliverables),
    }
    if with_events:
        data["events"] = [event_json(e) for e in view.events]
    return data
