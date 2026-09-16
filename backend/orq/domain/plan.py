"""Plan de la revisión: qué agentes intervienen y por qué."""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime

from .agents import AGENTS
from .enums import AgentId, WarningLevel
from .errors import DomainError


@dataclass(frozen=True, slots=True)
class PlanItem:
    agent_id: AgentId
    #: Lo que propuso el orquestador.
    suggested: bool
    #: Lo que decidió la persona (el orquestador sugiere, no impone).
    enabled: bool
    reason: str = ""
    #: De dónde sale la sugerencia: `regla` (determinista) o `orquestador` (asistida por el LLM).
    source: str = "regla"


@dataclass(frozen=True, slots=True)
class Plan:
    items: tuple[PlanItem, ...]
    suggested_at: datetime
    overridden_by: str = ""

    @property
    def enabled_agents(self) -> tuple[AgentId, ...]:
        return tuple(i.agent_id for i in self.items if i.enabled)

    def item(self, agent_id: AgentId) -> PlanItem | None:
        return next((i for i in self.items if i.agent_id == agent_id), None)

    def is_enabled(self, agent_id: AgentId) -> bool:
        item = self.item(agent_id)
        return bool(item and item.enabled)

    def toggled(self, agent_id: AgentId, *, enabled: bool, by: str) -> "Plan":
        """Activa o desactiva un agente. Los no opcionales no se pueden desactivar."""
        item = self.item(agent_id)
        if item is None:
            raise DomainError(f"El plan no incluye al agente {agent_id.value}.")
        if not enabled and not AGENTS[agent_id].optional:
            raise DomainError(f"{AGENTS[agent_id].label} no se puede desactivar.")
        items = tuple(replace(i, enabled=enabled) if i.agent_id == agent_id else i for i in self.items)
        return replace(self, items=items, overridden_by=by)


@dataclass(frozen=True, slots=True)
class PlanWarning:
    agent_id: AgentId
    level: WarningLevel
    text: str

    @property
    def blocks(self) -> bool:
        return self.level is WarningLevel.BLOQUEO
