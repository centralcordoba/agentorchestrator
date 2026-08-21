"""SkepticAgent: busca contradicciones entre las opiniones técnica y de riesgo.

Si discrepa, envía un CHALLENGE directamente al TechnicalAgent y recoge su respuesta
(mantiene o concede). Todo queda registrado como mensajes.

- Modo reglas: las objeciones salen de comprobaciones fijas (RSI extremo, confianza baja,
  riesgo alto, momento contrario).
- Modo llm: el modelo revisa ambas opiniones y, si discrepa, usa la herramienta
  `challenge_technical`, que envía el reto real al agente técnico y devuelve su respuesta.
"""
from __future__ import annotations

from typing import Any

from ..models import AgentMessage, AgentName, AgentOpinion, LLMExplanation, MessageType, Stance
from ..providers.llm_provider import LLMError, ToolSpec
from ..services.validation import validate_agent_output
from .base_agent import BaseAgent, Tool

RULES_INSTRUCTIONS = (
    "Resume en 2-3 frases si la postura técnica es coherente con el riesgo y los indicadores, "
    "y en caso de discrepancia enumera las objeciones que ya figuran en `counterarguments`. "
    "No introduzcas objeciones nuevas ni números ausentes."
)

LLM_INSTRUCTIONS = (
    "Eres el agente escéptico: tu trabajo es encontrar contradicciones, no repetir el análisis. Revisa la "
    "opinión técnica y la de riesgo en <facts>. Busca: postura alcista con RSI14 >70 o bajista con RSI14 <30; "
    "confianza técnica <0.5 sosteniendo una postura no neutral; señal alcista con riesgo ALTO; momento a 20 "
    "sesiones contrario a la postura; evidencia que no respalda la conclusión. Si encuentras objeciones "
    "relevantes, DEBES enviarlas al analista técnico con `challenge_technical` y leer su respuesta antes de "
    "concluir. Responde `agrees: true` solo si no hay objeciones de peso. `suggested_stance` es la postura "
    "que tú considerarías prudente."
)

