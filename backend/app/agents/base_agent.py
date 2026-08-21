"""Clase base de los agentes.

Un agente:
- recibe un `AgentMessage` en `handle()` y devuelve otro `AgentMessage` (respuesta);
- puede enviar mensajes a otros agentes con `send()`; el orquestador los entrega
  y los hace visibles como eventos;
- puede pedir al LLM una explicación resumida con `explain()`, que siempre pasa
  por la validación "no inventar datos" y tiene un fallback determinista.
"""
from __future__ import annotations

import logging
import traceback
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Optional

from ..config import Settings
from ..events import EventBus
from ..models import AgentMessage, AgentName, EventType, LLMExplanation, MessageType
from ..providers.llm_provider import EXPLANATION_SCHEMA, LLMError, LLMProvider, LLMRequest
from ..providers.market_data_provider import MarketDataProvider, MarketSeries
from ..services.validation import validate_explanation

log = logging.getLogger(__name__)

Deliver = Callable[[AgentMessage], Awaitable[AgentMessage]]


@dataclass
class AgentContext:
    """Dependencias compartidas por todos los agentes de una ejecución."""

    run_id: str
    bus: EventBus
    llm: LLMProvider
    market: MarketDataProvider
    settings: Settings
    deliver: Deliver                                    # entrega un mensaje y devuelve la respuesta
    data: dict[str, MarketSeries] = field(default_factory=dict)  # series compartidas por referencia


class BaseAgent:
    name: AgentName = AgentName.ORCHESTRATOR
    description: str = ""

    def __init__(self, ctx: AgentContext) -> None:
        self.ctx = ctx

    # ----------------------------------------------------------------- mensajes
    def make_message(
        self,
        recipient: AgentName,
        type: MessageType,
        payload: dict[str, Any],
        *,
        symbol: Optional[str] = None,
        in_reply_to: Optional[str] = None,
    ) -> AgentMessage:
        return AgentMessage(
            run_id=self.ctx.run_id,
            symbol=symbol,
            sender=self.name,
            recipient=recipient,
            type=type,
            payload=payload,
            in_reply_to=in_reply_to,
        )

    async def send(
        self,
        recipient: AgentName,
        type: MessageType,
        payload: dict[str, Any],
        *,
        symbol: Optional[str] = None,
        in_reply_to: Optional[str] = None,
    ) -> AgentMessage:
        """Envía un mensaje a otro agente y espera su respuesta."""
        msg = self.make_message(recipient, type, payload, symbol=symbol, in_reply_to=in_reply_to)
        return await self.ctx.deliver(msg)

    def reply(self, to: AgentMessage, type: MessageType, payload: dict[str, Any]) -> AgentMessage:
        return self.make_message(to.sender, type, payload, symbol=to.symbol, in_reply_to=to.id)

    def error_reply(self, to: AgentMessage, reason: str, *, code: str = "agent_error") -> AgentMessage:
        return self.reply(to, MessageType.ERROR, {"code": code, "reason": reason})

    # ------------------------------------------------------------- ciclo de vida
    async def handle(self, message: AgentMessage) -> AgentMessage:
        """Punto de entrada: envuelve `process()` con eventos de inicio/fin/error."""
        bus = self.ctx.bus
        await bus.emit(
            self.ctx.run_id,
            EventType.AGENT_STARTED,
            symbol=message.symbol,
            agent=self.name,
            data={"message_id": message.id, "message_type": message.type.value, "from": message.sender.value},
        )
        try:
            response = await self.process(message)
        except Exception as e:  # error no controlado → mensaje ERROR, nunca una excepción silenciosa
            log.error("Agente %s falló: %s\n%s", self.name.value, e, traceback.format_exc())
            await bus.emit(
                self.ctx.run_id,
                EventType.AGENT_ERROR,
                symbol=message.symbol,
                agent=self.name,
                data={"error": str(e), "error_type": e.__class__.__name__},
            )
            return self.error_reply(message, f"{e.__class__.__name__}: {e}")

        if response.type == MessageType.ERROR:
            await bus.emit(
                self.ctx.run_id,
                EventType.AGENT_ERROR,
                symbol=message.symbol,
                agent=self.name,
                data={"error": response.payload.get("reason"), "code": response.payload.get("code")},
            )
        else:
            await bus.emit(
                self.ctx.run_id,
                EventType.AGENT_COMPLETED,
                symbol=message.symbol,
                agent=self.name,
                data={"response_type": response.type.value, "summary": self.summarize(response)},
            )
        return response

    async def process(self, message: AgentMessage) -> AgentMessage:  # pragma: no cover - abstracto
        raise NotImplementedError

    def summarize(self, response: AgentMessage) -> str:
        """Texto corto para el log de eventos (sobrescribible)."""
        return response.type.value

    # ------------------------------------------------------------------- LLM
    async def explain(
        self,
        *,
        symbol: Optional[str],
        task: str,
        instructions: str,
        facts: dict[str, Any],
        fallback_summary: str,
    ) -> LLMExplanation:
        """Pide al LLM un resumen auditable. Si falla o inventa datos, usa el de reglas."""
        bus, llm = self.ctx.bus, self.ctx.llm
        await bus.emit(
            self.ctx.run_id,
            EventType.LLM_CALL_STARTED,
            symbol=symbol,
            agent=self.name,
            data={"task": task, "provider": llm.name, "fact_keys": sorted(facts)},
        )
        try:
            raw = await llm.complete_json(
                LLMRequest(agent=self.name.value, task=task, instructions=instructions, facts=facts, schema=EXPLANATION_SCHEMA)
            )
        except LLMError as e:
            await bus.emit(
                self.ctx.run_id,
                EventType.LLM_CALL_COMPLETED,
                symbol=symbol,
                agent=self.name,
                data={"task": task, "ok": False, "error": str(e), "fallback": "rules"},
            )
            return LLMExplanation(
                summary=fallback_summary,
                facts_used=sorted(facts),
                generated_by="rules",
                validation_warnings=[f"LLM no disponible: {e}"],
            )

        usage = raw.pop("_usage", None) if isinstance(raw, dict) else None
        explanation, warnings = validate_explanation(raw, facts, llm.name)
        hard = [w for w in warnings if "no aparece" in w or "vacío" in w]
        if warnings:
            await bus.emit(
                self.ctx.run_id,
                EventType.VALIDATION_WARNING,
                symbol=symbol,
                agent=self.name,
                data={"task": task, "warnings": warnings, "discarded": bool(hard)},
            )
        if hard:
            # La explicación del LLM no es fiable: se sustituye por la determinista.
            explanation = LLMExplanation(
                summary=fallback_summary,
                facts_used=sorted(facts),
                caveats=explanation.caveats,
                generated_by="rules",
                validation_warnings=warnings + ["Explicación del LLM descartada por la validación."],
            )
        await bus.emit(
            self.ctx.run_id,
            EventType.LLM_CALL_COMPLETED,
            symbol=symbol,
            agent=self.name,
            data={"task": task, "ok": True, "usage": usage, "warnings": len(warnings), "generated_by": explanation.generated_by},
        )
        return explanation
