"""DecisionAgent: agrega las opiniones en una decisión final.

Modo reglas (R0–R5):
- R0  sin datos / sin opinión técnica válida               → NO_ANALIZABLE
- R1  técnico ALCISTA, riesgo ≠ ALTO, escéptico de acuerdo → COMPRA
- R2  técnico BAJISTA, escéptico de acuerdo                → VENTA
- R3  técnico NEUTRAL                                      → ESPERAR
- R4  técnico ALCISTA con riesgo ALTO                      → ESPERAR (veto de riesgo)
- R5  escéptico discrepa (y técnico mantiene o concede)    → ESPERAR

Modo llm: el modelo propone la decisión y la justificación; las reglas vigilan (guardarraíles):
- G0  sin datos → NO_ANALIZABLE sin llamar al modelo
- G1  COMPRA con riesgo ALTO → ESPERAR
- G2  COMPRA sin postura técnica efectiva ALCISTA / VENTA sin BAJISTA → ESPERAR
- G3  escéptico discrepa y el técnico mantiene → confianza ≤ 0.5
- G4  NO_ANALIZABLE con datos disponibles → ESPERAR
"""
from __future__ import annotations

from typing import Any, Optional

from ..models import AgentMessage, AgentName, Decision, MessageType, Stance
from ..providers.llm_provider import LLMError
from ..services.validation import validate_agent_output
from .base_agent import BaseAgent

RULES_INSTRUCTIONS = (
    "Redacta en 2-3 frases la justificación de la decisión final ya tomada por la regla "
    "indicada en `rule`, citando la postura técnica, el nivel de riesgo y la posición del "
    "escéptico. Recuerda que es una señal experimental, no una recomendación."
)

LLM_INSTRUCTIONS = (
    "Eres el agente de decisión. Integra las opiniones de <facts> (técnico, riesgo y escéptico, incluida la "
    "respuesta del técnico al reto si la hubo) en una clasificación final: COMPRA, VENTA, ESPERAR o "
    "NO_ANALIZABLE. Criterios: COMPRA solo con postura técnica alcista efectiva, riesgo no ALTO y sin "
    "objeciones pendientes; VENTA con postura bajista efectiva y sin objeciones pendientes; en cualquier otro "
    "caso ESPERAR. La confianza debe reflejar el acuerdo entre agentes. En `key_factors` enumera los 2-4 "
    "factores decisivos. Es una señal experimental derivada de datos históricos, no una recomendación."
)

DECISION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "decision": {"type": "string", "enum": ["COMPRA", "VENTA", "ESPERAR", "NO_ANALIZABLE"]},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "rationale": {"type": "string"},
        "key_factors": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["decision", "confidence", "rationale", "key_factors"],
    "additionalProperties": False,
}

RISK_FACTOR = {"BAJO": 1.0, "MEDIO": 0.85, "ALTO": 0.6}


def effective_technical(tech: Optional[dict], skeptic: Optional[dict]) -> tuple[Optional[Stance], float]:
    """Postura técnica efectiva: la revisada tras el reto, si la hubo."""
    if not tech or tech.get("stance") is None:
        return None, 0.0
    revised = (skeptic or {}).get("technical_response") or {}
    stance = Stance(revised.get("stance") or tech["stance"])
    conf = float(revised.get("confidence", tech.get("confidence", 0.0)))
    return stance, conf


