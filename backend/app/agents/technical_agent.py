"""TechnicalAgent: calcula indicadores y fija una postura (ALCISTA/BAJISTA/NEUTRAL).

La postura sale de reglas deterministas sobre los indicadores; el LLM solo redacta
la explicación a partir de esos mismos números. También responde a los CHALLENGE
del escéptico, pudiendo mantener o rebajar su postura.
"""
from __future__ import annotations

from typing import Any

from ..models import AgentMessage, AgentName, AgentOpinion, MessageType, Stance
from ..services import indicators as ind
from .base_agent import BaseAgent

INSTRUCTIONS = (
    "Explica en 2-3 frases qué dicen los indicadores (medias móviles, RSI, MACD, retorno a 20 "
    "sesiones) y por qué la regla ha fijado la postura indicada en `stance`. Menciona solo "
    "números presentes en los hechos."
)


def compute_technical_facts(closes: list[float]) -> dict[str, Any]:
    last = closes[-1]
    sma20, sma50 = ind.sma(closes, 20), ind.sma(closes, 50)
    rsi14 = ind.rsi(closes, 14)
    macd = ind.macd(closes)
    ret20 = ind.pct_change(closes, 20)

    score = 0
    reasons: list[str] = []
    if sma50 is not None:
        if last > sma50:
            score += 1
            reasons.append("cierre por encima de la SMA50")
        else:
            score -= 1
            reasons.append("cierre por debajo de la SMA50")
    if sma20 is not None and sma50 is not None:
        if sma20 > sma50:
            score += 1
            reasons.append("SMA20 por encima de SMA50")
        else:
            score -= 1
            reasons.append("SMA20 por debajo de SMA50")
    if rsi14 is not None:
        if rsi14 < 30:
            score += 1
            reasons.append("RSI en sobreventa (<30)")
        elif rsi14 > 70:
            score -= 1
            reasons.append("RSI en sobrecompra (>70)")
    if macd is not None:
        if macd["histogram"] > 0:
            score += 1
            reasons.append("histograma MACD positivo")
        else:
            score -= 1
            reasons.append("histograma MACD negativo")

    if score >= 2:
        stance = Stance.ALCISTA
    elif score <= -2:
        stance = Stance.BAJISTA
    else:
        stance = Stance.NEUTRAL
    confidence = round(min(1.0, abs(score) / 4), 2)

    return {
        "bars_used": len(closes),
        "last_close": round(last, 4),
        "sma_20": ind.round_or_none(sma20, 4),
        "sma_50": ind.round_or_none(sma50, 4),
        "rsi_14": ind.round_or_none(rsi14, 2),
        "macd_histogram": ind.round_or_none(macd["histogram"] if macd else None, 4),
        "return_20d": ind.round_or_none(ret20, 4),
        "score": score,
        "rule_reasons": reasons,
        "stance": stance.value,
        "confidence": confidence,
    }


class TechnicalAgent(BaseAgent):
    name = AgentName.TECHNICAL
    description = "Indicadores técnicos (SMA, RSI, MACD) → postura alcista/bajista/neutral."

    async def process(self, message: AgentMessage) -> AgentMessage:
        if message.type == MessageType.CHALLENGE:
            return await self._answer_challenge(message)
        return await self._analyze(message)

    async def _analyze(self, message: AgentMessage) -> AgentMessage:
        data_ref = message.payload.get("data_ref")
        series = self.ctx.data.get(data_ref or "")
        if series is None:
            return self.error_reply(message, f"No encuentro la serie '{data_ref}'.", code="missing_data")
        closes = series.closes
        if len(closes) < self.ctx.settings.min_bars_technical:
            return self.error_reply(
                message,
                f"Solo {len(closes)} sesiones; el análisis técnico requiere {self.ctx.settings.min_bars_technical}.",
                code="insufficient_data",
            )

        facts = compute_technical_facts(closes)
        fallback = (
            f"Postura {facts['stance']} (puntuación {facts['score']}): {', '.join(facts['rule_reasons'])}. "
            f"Cierre {facts['last_close']}, RSI14 {facts['rsi_14']}."
        )
        explanation = await self.explain(
            symbol=message.symbol, task="technical_explanation", instructions=INSTRUCTIONS, facts=facts, fallback_summary=fallback
        )
        opinion = AgentOpinion(
            agent=self.name,
            stance=Stance(facts["stance"]),
            confidence=facts["confidence"],
            facts=facts,
            explanation=explanation,
        )
        return self.reply(message, MessageType.OPINION, opinion.model_dump(mode="json"))

    async def _answer_challenge(self, message: AgentMessage) -> AgentMessage:
        """El escéptico discrepa: el agente revisa su postura con reglas explícitas."""
        original = message.payload.get("original_opinion", {})
        counter = message.payload.get("counterarguments", [])
        facts = dict(original.get("facts", {}))
        stance = Stance(original.get("stance", Stance.NEUTRAL.value))
        confidence = float(original.get("confidence", 0.0))

        concede_keys = {"rsi_overbought", "rsi_oversold", "low_confidence"}
        conceded = [c for c in counter if c.get("code") in concede_keys]
        if conceded:
            new_confidence = round(max(0.0, confidence - 0.25 * len(conceded)), 2)
            new_stance = stance if new_confidence >= 0.5 else Stance.NEUTRAL
            verdict = "concede"
            note = "Acepto las objeciones sobre " + ", ".join(c["code"] for c in conceded) + "; rebajo la confianza."
        else:
            new_confidence, new_stance, verdict = confidence, stance, "maintains"
            note = "Mantengo la postura: las objeciones no afectan a los indicadores usados por la regla."

        facts.update({"stance": new_stance.value, "confidence": new_confidence, "challenge_verdict": verdict})
        return self.reply(
            message,
            MessageType.OPINION,
            {
                "agent": self.name.value,
                "stance": new_stance.value,
                "confidence": new_confidence,
                "challenge_verdict": verdict,
                "note": note,
                "facts": facts,
            },
        )

    def summarize(self, response: AgentMessage) -> str:
        p = response.payload
        extra = f" ({p['challenge_verdict']})" if p.get("challenge_verdict") else ""
        return f"{p.get('stance')} conf. {p.get('confidence')}{extra}"
