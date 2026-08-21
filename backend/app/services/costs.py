"""Agregación del consumo LLM (tokens y USD) a partir de los eventos de una ejecución.

Cada evento `llm_call_completed` con `ok=True` lleva un dict `usage` con
`input_tokens`, `output_tokens`, `model`, `cost_usd` y `cost_source`
(provider | estimated | mock | unknown). Aquí se suma por agente y en total.
"""
from __future__ import annotations

from typing import Iterable

from ..models import AgentCost, CostSummary, Event, EventType


def _add(acc: AgentCost, usage: dict) -> None:
    acc.calls += 1
    tin, tout = usage.get("input_tokens"), usage.get("output_tokens")
    if isinstance(tin, (int, float)):
        acc.input_tokens += int(tin)
    if isinstance(tout, (int, float)):
        acc.output_tokens += int(tout)
    cost = usage.get("cost_usd")
    if isinstance(cost, (int, float)):
        acc.cost_usd = round((acc.cost_usd or 0.0) + float(cost), 6)
        acc.cost_known_calls += 1
    source = str(usage.get("cost_source") or "unknown")
    acc.sources[source] = acc.sources.get(source, 0) + 1
    model = str(usage.get("model") or "?")
    acc.models[model] = acc.models.get(model, 0) + 1


def summarize_costs(events: Iterable[Event]) -> CostSummary:
    summary = CostSummary()
    for e in events:
        if e.type != EventType.LLM_CALL_COMPLETED or not e.data.get("ok"):
            continue
        usage = e.data.get("usage")
        if not isinstance(usage, dict):
            continue
        agent = e.agent.value if e.agent else "unknown"
        _add(summary.per_agent.setdefault(agent, AgentCost()), usage)
        _add(summary.total, usage)
    return summary
