"""SkepticAgent: busca contradicciones entre las opiniones técnica y de riesgo.

Si discrepa, envía un CHALLENGE directamente al TechnicalAgent y recoge su
respuesta (mantiene o concede). Todo queda registrado como mensajes.
"""
from __future__ import annotations

from typing import Any

from ..models import AgentMessage, AgentName, AgentOpinion, MessageType, Stance
from .base_agent import BaseAgent

INSTRUCTIONS = (
    "Resume en 2-3 frases si la postura técnica es coherente con el riesgo y los indicadores, "
    "y en caso de discrepancia enumera las objeciones que ya figuran en `counterarguments`. "
    "No introduzcas objeciones nuevas ni números ausentes."
)


def find_counterarguments(tech: dict[str, Any], risk: dict[str, Any]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    stance = tech.get("stance")
    tf = tech.get("facts", {})
    rsi = tf.get("rsi_14")
    ret20 = tf.get("return_20d")
    conf = float(tech.get("confidence") or 0)
    level = risk.get("risk_level")

    if stance == Stance.ALCISTA.value and rsi is not None and rsi > 70:
        out.append({"code": "rsi_overbought", "text": f"RSI14 de {rsi} está en sobrecompra; la continuidad alcista es dudosa."})
    if stance == Stance.BAJISTA.value and rsi is not None and rsi < 30:
        out.append({"code": "rsi_oversold", "text": f"RSI14 de {rsi} está en sobreventa; la presión bajista puede estar agotada."})
    if stance != Stance.NEUTRAL.value and conf < 0.5:
        out.append({"code": "low_confidence", "text": f"La confianza técnica ({conf}) es baja para sostener {stance}."})
    if stance == Stance.ALCISTA.value and level == "ALTO":
        out.append({"code": "high_risk", "text": "Un nivel de riesgo ALTO no es compatible con una señal de compra."})
    if stance == Stance.ALCISTA.value and ret20 is not None and ret20 < -0.05:
        out.append({"code": "negative_momentum", "text": f"El retorno a 20 sesiones ({ret20}) es negativo pese a la lectura alcista."})
    if stance == Stance.BAJISTA.value and ret20 is not None and ret20 > 0.05:
        out.append({"code": "positive_momentum", "text": f"El retorno a 20 sesiones ({ret20}) es positivo pese a la lectura bajista."})
    return out


class SkepticAgent(BaseAgent):
    name = AgentName.SKEPTIC
    description = "Busca contradicciones y reta al agente técnico cuando discrepa."

    async def process(self, message: AgentMessage) -> AgentMessage:
        tech = message.payload.get("technical")
        risk = message.payload.get("risk")
        if not tech or not risk:
            missing = [k for k, v in (("technical", tech), ("risk", risk)) if not v]
            return self.error_reply(message, f"Faltan opiniones previas: {', '.join(missing)}.", code="missing_input")

        counter = find_counterarguments(tech, risk)
        agrees = len(counter) == 0
        suggested = Stance(tech["stance"]) if agrees else Stance.NEUTRAL
        technical_response: dict[str, Any] | None = None

        if not agrees:
            # Discrepancia explícita: se reta al agente técnico y se escucha su respuesta.
            challenge = await self.send(
                AgentName.TECHNICAL,
                MessageType.CHALLENGE,
                {"counterarguments": counter, "original_opinion": tech},
                symbol=message.symbol,
                in_reply_to=message.id,
            )
            if challenge.type != MessageType.ERROR:
                technical_response = challenge.payload

        facts = {
            "technical_stance": tech["stance"],
            "technical_confidence": tech.get("confidence"),
            "rsi_14": tech.get("facts", {}).get("rsi_14"),
            "return_20d": tech.get("facts", {}).get("return_20d"),
            "risk_level": risk.get("risk_level"),
            "counterarguments": [c["text"] for c in counter],
            "agrees": agrees,
            "suggested_stance": suggested.value,
            "technical_response": (technical_response or {}).get("challenge_verdict"),
        }
        fallback = (
            "Sin contradicciones entre técnico y riesgo."
            if agrees
            else "Discrepo: " + " ".join(c["text"] for c in counter)
        )
        explanation = await self.explain(
            symbol=message.symbol, task="skeptic_review", instructions=INSTRUCTIONS, facts=facts, fallback_summary=fallback
        )
        opinion = AgentOpinion(
            agent=self.name,
            stance=suggested,
            agrees=agrees,
            confidence=0.8 if agrees else round(min(1.0, 0.5 + 0.15 * len(counter)), 2),
            facts=facts,
            explanation=explanation,
        )
        payload = opinion.model_dump(mode="json")
        payload["counterarguments"] = counter
        payload["technical_response"] = technical_response
        return self.reply(message, MessageType.CHALLENGE if not agrees else MessageType.OPINION, payload)

    def summarize(self, response: AgentMessage) -> str:
        p = response.payload
        if p.get("agrees"):
            return "de acuerdo con el análisis técnico"
        n = len(p.get("counterarguments", []))
        verdict = (p.get("technical_response") or {}).get("challenge_verdict", "sin respuesta")
        return f"discrepa ({n} objeciones); técnico: {verdict}"
