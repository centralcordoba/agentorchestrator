"""Clase base de los agentes.

Un agente:
- recibe un `AgentMessage` en `handle()` y devuelve otro `AgentMessage` (respuesta);
- puede enviar mensajes a otros agentes con `send()`; el orquestador los entrega
  y los hace visibles como eventos;
- en modo **reglas** decide con código y pide al LLM un resumen con `explain()`;
- en modo **llm** razona con el modelo en un bucle de herramientas (`run_agent_loop()`):
  el modelo invoca funciones deterministas (indicadores, más historial, retar a otro
  agente...) y termina con un JSON validado. Las reglas actúan como guardarraíles.
"""
from __future__ import annotations

import json
import logging
import traceback
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Optional

from ..config import Settings
from ..events import EventBus
from ..models import AgentMessage, AgentName, EventType, LLMExplanation, MessageType
from ..providers.llm_provider import (
    AGENT_SYSTEM_PROMPT,
    EXPLANATION_SCHEMA,
    ChatMessage,
    LLMError,
    LLMProvider,
    LLMRequest,
    ToolSpec,
    render_agent_prompt,
)
from ..providers.market_data_provider import MarketDataProvider, MarketSeries
from ..services.validation import validate_explanation

log = logging.getLogger(__name__)

Deliver = Callable[[AgentMessage], Awaitable[AgentMessage]]
ToolHandler = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


@dataclass
class AgentContext:
    """Dependencias compartidas por todos los agentes de una ejecución."""

    run_id: str
    bus: EventBus
    llm: LLMProvider
    market: MarketDataProvider
    settings: Settings
    deliver: Deliver                                    # entrega un mensaje y devuelve la respuesta
    agent_mode: str = "rules"                           # rules | llm
    data: dict[str, MarketSeries] = field(default_factory=dict)  # series compartidas por referencia


@dataclass
class Tool:
    """Herramienta que el modelo puede invocar en modo llm. El handler es código determinista."""

    spec: ToolSpec
    handler: ToolHandler


class BaseAgent:
    name: AgentName = AgentName.ORCHESTRATOR
    description: str = ""

    def __init__(self, ctx: AgentContext) -> None:
        self.ctx = ctx

    @property
    def llm_mode(self) -> bool:
        return self.ctx.agent_mode == "llm"

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
            data={
                "message_id": message.id,
                "message_type": message.type.value,
                "from": message.sender.value,
                "mode": self.ctx.agent_mode,
            },
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

    # ------------------------------------------------------------- eventos útiles
    async def warn(self, symbol: Optional[str], task: str, warnings: list[str], *, discarded: bool = False) -> None:
        if warnings:
            await self.ctx.bus.emit(
                self.ctx.run_id,
                EventType.VALIDATION_WARNING,
                symbol=symbol,
                agent=self.name,
                data={"task": task, "warnings": warnings, "discarded": discarded},
            )

    async def guardrail(self, symbol: Optional[str], rule: str, *, before: Any, after: Any, reason: str) -> None:
        """Registra que una regla ha corregido la salida del modelo."""
        await self.ctx.bus.emit(
            self.ctx.run_id,
            EventType.GUARDRAIL_APPLIED,
            symbol=symbol,
            agent=self.name,
            data={"rule": rule, "before": before, "after": after, "reason": reason},
        )

    # ------------------------------------------------------------ LLM: modo reglas
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
            data={"task": task, "provider": llm.name, "fact_keys": sorted(facts), "mode": "rules"},
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
        await self.warn(symbol, task, warnings, discarded=bool(hard))
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

    # --------------------------------------------------------------- LLM: modo llm
    async def run_agent_loop(
        self,
        *,
        symbol: Optional[str],
        task: str,
        instructions: str,
        facts: dict[str, Any],
        tools: list[Tool],
        schema: dict[str, Any],
    ) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
        """Bucle agente↔modelo con herramientas.

        Devuelve (salida_final, hechos_conocidos, registro_de_herramientas). `hechos_conocidos`
        es la unión de los hechos iniciales y de todos los resultados de herramientas: es el
        universo contra el que se valida la evidencia y los números del modelo.
        Lanza LLMError si el modelo no está disponible o no termina en `AGENT_MAX_STEPS` turnos.
        """
        bus, llm = self.ctx.bus, self.ctx.llm
        by_name = {t.spec.name: t for t in tools}
        messages = [ChatMessage(role="user", content=render_agent_prompt(task, instructions, facts, schema))]
        known: dict[str, Any] = dict(facts)
        tool_log: list[dict[str, Any]] = []
        max_steps = max(1, self.ctx.settings.agent_max_steps)

        for step in range(1, max_steps + 1):
            await bus.emit(
                self.ctx.run_id,
                EventType.LLM_CALL_STARTED,
                symbol=symbol,
                agent=self.name,
                data={"task": task, "step": step, "provider": llm.name, "tools": sorted(by_name), "mode": "llm"},
            )
            try:
                turn = await llm.chat(
                    task=task, system=AGENT_SYSTEM_PROMPT, messages=messages, tools=[t.spec for t in tools], schema=schema
                )
            except LLMError as e:
                await bus.emit(
                    self.ctx.run_id,
                    EventType.LLM_CALL_COMPLETED,
                    symbol=symbol,
                    agent=self.name,
                    data={"task": task, "step": step, "ok": False, "error": str(e), "fallback": "rules"},
                )
                raise
            await bus.emit(
                self.ctx.run_id,
                EventType.LLM_CALL_COMPLETED,
                symbol=symbol,
                agent=self.name,
                data={
                    "task": task,
                    "step": step,
                    "ok": True,
                    "usage": turn.usage,
                    "tool_calls": [c.name for c in turn.tool_calls],
                    "final": turn.output is not None,
                },
            )
            messages.append(turn.assistant)

            if not turn.tool_calls:
                return turn.output or {}, known, tool_log

            for call in turn.tool_calls:
                tool = by_name.get(call.name)
                if tool is None:
                    result: dict[str, Any] = {"error": f"Herramienta desconocida: {call.name}"}
                else:
                    try:
                        result = await tool.handler(call.arguments or {})
                    except Exception as e:  # el fallo de una herramienta se devuelve al modelo, no rompe el agente
                        log.warning("Herramienta %s falló: %s", call.name, e)
                        result = {"error": f"{e.__class__.__name__}: {e}"}
                if isinstance(result, dict) and "error" not in result:
                    known.update(result)
                tool_log.append({"tool": call.name, "arguments": call.arguments, "result": result})
                await bus.emit(
                    self.ctx.run_id,
                    EventType.TOOL_CALLED,
                    symbol=symbol,
                    agent=self.name,
                    data={"task": task, "step": step, "tool": call.name, "arguments": call.arguments, "result": result},
                )
                messages.append(
                    ChatMessage(
                        role="tool",
                        tool_call_id=call.id,
                        tool_name=call.name,
                        content=json.dumps(result, ensure_ascii=False, default=str),
                    )
                )

        raise LLMError(f"El agente no entregó una respuesta final en {max_steps} turnos.")

    @staticmethod
    def tool_called(tool_log: list[dict[str, Any]], name: str) -> bool:
        return any(t["tool"] == name and "error" not in (t.get("result") or {}) for t in tool_log)
