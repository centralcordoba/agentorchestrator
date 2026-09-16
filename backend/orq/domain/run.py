"""Ejecución de una revisión: perfiles congelados, estado por agente y traza."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .enums import AgentId, AgentRunStatus, ProviderId, RunStatus, TraceEventType
from .errors import DomainError


@dataclass(frozen=True, slots=True)
class ProfileSnapshot:
    """Proveedor, modelo y versión de prompt congelados al arrancar la ejecución.

    Una vez escrito no se reescribe: es lo que hace reproducible y auditable la revisión.
    """

    provider: ProviderId
    model: str
    prompt_version: int
    temperature: float = 0.0
    max_steps: int = 4


@dataclass(frozen=True, slots=True)
class Usage:
    """Consumo de una llamada o de un agente completo."""

    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0

    def __add__(self, other: "Usage") -> "Usage":
        return Usage(
            tokens_in=self.tokens_in + other.tokens_in,
            tokens_out=self.tokens_out + other.tokens_out,
            cost_usd=round(self.cost_usd + other.cost_usd, 6),
        )


@dataclass(frozen=True, slots=True)
class LLMCall:
    """Registro de una llamada al modelo, para auditoría y control de coste.

    Guarda metadatos, **nunca el contenido**: el prompt o la respuesta podrían llevar PHI.
    """

    agent_id: AgentId
    provider: ProviderId
    model: str
    prompt_version: int
    usage: Usage
    duration_ms: int
    attempts: int = 1
    tools_used: tuple[str, ...] = ()
    tools_rejected: tuple[str, ...] = ()
    at: datetime | None = None
    error: str = ""


@dataclass(frozen=True, slots=True)
class TraceEvent:
    """Evento de la traza. Se persiste: es la evidencia que citan el asistente y la auditoría.

    Nunca contiene valores de identificadores de PHI (el guardarraíl vive en ORQ-20).
    """

    seq: int
    run_id: str
    at: datetime
    type: TraceEventType
    agent: AgentId | None = None
    to: AgentId | None = None
    title: str = ""
    detail: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    usage: Usage | None = None


@dataclass(slots=True)
class AgentExecution:
    """Estado de un agente dentro de la ejecución."""

    agent_id: AgentId
    status: AgentRunStatus = AgentRunStatus.PENDIENTE
    reason: str = ""
    started_at: datetime | None = None
    finished_at: datetime | None = None
    usage: Usage = field(default_factory=Usage)
    #: Salida ya validada contra el esquema del agente.
    output: dict[str, Any] | None = None
    #: Llamadas al modelo que hizo este agente (metadatos, sin contenido).
    calls: tuple[LLMCall, ...] = ()
    error: str = ""


@dataclass(slots=True)
class Run:
    id: str
    requirement_id: str
    started_by: str
    started_at: datetime
    enabled_agents: tuple[AgentId, ...]
    #: Congelado al arrancar; no se reescribe.
    profiles: dict[AgentId, ProfileSnapshot] = field(default_factory=dict)
    status: RunStatus = RunStatus.EN_CURSO
    executions: dict[AgentId, AgentExecution] = field(default_factory=dict)
    finished_at: datetime | None = None
    cancelled_at: datetime | None = None
    error: str = ""

    def execution(self, agent_id: AgentId) -> AgentExecution:
        if agent_id not in self.executions:
            self.executions[agent_id] = AgentExecution(agent_id=agent_id)
        return self.executions[agent_id]

    def profile(self, agent_id: AgentId) -> ProfileSnapshot:
        try:
            return self.profiles[agent_id]
        except KeyError as exc:  # pragma: no cover - indica un fallo de construcción
            raise DomainError(f"La ejecución no congeló el perfil de {agent_id.value}.") from exc

    @property
    def usage(self) -> Usage:
        total = Usage()
        for execution in self.executions.values():
            total = total + execution.usage
        return total

    @property
    def is_finished(self) -> bool:
        return self.status is not RunStatus.EN_CURSO