def decide(tech: Optional[dict], risk: Optional[dict], skeptic: Optional[dict], error: Optional[str]) -> dict[str, Any]:
    if error or not tech or tech.get("stance") is None:
        return {"decision": Decision.NO_ANALIZABLE.value, "confidence": 0.0, "rule": "R0: datos insuficientes o análisis técnico no disponible"}

    stance, t_conf = effective_technical(tech, skeptic)
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
    description = "Agrega opiniones → COMPRA / VENTA / ESPERAR / NO_ANALIZABLE (reglas o LLM con guardarraíles)."

    async def process(self, message: AgentMessage) -> AgentMessage:
        p = message.payload
        tech, risk, skeptic, error = p.get("technical"), p.get("risk"), p.get("skeptic"), p.get("error")
        reference = decide(tech, risk, skeptic, error)

        # G0 / R0: sin datos no hay nada que razonar ni explicar (no se llama al modelo).
        if reference["decision"] == Decision.NO_ANALIZABLE.value:
            summary = f"NO_ANALIZABLE por la regla '{reference['rule']}'." + (f" Motivo: {error}" if error else "")
            return self._reply(message, reference, rationale=summary, generated_by="rules", caveats=["No se dispone de datos suficientes; no se emite señal."], warnings=[], mode="rules", facts=self._facts(tech, risk, skeptic, error, reference), guardrails=[])

        if self.llm_mode:
            try:
                return await self._decide_llm(message, tech, risk, skeptic, reference)
            except LLMError as e:
                return await self._decide_rules(message, tech, risk, skeptic, error, reference, fallback_note=f"Modo LLM no disponible ({e}); se usó el modo reglas.")
        return await self._decide_rules(message, tech, risk, skeptic, error, reference)

    # ---------------------------------------------------------------- helpers
    @staticmethod
    def _facts(tech, risk, skeptic, error, outcome) -> dict[str, Any]:
        return {
            **outcome,
            "technical_stance": (tech or {}).get("stance"),
            "technical_confidence": (tech or {}).get("confidence"),
            "technical_revised_stance": ((skeptic or {}).get("technical_response") or {}).get("stance"),
            "risk_level": (risk or {}).get("risk_level"),
            "skeptic_agrees": (skeptic or {}).get("agrees"),
            "technical_challenge_verdict": ((skeptic or {}).get("technical_response") or {}).get("challenge_verdict"),
            "error": error,
        }

    def _reply(self, message, outcome, *, rationale, generated_by, caveats, warnings, mode, facts, guardrails, rule_reference=None) -> AgentMessage:
        return self.reply(
            message,
            MessageType.DECISION,
            {
                **outcome,
                "rationale": rationale,
                "generated_by": generated_by,
                "caveats": caveats,
                "validation_warnings": warnings,
                "mode": mode,
                "guardrails": guardrails,
                "rule_reference": rule_reference or {},
                "facts": facts,
            },
        )

    # ------------------------------------------------------------------ reglas
    async def _decide_rules(self, message, tech, risk, skeptic, error, outcome, fallback_note: str | None = None) -> AgentMessage:
        facts = self._facts(tech, risk, skeptic, error, outcome)
        fallback = f"{outcome['decision']} por la regla '{outcome['rule']}'."
        explanation = await self.explain(
            symbol=message.symbol, task="decision_rationale", instructions=RULES_INSTRUCTIONS, facts=facts, fallback_summary=fallback
        )
        if fallback_note:
            explanation.validation_warnings.insert(0, fallback_note)
        return self._reply(message, outcome, rationale=explanation.summary, generated_by=explanation.generated_by, caveats=explanation.caveats,
                           warnings=explanation.validation_warnings, mode="rules_fallback" if fallback_note else "rules", facts=facts, guardrails=[])

    # --------------------------------------------------------------------- llm
    async def _decide_llm(self, message, tech, risk, skeptic, reference) -> AgentMessage:
        symbol = message.symbol
        eff_stance, eff_conf = effective_technical(tech, skeptic)
        tr = (skeptic or {}).get("technical_response") or {}
        facts = {
            "technical": {
                "stance": tech.get("stance"), "confidence": tech.get("confidence"),
                "summary": (tech.get("explanation") or {}).get("summary"),
                "evidence": tech.get("evidence", []),
            },
            "technical_after_challenge": {
                "verdict": tr.get("challenge_verdict"), "stance": tr.get("stance"), "confidence": tr.get("confidence"), "reply": tr.get("note"),
            } if tr else None,
            "risk": {
                "risk_level": (risk or {}).get("risk_level"), "confidence": (risk or {}).get("confidence"),
                "summary": ((risk or {}).get("explanation") or {}).get("summary"),
                "metrics": {k: v for k, v in ((risk or {}).get("facts") or {}).items() if k in ("annualized_volatility", "max_drawdown", "atr_pct", "bars_used")},
            } if risk else None,
            "skeptic": {
                "agrees": (skeptic or {}).get("agrees"), "counterarguments": (skeptic or {}).get("counterarguments", []),
                "suggested_stance": (skeptic or {}).get("suggested_stance") or (skeptic or {}).get("stance"),
                "summary": ((skeptic or {}).get("explanation") or {}).get("summary"),
            } if skeptic else None,
        }
        output, known, _ = await self.run_agent_loop(
            symbol=symbol, task="decision", instructions=LLM_INSTRUCTIONS, facts=facts, tools=[], schema=DECISION_SCHEMA
        )
        clean, warnings, hard = validate_agent_output(
            output, known, enum_fields={"decision": [d.value for d in Decision]}, text_fields=("rationale",), list_fields=("key_factors",)
        )
        await self.warn(symbol, "decision", warnings + hard, discarded=bool(hard))
        if hard:
            raise LLMError("; ".join(hard))

        decision = Decision(clean["decision"])
        confidence = clean["confidence"]
        guardrails: list[dict[str, Any]] = []
        level = (risk or {}).get("risk_level")
        agrees = bool((skeptic or {}).get("agrees", True))
        maintained = tr.get("challenge_verdict") == "maintains"

        async def apply(rule: str, new_decision: Optional[Decision], new_conf: Optional[float], reason: str) -> None:
            nonlocal decision, confidence
            before = {"decision": decision.value, "confidence": confidence}
            if new_decision is not None:
                decision = new_decision
            if new_conf is not None:
                confidence = round(min(confidence, new_conf), 2)
            after = {"decision": decision.value, "confidence": confidence}
            guardrails.append({"rule": rule, "before": before, "after": after, "reason": reason})
            await self.guardrail(symbol, rule, before=before, after=after, reason=reason)

        if decision == Decision.COMPRA and level == "ALTO":
            await apply("G1: veto por riesgo ALTO", Decision.ESPERAR, 0.6, "No se emite COMPRA con riesgo ALTO.")
        if decision == Decision.COMPRA and eff_stance != Stance.ALCISTA:
            await apply("G2: decisión sin respaldo de la postura técnica", Decision.ESPERAR, 0.5, f"COMPRA exige postura técnica efectiva ALCISTA (actual: {eff_stance.value if eff_stance else 'ninguna'}).")
        if decision == Decision.VENTA and eff_stance != Stance.BAJISTA:
            await apply("G2: decisión sin respaldo de la postura técnica", Decision.ESPERAR, 0.5, f"VENTA exige postura técnica efectiva BAJISTA (actual: {eff_stance.value if eff_stance else 'ninguna'}).")
        if decision in (Decision.COMPRA, Decision.VENTA) and not agrees and maintained and confidence > 0.5:
            await apply("G3: discrepancia no resuelta", None, 0.5, "El escéptico discrepa y el técnico mantiene: confianza acotada a 0.5.")
        if decision == Decision.NO_ANALIZABLE:
            await apply("G4: NO_ANALIZABLE con datos disponibles", Decision.ESPERAR, 0.4, "Hay datos y opiniones; la señal prudente es ESPERAR.")

        outcome = {"decision": decision.value, "confidence": confidence, "rule": "LLM" + (" + " + ", ".join(g["rule"].split(":")[0] for g in guardrails) if guardrails else "")}
        facts_out = self._facts(tech, risk, skeptic, None, outcome)
        facts_out["effective_technical_stance"] = eff_stance.value if eff_stance else None
        facts_out["effective_technical_confidence"] = eff_conf
        facts_out["key_factors"] = clean.get("key_factors", [])
        facts_out["rule_decision"] = reference["decision"]
        facts_out["rule_applied_by_rules_mode"] = reference["rule"]

        rationale = clean["rationale"]
        if "rationale" in clean["_ungrounded"] or not rationale:
            rationale = f"{decision.value} (confianza {confidence}). Factores: " + "; ".join(clean.get("key_factors", [])[:4] or ["sin factores citados"]) + "."
            warnings.append("Justificación del modelo sustituida por los factores clave validados.")
        if guardrails:
            rationale += " Guardarraíles aplicados: " + "; ".join(g["rule"] for g in guardrails) + "."

        return self._reply(message, outcome, rationale=rationale, generated_by=self.ctx.llm.name, caveats=["Señal experimental derivada de datos históricos; no es una recomendación."],
                           warnings=warnings, mode="llm", facts=facts_out, guardrails=guardrails,
                           rule_reference={"decision": reference["decision"], "confidence": reference["confidence"], "rule": reference["rule"]})

    def summarize(self, response: AgentMessage) -> str:
        p = response.payload
        ref = (p.get("rule_reference") or {}).get("decision")
        ref_txt = f" · reglas: {ref}" if ref and ref != p.get("decision") else ""
        return f"{p.get('decision')} (conf. {p.get('confidence')}) — {p.get('rule')}{ref_txt}"
