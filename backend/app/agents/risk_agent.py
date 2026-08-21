"""RiskAgent: mide volatilidad, drawdown y ATR y asigna un nivel de riesgo.

Patrón pedagógico clave: si la serie recibida es corta, este agente NO adivina;
envía un INFO_REQUEST directamente al MarketDataAgent pidiendo historial ampliado
y continúa con la INFO_RESPONSE.
"""
from __future__ import annotations

from typing import Any

from ..models import AgentMessage, AgentName, AgentOpinion, MessageType, RiskLevel
from ..services import indicators as ind
from .base_agent import BaseAgent

INSTRUCTIONS = (
    "Explica en 2-3 frases el perfil de riesgo histórico (volatilidad anualizada, drawdown "
    "máximo, ATR relativo) y por qué la regla asigna el `risk_level` indicado. No cambies el nivel."
)


def compute_risk_facts(closes: list[float], highs: list[float], lows: list[float]) -> dict[str, Any]:
    vol = ind.annualized_volatility(closes)
    dd = ind.max_drawdown(closes)
    atr14 = ind.atr(highs, lows, closes, 14)
    last = closes[-1]
    atr_pct = (atr14 / last) if (atr14 is not None and last) else None

    if (vol is not None and vol > 0.45) or (dd is not None and dd < -0.35):
        level = RiskLevel.ALTO
    elif (vol is not None and vol < 0.20) and (dd is not None and dd > -0.15):
        level = RiskLevel.BAJO
    else:
        level = RiskLevel.MEDIO

    return {
        "bars_used": len(closes),
        "annualized_volatility": ind.round_or_none(vol, 4),
        "max_drawdown": ind.round_or_none(dd, 4),
        "atr_14": ind.round_or_none(atr14, 4),
        "atr_pct": ind.round_or_none(atr_pct, 4),
        "risk_level": level.value,
        "thresholds": {"alto_vol": 0.45, "alto_drawdown": -0.35, "bajo_vol": 0.20, "bajo_drawdown": -0.15},
    }


class RiskAgent(BaseAgent):
    name = AgentName.RISK
    description = "Volatilidad, drawdown y ATR → nivel de riesgo BAJO/MEDIO/ALTO."

    async def process(self, message: AgentMessage) -> AgentMessage:
        data_ref = message.payload.get("data_ref")
        series = self.ctx.data.get(data_ref or "")
        if series is None:
            return self.error_reply(message, f"No encuentro la serie '{data_ref}'.", code="missing_data")

        min_bars = self.ctx.settings.min_bars_risk
        extended_requested = False
        if len(series.bars) < min_bars:
            # Petición de información adicional a otro agente (comunicación directa).
            extended_requested = True
            info = await self.send(
                AgentName.MARKET_DATA,
                MessageType.INFO_REQUEST,
                {
                    "symbol": series.symbol,
                    "days": self.ctx.settings.extended_history_days,
                    "reason": f"Necesito ≥{min_bars} sesiones para drawdown/volatilidad; tengo {len(series.bars)}.",
                },
                symbol=message.symbol,
                in_reply_to=message.id,
            )
            if info.type == MessageType.ERROR:
                return self.error_reply(
                    message, f"No pude ampliar el historial: {info.payload.get('reason')}", code="insufficient_data"
                )
            extended = self.ctx.data.get(info.payload.get("data_ref", ""))
            if extended is None or len(extended.bars) < min_bars:
                got = len(extended.bars) if extended else 0
                return self.error_reply(
                    message,
                    f"El historial ampliado sigue siendo insuficiente ({got} < {min_bars}).",
                    code="insufficient_data",
                )
            series = extended

        facts = compute_risk_facts(series.closes, series.highs, series.lows)
        facts["extended_data_requested"] = extended_requested
        fallback = (
            f"Riesgo {facts['risk_level']}: volatilidad anualizada {facts['annualized_volatility']}, "
            f"drawdown máximo {facts['max_drawdown']}, ATR relativo {facts['atr_pct']} "
            f"sobre {facts['bars_used']} sesiones."
        )
        explanation = await self.explain(
            symbol=message.symbol, task="risk_explanation", instructions=INSTRUCTIONS, facts=facts, fallback_summary=fallback
        )
        level = RiskLevel(facts["risk_level"])
        opinion = AgentOpinion(
            agent=self.name,
            risk_level=level,
            confidence={"BAJO": 0.8, "MEDIO": 0.6, "ALTO": 0.85}[level.value],
            facts=facts,
            explanation=explanation,
        )
        return self.reply(message, MessageType.OPINION, opinion.model_dump(mode="json"))

    def summarize(self, response: AgentMessage) -> str:
        p = response.payload
        return f"riesgo {p.get('risk_level')} (vol {p.get('facts', {}).get('annualized_volatility')})"
