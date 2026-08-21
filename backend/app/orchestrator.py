"""Orquestador: inicia la ejecución, enruta mensajes y coordina el flujo por símbolo.

Flujo por símbolo (los símbolos se procesan en paralelo, con un límite):

    orchestrator ──task_request──▶ market_data
                 ◀──task_result──┘            (o ERROR → decision → NO_ANALIZABLE)
    orchestrator ──task_request──▶ technical ─┐  en paralelo
    orchestrator ──task_request──▶ risk ──────┤  (risk puede pedir más datos a market_data)
                 ◀──opinion──────┘ ◀──opinion─┘
    orchestrator ──task_request──▶ skeptic    (si discrepa: skeptic ──challenge──▶ technical)
                 ◀──opinion/challenge─┘
    orchestrator ──task_request──▶ decision
                 ◀──decision─────┘
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

from .agents.base_agent import AgentContext, BaseAgent
from .agents.decision_agent import DecisionAgent
from .agents.market_data_agent import MarketDataAgent
from .agents.risk_agent import RiskAgent
from .agents.skeptic_agent import SkepticAgent
from .agents.technical_agent import TechnicalAgent
from .config import Settings
from .events import EventBus
from .models import (
    AgentMessage,
    AgentName,
    AgentOpinion,
    Decision,
    EventType,
    LLMExplanation,
    MessageType,
    RunStatus,
    SymbolResult,
)
from .providers.llm_provider import LLMProvider
from .providers.market_data_provider import MarketDataProvider
from .services.costs import summarize_costs
from .services.run_store import RunStore

log = logging.getLogger(__name__)


class Orchestrator:
    def __init__(
        self,
        *,
        run_id: str,
        symbols: list[str],
        bus: EventBus,
        store: RunStore,
        llm: LLMProvider,
        market: MarketDataProvider,
        settings: Settings,
        message_delay_ms: Optional[int] = None,
        agent_mode: Optional[str] = None,
    ) -> None:
        self.run_id = run_id
        self.symbols = symbols
        self.bus = bus
        self.store = store
        self.settings = settings
        delay = settings.message_delay_ms if message_delay_ms is None else message_delay_ms
        self.message_delay_ms = max(0, min(int(delay), settings.max_message_delay_ms))
        mode = (agent_mode or settings.agent_mode or "rules").lower()
        self.agent_mode = mode if mode in ("rules", "llm") else "rules"
        self.ctx = AgentContext(
            run_id=run_id, bus=bus, llm=llm, market=market, settings=settings, deliver=self.deliver, agent_mode=self.agent_mode
        )
        self.agents: dict[AgentName, BaseAgent] = {
            a.name: a for a in (MarketDataAgent(self.ctx), TechnicalAgent(self.ctx), RiskAgent(self.ctx), SkepticAgent(self.ctx), DecisionAgent(self.ctx))
        }

    # ------------------------------------------------------------------ routing
    async def _transit(self) -> None:
        """Latencia simulada del 'canal' entre agentes (se aplica a cada salto)."""
        if self.message_delay_ms > 0:
            await asyncio.sleep(self.message_delay_ms / 1000)

    async def deliver(self, message: AgentMessage) -> AgentMessage:
        """Único camino por el que viaja un mensaje: se publica, 'viaja' y se entrega al destinatario.

        El evento se emite ANTES del retardo para que la UI muestre el mensaje en tránsito
        mientras el destinatario aún no ha empezado a trabajar.
        """
        await self.bus.emit_message(message)
        await self._transit()
        target = self.agents.get(message.recipient)
        if target is None:
            return AgentMessage(
                run_id=self.run_id,
                symbol=message.symbol,
                sender=AgentName.ORCHESTRATOR,
                recipient=message.sender,
                type=MessageType.ERROR,
                payload={"code": "unknown_recipient", "reason": f"No existe el agente {message.recipient}."},
                in_reply_to=message.id,
            )
        response = await target.handle(message)
        await self.bus.emit_message(response)
        await self._transit()  # la respuesta también viaja de vuelta
        return response

    async def ask(self, recipient: AgentName, payload: dict, symbol: str, in_reply_to: Optional[str] = None) -> AgentMessage:
        msg = AgentMessage(
            run_id=self.run_id,
            symbol=symbol,
            sender=AgentName.ORCHESTRATOR,
            recipient=recipient,
            type=MessageType.TASK_REQUEST,
            payload=payload,
            in_reply_to=in_reply_to,
        )
        return await self.deliver(msg)

    # --------------------------------------------------------------------- run
    async def run(self) -> None:
        self.store.set_status(self.run_id, RunStatus.RUNNING)
        await self.bus.emit(
            self.run_id,
            EventType.RUN_STARTED,
            agent=AgentName.ORCHESTRATOR,
            data={
                "symbols": self.symbols,
                "max_parallel": self.settings.max_parallel_symbols,
                "message_delay_ms": self.message_delay_ms,
                "agent_mode": self.agent_mode,
                "agents": {a.name.value: a.description for a in self.agents.values()},
                "llm_provider": self.ctx.llm.name,
                "market_data_provider": self.ctx.market.name,
            },
        )
        semaphore = asyncio.Semaphore(self.settings.max_parallel_symbols)

        async def guarded(symbol: str) -> None:
            async with semaphore:
                try:
                    await self.analyze_symbol(symbol)
                except Exception as e:  # último cortafuegos: nunca dejar un símbolo sin resultado
                    log.exception("Fallo inesperado analizando %s", symbol)
                    await self._finish_symbol(
                        SymbolResult(symbol=symbol, decision=Decision.NO_ANALIZABLE, rationale=f"Error interno: {e}", error=str(e))
                    )

        await asyncio.gather(*(guarded(s) for s in self.symbols))

        run = self.store.get(self.run_id)
        costs = summarize_costs(self.store.events(self.run_id))
        if run is not None:
            run.costs = costs
        self.store.set_status(self.run_id, RunStatus.COMPLETED)
        await self.bus.emit(
            self.run_id,
            EventType.RUN_COMPLETED,
            agent=AgentName.ORCHESTRATOR,
            data={
                "results": {s: r.decision.value for s, r in (run.results.items() if run else [])},
                "symbols_total": len(self.symbols),
                "costs": costs.model_dump(mode="json"),
            },
        )

    # ----------------------------------------------------------------- symbol
    async def analyze_symbol(self, symbol: str) -> None:
        await self.bus.emit(self.run_id, EventType.SYMBOL_STARTED, symbol=symbol, agent=AgentName.ORCHESTRATOR)
        opinions: list[AgentOpinion] = []
        disagreements = 0

        # 1) Datos de mercado
        md = await self.ask(AgentName.MARKET_DATA, {"symbol": symbol, "days": self.settings.initial_history_days}, symbol)
        if md.type == MessageType.ERROR:
            reason = md.payload.get("reason", "sin datos")
            decision = await self.ask(AgentName.DECISION, {"symbol": symbol, "error": reason}, symbol, in_reply_to=md.id)
            await self._finish_symbol(self._build_result(symbol, decision, [], md, disagreements, error=reason))
            return

        data_ref = md.payload["data_ref"]

        # 2) Análisis técnico y de riesgo EN PARALELO (ambos consumen la salida de market_data)
        tech_msg, risk_msg = await asyncio.gather(
            self.ask(AgentName.TECHNICAL, {"symbol": symbol, "data_ref": data_ref}, symbol, in_reply_to=md.id),
            self.ask(AgentName.RISK, {"symbol": symbol, "data_ref": data_ref}, symbol, in_reply_to=md.id),
        )
        tech = tech_msg.payload if tech_msg.type == MessageType.OPINION else None
        risk = risk_msg.payload if risk_msg.type == MessageType.OPINION else None
        for m in (tech_msg, risk_msg):
            if m.type == MessageType.OPINION:
                opinions.append(AgentOpinion.model_validate(m.payload))

        skeptic: Optional[dict] = None
        if tech and risk:
            # 3) Escéptico (puede retar al técnico directamente)
            sk_msg = await self.ask(
                AgentName.SKEPTIC, {"symbol": symbol, "technical": tech, "risk": risk}, symbol, in_reply_to=tech_msg.id
            )
            if sk_msg.type in (MessageType.OPINION, MessageType.CHALLENGE):
                skeptic = sk_msg.payload
                opinions.append(AgentOpinion.model_validate({k: v for k, v in skeptic.items() if k in AgentOpinion.model_fields}))
                if not skeptic.get("agrees", True):
                    disagreements += 1
                    await self.bus.emit(
                        self.run_id,
                        EventType.DISAGREEMENT,
                        symbol=symbol,
                        agent=AgentName.SKEPTIC,
                        data={
                            "against": AgentName.TECHNICAL.value,
                            "counterarguments": skeptic.get("counterarguments", []),
                            "technical_response": (skeptic.get("technical_response") or {}).get("challenge_verdict"),
                        },
                    )

        # 4) Decisión final
        error = None
        if not tech:
            error = f"Análisis técnico no disponible: {tech_msg.payload.get('reason', 'error')}"
        decision = await self.ask(
            AgentName.DECISION,
            {"symbol": symbol, "technical": tech, "risk": risk, "skeptic": skeptic, "error": error},
            symbol,
            in_reply_to=tech_msg.id,
        )
        await self._finish_symbol(self._build_result(symbol, decision, opinions, md, disagreements, error=error))

    # ---------------------------------------------------------------- helpers
    def _build_result(
        self,
        symbol: str,
        decision_msg: AgentMessage,
        opinions: list[AgentOpinion],
        md: AgentMessage,
        disagreements: int,
        *,
        error: Optional[str],
    ) -> SymbolResult:
        p = decision_msg.payload
        if decision_msg.type != MessageType.DECISION:
            return SymbolResult(
                symbol=symbol,
                decision=Decision.NO_ANALIZABLE,
                rationale=f"El agente de decisión falló: {p.get('reason')}",
                opinions=opinions,
                error=p.get("reason"),
                disagreements=disagreements,
            )
        decision_opinion = AgentOpinion(
            agent=AgentName.DECISION,
            confidence=float(p.get("confidence", 0)),
            facts=p.get("facts", {}),
            explanation=LLMExplanation(
                summary=p.get("rationale", ""),
                facts_used=list(p.get("facts", {}).keys()),
                caveats=p.get("caveats", []),
                generated_by=p.get("generated_by", "rules"),
                validation_warnings=p.get("validation_warnings", []),
            ),
        )
        data_ok = md.type != MessageType.ERROR
        return SymbolResult(
            symbol=symbol,
            decision=Decision(p["decision"]),
            confidence=float(p.get("confidence", 0)),
            rationale=p.get("rationale", ""),
            opinions=opinions + [decision_opinion],
            data_source=md.payload.get("source") if data_ok else None,
            bars_used=int(md.payload.get("bars", 0)) if data_ok else 0,
            last_close=md.payload.get("last_close") if data_ok else None,
            last_bar_date=md.payload.get("last_date") if data_ok else None,
            error=error,
            disagreements=disagreements,
        )

    async def _finish_symbol(self, result: SymbolResult) -> None:
        self.store.set_result(self.run_id, result)
        await self.bus.emit(
            self.run_id,
            EventType.DECISION_MADE,
            symbol=result.symbol,
            agent=AgentName.DECISION,
            data={"decision": result.decision.value, "confidence": result.confidence, "rationale": result.rationale},
        )
        await self.bus.emit(
            self.run_id,
            EventType.SYMBOL_COMPLETED,
            symbol=result.symbol,
            agent=AgentName.ORCHESTRATOR,
            data={"result": result.model_dump(mode="json")},
        )