SKEPTIC_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "agrees": {"type": "boolean"},
        "counterarguments": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"code": {"type": "string"}, "text": {"type": "string"}},
                "required": ["code", "text"],
                "additionalProperties": False,
            },
        },
        "suggested_stance": {"type": "string", "enum": ["ALCISTA", "BAJISTA", "NEUTRAL"]},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "summary": {"type": "string"},
        "caveats": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["agrees", "counterarguments", "suggested_stance", "confidence", "summary", "caveats"],
    "additionalProperties": False,
}


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
        if self.llm_mode:
            try:
                return await self._review_llm(message, tech, risk)
            except LLMError as e:
                return await self._review_rules(message, tech, risk, fallback_note=f"Modo LLM no disponible ({e}); se usó el modo reglas.")
        return await self._review_rules(message, tech, risk)

    async def _challenge(self, message: AgentMessage, tech: dict[str, Any], counter: list[dict[str, str]]) -> dict[str, Any] | None:
        """Reto real al agente técnico (mensaje CHALLENGE visible en la traza)."""
        reply = await self.send(
            AgentName.TECHNICAL,
            MessageType.CHALLENGE,
            {"counterarguments": counter, "original_opinion": tech},
            symbol=message.symbol,
            in_reply_to=message.id,
        )
        return reply.payload if reply.type != MessageType.ERROR else None

    # ------------------------------------------------------------------ reglas
    async def _review_rules(self, message: AgentMessage, tech: dict[str, Any], risk: dict[str, Any], fallback_note: str | None = None) -> AgentMessage:
        counter = find_counterarguments(tech, risk)
        agrees = len(counter) == 0
        suggested = Stance(tech["stance"]) if agrees else Stance.NEUTRAL
        technical_response = await self._challenge(message, tech, counter) if not agrees else None

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
        fallback = "Sin contradicciones entre técnico y riesgo." if agrees else "Discrepo: " + " ".join(c["text"] for c in counter)
        explanation = await self.explain(
            symbol=message.symbol, task="skeptic_review", instructions=RULES_INSTRUCTIONS, facts=facts, fallback_summary=fallback
        )
        if fallback_note:
            explanation.validation_warnings.insert(0, fallback_note)
        return self._reply(message, agrees, suggested, 0.8 if agrees else round(min(1.0, 0.5 + 0.15 * len(counter)), 2), facts, explanation, counter, technical_response, mode="rules_fallback" if fallback_note else "rules")

    # --------------------------------------------------------------------- llm
    async def _review_llm(self, message: AgentMessage, tech: dict[str, Any], risk: dict[str, Any]) -> AgentMessage:
        symbol = message.symbol
        facts = {
            "technical": {
                "stance": tech.get("stance"),
                "confidence": tech.get("confidence"),
                "summary": (tech.get("explanation") or {}).get("summary"),
                "evidence": tech.get("evidence", []),
                "indicators": {k: v for k, v in (tech.get("facts") or {}).items() if not k.startswith("rule_")},
            },
            "risk": {
                "risk_level": risk.get("risk_level"),
                "confidence": risk.get("confidence"),
                "summary": (risk.get("explanation") or {}).get("summary"),
                "metrics": {k: v for k, v in (risk.get("facts") or {}).items() if k not in ("thresholds", "rule_risk_level")},
            },
        }
        state: dict[str, Any] = {"technical_response": None, "challenges": 0, "counter": []}

        async def challenge_technical(args: dict[str, Any]) -> dict[str, Any]:
            if state["challenges"] >= 1:
                return {"error": "Solo se permite un reto por revisión."}
            raw = args.get("counterarguments") or []
            counter = [
                {"code": str(c.get("code", "objection")).strip()[:40], "text": str(c.get("text", "")).strip()[:300]}
                for c in raw if isinstance(c, dict) and c.get("text")
            ]
            if not counter:
                return {"error": "Debes indicar al menos una objeción con 'code' y 'text'."}
            state["challenges"] += 1
            state["counter"] = counter
            response = await self._challenge(message, tech, counter)
            state["technical_response"] = response
            if response is None:
                return {"error": "El agente técnico no respondió al reto."}
            return {
                "technical_verdict": response.get("challenge_verdict"),
                "technical_revised_stance": response.get("stance"),
                "technical_revised_confidence": response.get("confidence"),
                "technical_reply": response.get("note"),
            }

        tools = [
            Tool(
                ToolSpec(
                    name="challenge_technical",
                    description="Envía objeciones al analista técnico y devuelve su respuesta (mantiene o concede, con postura y confianza revisadas).",
                    parameters={
                        "type": "object",
                        "properties": {
                            "counterarguments": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {"code": {"type": "string"}, "text": {"type": "string"}},
                                    "required": ["code", "text"],
                                    "additionalProperties": False,
                                },
                            }
                        },
                        "required": ["counterarguments"],
                        "additionalProperties": False,
                    },
                ),
                challenge_technical,
            )
        ]
        output, known, tool_log = await self.run_agent_loop(
            symbol=symbol, task="skeptic_review", instructions=LLM_INSTRUCTIONS, facts=facts, tools=tools, schema=SKEPTIC_SCHEMA
        )
        clean, warnings, hard = validate_agent_output(
            output, known, enum_fields={"suggested_stance": [s.value for s in Stance]}, bool_fields=("agrees",), list_fields=("caveats",)
        )
        await self.warn(symbol, "skeptic_review", warnings + hard, discarded=bool(hard))
        if hard:
            raise LLMError("; ".join(hard))

        agrees = clean["agrees"]
        raw_counter = output.get("counterarguments") or []
        counter = [
            {"code": str(c.get("code", "objection")).strip()[:40], "text": str(c.get("text", "")).strip()[:300]}
            for c in raw_counter if isinstance(c, dict) and c.get("text")
        ] or state["counter"]
        if not agrees and not counter:
            await self.guardrail(symbol, "S1: discrepa sin objeciones", before=False, after=True, reason="Una discrepancia exige al menos una objeción explícita.")
            agrees = True
        if not agrees and not self.tool_called(tool_log, "challenge_technical"):
            # El modelo discrepó pero no retó: ejecutamos el reto para que la discrepancia sea real.
            warnings.append("El escéptico discrepó sin retar al técnico; el reto se envió automáticamente.")
            state["technical_response"] = await self._challenge(message, tech, counter)
        suggested = Stance(clean["suggested_stance"])
        technical_response = state["technical_response"]

        facts_out = {
            "technical_stance": tech.get("stance"),
            "technical_confidence": tech.get("confidence"),
            "rsi_14": (tech.get("facts") or {}).get("rsi_14"),
            "return_20d": (tech.get("facts") or {}).get("return_20d"),
            "risk_level": risk.get("risk_level"),
            "counterarguments": [c["text"] for c in counter],
            "agrees": agrees,
            "suggested_stance": suggested.value,
            "technical_response": (technical_response or {}).get("challenge_verdict"),
            "rule_counterargument_codes": [c["code"] for c in find_counterarguments(tech, risk)],
        }
        summary = clean["summary"]
        if "summary" in clean["_ungrounded"] or not summary:
            summary = ("Sin objeciones de peso." if agrees else "Discrepo: " + " ".join(c["text"] for c in counter))
            warnings.append("Resumen del modelo sustituido por las objeciones validadas.")
        explanation = LLMExplanation(
            summary=summary, facts_used=["technical", "risk"], caveats=clean.get("caveats", []),
            generated_by=self.ctx.llm.name, validation_warnings=warnings,
        )
        return self._reply(message, agrees, suggested, clean["confidence"], facts_out, explanation, counter, technical_response, mode="llm",
                           rule_reference={"agrees": not facts_out["rule_counterargument_codes"], "codes": facts_out["rule_counterargument_codes"]})

    # ---------------------------------------------------------------- común
    def _reply(self, message, agrees, suggested, confidence, facts, explanation, counter, technical_response, *, mode, rule_reference=None) -> AgentMessage:
        opinion = AgentOpinion(
            agent=self.name, stance=suggested, agrees=agrees, confidence=confidence, facts=facts,
            explanation=explanation, mode=mode, rule_reference=rule_reference or {},
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
