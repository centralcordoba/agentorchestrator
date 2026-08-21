"""Modelos de dominio: mensajes entre agentes, eventos de observabilidad y resultados."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


def now() -> datetime:
    return datetime.now(timezone.utc)


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


# --------------------------------------------------------------------------- enums
class Decision(str, Enum):
    COMPRA = "COMPRA"
    VENTA = "VENTA"
    ESPERAR = "ESPERAR"
    NO_ANALIZABLE = "NO_ANALIZABLE"


class Stance(str, Enum):
    ALCISTA = "ALCISTA"
    BAJISTA = "BAJISTA"
    NEUTRAL = "NEUTRAL"


class RiskLevel(str, Enum):
    BAJO = "BAJO"
    MEDIO = "MEDIO"
    ALTO = "ALTO"


class AgentName(str, Enum):
    ORCHESTRATOR = "orchestrator"
    MARKET_DATA = "market_data"
    TECHNICAL = "technical"
    RISK = "risk"
    SKEPTIC = "skeptic"
    DECISION = "decision"


class MessageType(str, Enum):
    TASK_REQUEST = "task_request"        # "haz X"
    TASK_RESULT = "task_result"          # resultado de una tarea
    INFO_REQUEST = "info_request"        # "necesito más datos"
    INFO_RESPONSE = "info_response"      # respuesta a una petición de datos
    OPINION = "opinion"                  # opinión de un agente analista
    CHALLENGE = "challenge"              # réplica / discrepancia
    DECISION = "decision"                # decisión final
    ERROR = "error"                      # fallo o dato faltante


class EventType(str, Enum):
    RUN_STARTED = "run_started"
    RUN_COMPLETED = "run_completed"
    SYMBOL_STARTED = "symbol_started"
    SYMBOL_COMPLETED = "symbol_completed"
    AGENT_STARTED = "agent_started"
    AGENT_COMPLETED = "agent_completed"
    AGENT_ERROR = "agent_error"
    MESSAGE_SENT = "message_sent"
    LLM_CALL_STARTED = "llm_call_started"
    LLM_CALL_COMPLETED = "llm_call_completed"
    VALIDATION_WARNING = "validation_warning"
    DISAGREEMENT = "disagreement"
    DECISION_MADE = "decision_made"
    TOOL_CALLED = "tool_called"              # modo llm: el agente invoca una herramienta
    GUARDRAIL_APPLIED = "guardrail_applied"  # modo llm: una regla corrige la salida del modelo


class AgentMode(str, Enum):
    RULES = "rules"   # las reglas deciden; el LLM solo redacta
    LLM = "llm"       # el LLM razona con herramientas; las reglas vigilan


# ------------------------------------------------------------------------ messages
class AgentMessage(BaseModel):
    """Unidad de comunicación entre agentes. Todo lo que un agente sabe de otro
    pasa por aquí, y todo mensaje se publica como evento observable."""

    id: str = Field(default_factory=lambda: new_id("msg"))
    run_id: str
    symbol: Optional[str] = None
    sender: AgentName
    recipient: AgentName
    type: MessageType
    payload: dict[str, Any] = Field(default_factory=dict)
    in_reply_to: Optional[str] = None
    timestamp: datetime = Field(default_factory=now)


class Event(BaseModel):
    """Evento de observabilidad emitido por el orquestador o por los agentes."""

    seq: int
    run_id: str
    type: EventType
    timestamp: datetime = Field(default_factory=now)
    symbol: Optional[str] = None
    agent: Optional[AgentName] = None
    message: Optional[AgentMessage] = None
    data: dict[str, Any] = Field(default_factory=dict)


# ------------------------------------------------------------------------- outputs
class LLMExplanation(BaseModel):
    """Salida estructurada y auditable del LLM. Nunca contiene razonamiento oculto."""

    summary: str
    facts_used: list[str] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)
    generated_by: str = "rules"          # "rules" | nombre del proveedor LLM
    validation_warnings: list[str] = Field(default_factory=list)


class Evidence(BaseModel):
    """Evidencia citada por un agente en modo llm: nombre exacto de un hecho + observación."""

    fact: str
    observation: str


class AgentOpinion(BaseModel):
    agent: AgentName
    stance: Optional[Stance] = None
    risk_level: Optional[RiskLevel] = None
    agrees: Optional[bool] = None
    confidence: float = 0.0
    facts: dict[str, Any] = Field(default_factory=dict)
    explanation: LLMExplanation
    # Modo llm
    mode: str = "rules"                                   # rules | llm | rules_fallback
    evidence: list[Evidence] = Field(default_factory=list)
    rule_reference: dict[str, Any] = Field(default_factory=dict)   # lo que habrían dicho las reglas


class SymbolResult(BaseModel):
    symbol: str
    decision: Decision
    confidence: float = 0.0
    rationale: str = ""
    opinions: list[AgentOpinion] = Field(default_factory=list)
    data_source: Optional[str] = None
    bars_used: int = 0
    last_close: Optional[float] = None
    last_bar_date: Optional[str] = None
    error: Optional[str] = None
    disagreements: int = 0


class RunStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


DISCLAIMER = (
    "Demo educativa. No constituye asesoramiento financiero ni recomendación de inversión. "
    "Las señales son experimentales y se derivan exclusivamente de datos históricos."
)


class AgentCost(BaseModel):
    """Consumo LLM acumulado (por agente o total)."""

    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: Optional[float] = None          # None si ninguna llamada informó coste
    cost_known_calls: int = 0                 # llamadas con coste conocido (proveedor o estimado)
    sources: dict[str, int] = Field(default_factory=dict)   # provider | estimated | mock | unknown → nº llamadas
    models: dict[str, int] = Field(default_factory=dict)    # modelo → nº llamadas


class CostSummary(BaseModel):
    currency: str = "USD"
    per_agent: dict[str, AgentCost] = Field(default_factory=dict)
    total: AgentCost = Field(default_factory=AgentCost)


class RunSummary(BaseModel):
    run_id: str
    status: RunStatus
    symbols: list[str]
    created_at: datetime
    finished_at: Optional[datetime] = None
    results: dict[str, SymbolResult] = Field(default_factory=dict)
    providers: dict[str, str] = Field(default_factory=dict)
    message_delay_ms: int = 0
    agent_mode: AgentMode = AgentMode.RULES
    costs: Optional[CostSummary] = None
    disclaimer: str = DISCLAIMER


# ------------------------------------------------------------------------- api io
class RunRequest(BaseModel):
    symbols: list[str] = Field(..., min_length=1, max_length=20)
    # Retardo por mensaje entre agentes (ms). None → valor por defecto del servidor.
    message_delay_ms: Optional[int] = Field(default=None, ge=0, le=5000)
    # Modo de los agentes. None → valor por defecto del servidor (AGENT_MODE).
    agent_mode: Optional[AgentMode] = None


class RunCreated(BaseModel):
    run_id: str
    symbols: list[str]
    rejected: dict[str, str] = Field(default_factory=dict)
    message_delay_ms: int = 0
    agent_mode: AgentMode = AgentMode.RULES
