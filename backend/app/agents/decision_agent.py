"""DecisionAgent: agrega las opiniones en una decisión final con reglas explícitas.

Reglas (en orden):
- R0  sin datos / sin opinión técnica válida               → NO_ANALIZABLE
- R1  técnico ALCISTA, riesgo ≠ ALTO, escéptico de acuerdo → COMPRA
- R2  técnico BAJISTA, escéptico de acuerdo                → VENTA
- R3  técnico NEUTRAL                                      → ESPERAR
- R4  técnico ALCISTA con riesgo ALTO                      → ESPERAR (veto de riesgo)
- R5  escéptico discrepa (y técnico mantiene o concede)    → ESPERAR
"""
from __future__ import annotations

from typing import Any, Optional

from ..models import AgentMessage, AgentName, Decision, MessageType, Stance
from .base_agent import BaseAgent

INSTRUCTIONS = (
    "Redacta en 2-3 frases la justificación de la decisión final ya tomada por la regla "
    "indicada en `rule`, citando la postura técnica, el nivel de riesgo y la posición del "
    "escéptico. Recuerda que es una señal experimental, no una recomendación."
)

RISK_FACTOR = {"BAJO": 1.0, "MEDIO": 0.85, "ALTO": 0.6}


def decide(tech: Optional[dict], risk: Optional[dict], skeptic: Optional[dict], error: Optional[str]) -> dict[str, Any]:
    if error or not tech or tech.get("stance") is None:
        return {
            "decision": Decision.NO_ANALIZABLE.value,
            "confidence": 0.0,
            "rule": "R0: datos insuficientes o análisis técnico no disponible",
        }

    # Si el técnico respondió a un reto, usamos su postura revisada.
    revised = ((skeptic or {}).get("technical_response") or {})
    stance = Stance(revised.get("stance") or tech["stance"])
    t_conf = float(revised.get("confidence", tech.get("confidence", 0.0)))
    level = (risk or {}).get("risk_level") or "MEDIO"
    agrees = bool((skeptic or {}).get("agrees", True))
    r_factor = RISK_FACTOR.get(level, 0.85)

    if stance == Stance.ALCISTA and level != "ALTO" and agrees:
        return {"decision": Decision.COMPRA.value, "confidence": round(t_conf * r_factor, 2), "rule": "R1: técnico alcista, riesgo aceptable, sin objeciones"}
    if stance == Stance.BAJISTA and agrees:
        return {"decision": Decision.VENTA.value, "confidence": round(t_conf * r_factor, 2), "rule": "R2: técnico bajista sin objeciones"}
    if stance == Stance.NEUTRAL:
        return {"decision": Decision.ESPERAR.value, "confidence": round(1 - t_conf, 2), "rule": "R3: lectura técnica neutral"}
    if stance == Stance.ALCISTA and level == "ALTO":
        return {"decision": Decision.ESPERAR.value, "confidence": 0.6, "rule": "R4: veto por riesgo ALTO"}
    return {"decision": Decision.ESPERAR.value, "confidence": 0.5, "rule": "R5: discrepancia del escéptico no resuelta"}


class DecisionAgent(BaseAgent):
    name = AgentName.DECISION
    description = "Agrega opiniones con reglas explícitas → COMPRA / VENTA / ESPERAR / NO_ANALIZABLE."

    async def process(self, message: AgentMessage) -> AgentMessage:
        p = message.payload
        tech, risk, skeptic = p.get("technical"), p.get("risk"), p.get("skeptic")
        error = p.get("error")

        outcome = decide(tech, risk, skeptic, error)
        facts = {
            **outcome,
            "technical_stance": (tech or {}).get("stance"),
            "technical_confidence": (tech or {}).get("confidence"),
            # Si el técnico respondió a un reto del escéptico, esta es la postura efectiva.
            "technical_revised_stance": ((skeptic or {}).get("technical_response") or {}).get("stance"),
            "risk_level": (risk or {}).get("risk_level"),
            "skeptic_agrees": (skeptic or {}).get("agrees"),
            "technical_challenge_verdict": ((skeptic or {}).get("technical_response") or {}).get("challenge_verdict"),
            "error": error,
        }
        fallback = f"{outcome['decision']} por la regla '{outcome['rule']}'."
        if error:
            fallback += f" Motivo: {error}"

        if outcome["decision"] == Decision.NO_ANALIZABLE.value:
            # Sin datos no hay nada que explicar: no se llama al LLM (evita inventar contexto).
            summary = fallback
            generated_by = "rules"
            caveats = ["No se dispone de datos suficientes; no se emite señal."]
            warnings: list[str] = []
        else:
            explanation = await self.explain(
                symbol=message.symbol, task="decision_rationale", instructions=INSTRUCTIONS, facts=facts, fallback_summary=fallback
            )
            summary, generated_by, caveats, warnings = (
                explanation.summary,
                explanation.generated_by,
                explanation.caveats,
                explanation.validation_warnings,
            )

        return self.reply(
            message,
            MessageType.DECISION,
            {
                **outcome,
                "rationale": summary,
                "generated_by": generated_by,
                "caveats": caveats,
                "validation_warnings": warnings,
                "facts": facts,
            },
        )

    def summarize(self, response: AgentMessage) -> str:
        p = response.payload
        return f"{p.get('decision')} (conf. {p.get('confidence')}) — {p.get('rule')}"
