"""TechnicalAgent: indicadores técnicos → postura ALCISTA / BAJISTA / NEUTRAL.

- Modo reglas: la postura sale de una puntuación determinista; el LLM solo redacta.
- Modo llm: el modelo debe invocar `compute_indicators` y fijar postura, confianza y
  evidencia. Guardarraíl: una postura opuesta a la de las reglas con menos de dos
  evidencias se rebaja a NEUTRAL.

También responde a los CHALLENGE del escéptico (mantiene o concede).
"""
from __future__ import annotations

from typing import Any

from ..models import AgentMessage, AgentName, AgentOpinion, Evidence, LLMExplanation, MessageType, Stance
from ..providers.llm_provider import LLMError, ToolSpec
from ..services import indicators as ind
from ..services.validation import evidence_summary, validate_agent_output
from .base_agent import BaseAgent, Tool

RULES_INSTRUCTIONS = (
    "Explica en 2-3 frases qué dicen los indicadores (medias móviles, RSI, MACD, retorno a 20 "
    "sesiones) y por qué la regla ha fijado la postura indicada en `stance`. Menciona solo "
    "números presentes en los hechos."
)

LLM_INSTRUCTIONS = (
    "Eres el analista técnico. Debes fijar una postura (ALCISTA, BAJISTA o NEUTRAL) sobre la serie de "
    "precios descrita en <facts>. Primero invoca la herramienta `compute_indicators` para obtener los "
    "indicadores calculados (no los estimes). Después razona: tendencia (cierre vs SMA50, SMA20 vs SMA50), "
    "momento (histograma MACD, retorno a 20 sesiones) y sobrecompra/sobreventa (RSI14 >70 / <30). "
    "Cita cada indicador usado en `evidence` con su nombre exacto. Con señales mixtas responde NEUTRAL."
)

CHALLENGE_INSTRUCTIONS = (
    "El agente escéptico ha retado tu postura con las objeciones de `counterarguments`. Revisa tu "
    "`original_opinion` a la luz de ellas. Si las objeciones son pertinentes, responde `concedes` y rebaja "
    "tu confianza (y la postura a NEUTRAL si ya no se sostiene); si no lo son, responde `maintains` y "
    "explica por qué en `reply`, citando solo indicadores presentes en los hechos."
)

TECH_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "stance": {"type": "string", "enum": ["ALCISTA", "BAJISTA", "NEUTRAL"]},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "evidence": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"fact": {"type": "string"}, "observation": {"type": "string"}},
                "required": ["fact", "observation"],
                "additionalProperties": False,
            },
        },
        "summary": {"type": "string"},
        "caveats": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["stance", "confidence", "evidence", "summary", "caveats"],
    "additionalProperties": False,
}

CHALLENGE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": ["maintains", "concedes"]},
        "stance": {"type": "string", "enum": ["ALCISTA", "BAJISTA", "NEUTRAL"]},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "reply": {"type": "string"},
    },
    "required": ["verdict", "stance", "confidence", "reply"],
    "additionalProperties": False,
}

CONCEDE_CODES = {"rsi_overbought", "rsi_oversold", "low_confidence"}


# --------------------------------------------------------------------------- cálculo
def indicator_facts(closes: list[float]) -> dict[str, Any]:
    """Solo números: lo que devuelve la herramienta `compute_indicators`."""
    macd = ind.macd(closes)
    return {
        "bars_used": len(closes),
        "last_close": round(closes[-1], 4),
        "sma_20": ind.round_or_none(ind.sma(closes, 20), 4),
        "sma_50": ind.round_or_none(ind.sma(closes, 50), 4),
        "rsi_14": ind.round_or_none(ind.rsi(closes, 14), 2),
        "macd_histogram": ind.round_or_none(macd["histogram"] if macd else None, 4),
        "return_20d": ind.round_or_none(ind.pct_change(closes, 20), 4),
    }


def rule_stance(f: dict[str, Any]) -> dict[str, Any]:
    """Postura determinista a partir de los indicadores (referencia y guardarraíl)."""
    last, sma20, sma50, rsi14, hist = f.get("last_close"), f.get("sma_20"), f.get("sma_50"), f.get("rsi_14"), f.get("macd_histogram")
    score = 0
    reasons: list[str] = []
    evidence: list[dict[str, str]] = []
    if sma50 is not None and last is not None:
        up = last > sma50
        score += 1 if up else -1
        reasons.append("cierre por encima de la SMA50" if up else "cierre por debajo de la SMA50")
        evidence.append({"fact": "sma_50", "observation": f"el cierre {last} está {'por encima' if up else 'por debajo'} de la SMA50 {sma50}"})
    if sma20 is not None and sma50 is not None:
        up = sma20 > sma50
        score += 1 if up else -1
        reasons.append("SMA20 por encima de SMA50" if up else "SMA20 por debajo de SMA50")
        evidence.append({"fact": "sma_20", "observation": f"SMA20 {sma20} {'>' if up else '<'} SMA50 {sma50}"})
    if rsi14 is not None:
        if rsi14 < 30:
            score += 1
            reasons.append("RSI en sobreventa (<30)")
            evidence.append({"fact": "rsi_14", "observation": f"RSI14 {rsi14} en sobreventa"})
        elif rsi14 > 70:
            score -= 1
            reasons.append("RSI en sobrecompra (>70)")
            evidence.append({"fact": "rsi_14", "observation": f"RSI14 {rsi14} en sobrecompra"})
    if hist is not None:
        pos = hist > 0
        score += 1 if pos else -1
        reasons.append("histograma MACD positivo" if pos else "histograma MACD negativo")
        evidence.append({"fact": "macd_histogram", "observation": f"histograma MACD {hist} {'positivo' if pos else 'negativo'}"})

    stance = Stance.ALCISTA if score >= 2 else Stance.BAJISTA if score <= -2 else Stance.NEUTRAL
    return {
        "score": score,
        "rule_reasons": reasons,
        "stance": stance.value,
        "confidence": round(min(1.0, abs(score) / 4), 2),
        "evidence": evidence,
    }


def compute_technical_facts(closes: list[float]) -> dict[str, Any]:
    """Compatibilidad (modo reglas y scripts): indicadores + postura por reglas."""
    facts = indicator_facts(closes)
    ref = rule_stance(facts)
    return {**facts, "score": ref["score"], "rule_reasons": ref["rule_reasons"], "stance": ref["stance"], "confidence": ref["confidence"]}


# ---------------------------------------------------------------------------- agente
class TechnicalAgent(BaseAgent):
    name = AgentName.TECHNICAL
    description = "Indicadores técnicos (SMA, RSI, MACD) → postura alcista/bajista/neutral."

    async def process(self, message: AgentMessage) -> AgentMessage:
        if message.type == MessageType.CHALLENGE:
            if self.llm_mode:
                try:
                    return await self._answer_challenge_llm(message)
                except LLMError:
                    pass  # ya registrado en la traza → respuesta por reglas
            return self._answer_challenge_rules(message)

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
        if self.llm_mode:
            try:
                return await self._analyze_llm(message, closes)
            except LLMError as e:
                return await self._analyze_rules(message, closes, fallback_note=f"Modo LLM no disponible ({e}); se usó el modo reglas.")
        return await self._analyze_rules(message, closes)

    # ------------------------------------------------------------------ reglas
    async def _analyze_rules(self, message: AgentMessage, closes: list[float], fallback_note: str | None = None) -> AgentMessage:
        facts = compute_technical_facts(closes)
        fallback = (
            f"Postura {facts['stance']} (puntuación {facts['score']}): {', '.join(facts['rule_reasons'])}. "
            f"Cierre {facts['last_close']}, RSI14 {facts['rsi_14']}."
        )
        explanation = await self.explain(
            symbol=message.symbol, task="technical_explanation", instructions=RULES_INSTRUCTIONS, facts=facts, fallback_summary=fallback
        )
        if fallback_note:
            explanation.validation_warnings.insert(0, fallback_note)
        opinion = AgentOpinion(
            agent=self.name,
            stance=Stance(facts["stance"]),
            confidence=facts["confidence"],
            facts=facts,
            explanation=explanation,
            mode="rules_fallback" if fallback_note else "rules",
            evidence=[Evidence(**e) for e in rule_stance(facts)["evidence"]],
        )
        return self.reply(message, MessageType.OPINION, opinion.model_dump(mode="json"))

    def _answer_challenge_rules(self, message: AgentMessage) -> AgentMessage:
        original = message.payload.get("original_opinion", {})
        counter = message.payload.get("counterarguments", [])
        facts = dict(original.get("facts", {}))
        stance = Stance(original.get("stance", Stance.NEUTRAL.value))
        confidence = float(original.get("confidence", 0.0))

        conceded = [c for c in counter if c.get("code") in CONCEDE_CODES]
        if conceded:
            new_confidence = round(max(0.0, confidence - 0.25 * len(conceded)), 2)
            new_stance = stance if new_confidence >= 0.5 else Stance.NEUTRAL
            verdict = "concedes"
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
                "mode": "rules",
                "facts": facts,
            },
        )

    # --------------------------------------------------------------------- llm
    async def _analyze_llm(self, message: AgentMessage, closes: list[float]) -> AgentMessage:
        symbol = message.symbol
        series = self.ctx.data[message.payload["data_ref"]]
        facts = {
            "symbol": series.symbol,
            "data_ref": message.payload["data_ref"],
            **{k: v for k, v in series.summary().items() if k != "symbol"},
        }
        indicators = indicator_facts(closes)

        async def compute_indicators(_: dict[str, Any]) -> dict[str, Any]:
            return dict(indicators)

        tools = [
            Tool(
                ToolSpec(
                    name="compute_indicators",
                    description="Calcula SMA20, SMA50, RSI14, histograma MACD y retorno a 20 sesiones sobre la serie de precios.",
                    parameters={"type": "object", "properties": {}, "additionalProperties": False},
                ),
                compute_indicators,
            )
        ]
        output, known, tool_log = await self.run_agent_loop(
            symbol=symbol, task="technical_analysis", instructions=LLM_INSTRUCTIONS, facts=facts, tools=tools, schema=TECH_SCHEMA
        )
        if not self.tool_called(tool_log, "compute_indicators"):
            await self.warn(symbol, "technical_analysis", ["El agente fijó postura sin consultar los indicadores; salida descartada."], discarded=True)
            raise LLMError("el modelo no consultó la herramienta compute_indicators")

        clean, warnings, hard = validate_agent_output(
            output, known, enum_fields={"stance": [s.value for s in Stance]}, text_fields=("summary",)
        )
        await self.warn(symbol, "technical_analysis", warnings + hard, discarded=bool(hard))
        if hard:
            raise LLMError("; ".join(hard))

        ref = rule_stance(indicators)
        stance = Stance(clean["stance"])
        confidence = clean["confidence"]
        evidence = clean.get("evidence", [])

        opposite = {Stance.ALCISTA: Stance.BAJISTA, Stance.BAJISTA: Stance.ALCISTA}
        if opposite.get(stance) is not None and opposite[stance].value == ref["stance"] and len(evidence) < 2:
            await self.guardrail(
                symbol, "T1: postura opuesta a las reglas con evidencia insuficiente",
                before=stance.value, after=Stance.NEUTRAL.value,
                reason=f"Las reglas indican {ref['stance']} (puntuación {ref['score']}); el modelo citó {len(evidence)} evidencia(s).",
            )
            stance = Stance.NEUTRAL
            confidence = min(confidence, 0.4)

        summary = clean["summary"]
        if "summary" in clean["_ungrounded"] or not summary:
            summary = evidence_summary(f"Postura {stance.value} (confianza {confidence}).", evidence, known)
            warnings.append("Resumen del modelo sustituido por uno construido con la evidencia validada.")

        opinion_facts = {**indicators, "rule_stance": ref["stance"], "rule_score": ref["score"], "rule_reasons": ref["rule_reasons"]}
        opinion = AgentOpinion(
            agent=self.name,
            stance=stance,
            confidence=confidence,
            facts=opinion_facts,
            explanation=LLMExplanation(
                summary=summary,
                facts_used=[e["fact"] for e in evidence],
                caveats=clean.get("caveats", []),
                generated_by=self.ctx.llm.name,
                validation_warnings=warnings,
            ),
            mode="llm",
            evidence=[Evidence(**e) for e in evidence],
            rule_reference={"stance": ref["stance"], "score": ref["score"], "confidence": ref["confidence"]},
        )
        return self.reply(message, MessageType.OPINION, opinion.model_dump(mode="json"))

    async def _answer_challenge_llm(self, message: AgentMessage) -> AgentMessage:
        original = message.payload.get("original_opinion", {})
        counter = message.payload.get("counterarguments", [])
        facts = {
            "original_opinion": {
                "stance": original.get("stance"),
                "confidence": original.get("confidence"),
                "summary": (original.get("explanation") or {}).get("summary"),
                "evidence": original.get("evidence", []),
            },
            "indicators": {k: v for k, v in (original.get("facts") or {}).items() if not k.startswith("rule_")},
            "counterarguments": counter,
        }
        output, known, _ = await self.run_agent_loop(
            symbol=message.symbol, task="technical_challenge_response", instructions=CHALLENGE_INSTRUCTIONS, facts=facts, tools=[], schema=CHALLENGE_SCHEMA
        )
        clean, warnings, hard = validate_agent_output(
            output, known,
            enum_fields={"verdict": ["maintains", "concedes"], "stance": [s.value for s in Stance]},
            text_fields=("reply",), list_fields=(),
        )
        await self.warn(message.symbol, "technical_challenge_response", warnings + hard, discarded=bool(hard))
        if hard:
            raise LLMError("; ".join(hard))

        orig_stance = Stance(original.get("stance", Stance.NEUTRAL.value))
        orig_conf = float(original.get("confidence", 0.0))
        verdict, stance, confidence = clean["verdict"], Stance(clean["stance"]), clean["confidence"]
        if verdict == "maintains" and stance != orig_stance:
            await self.guardrail(message.symbol, "T2: 'mantiene' pero cambia de postura", before=stance.value, after=orig_stance.value, reason="Mantener implica conservar la postura original.")
            stance = orig_stance
        if verdict == "concedes" and confidence > orig_conf - 0.1:
            new_conf = round(max(0.0, orig_conf - 0.25), 2)
            await self.guardrail(message.symbol, "T3: 'concede' sin rebajar la confianza", before=confidence, after=new_conf, reason="Conceder objeciones exige reducir la confianza.")
            confidence = new_conf
        reply = clean["reply"]
        if "reply" in clean["_ungrounded"]:
            reply = f"{'Concedo' if verdict == 'concedes' else 'Mantengo'} la postura {stance.value} (confianza {confidence})."

        facts_out = dict(original.get("facts", {}))
        facts_out.update({"stance": stance.value, "confidence": confidence, "challenge_verdict": verdict})
        return self.reply(
            message,
            MessageType.OPINION,
            {
                "agent": self.name.value,
                "stance": stance.value,
                "confidence": confidence,
                "challenge_verdict": verdict,
                "note": reply,
                "mode": "llm",
                "facts": facts_out,
            },
        )

    def summarize(self, response: AgentMessage) -> str:
        p = response.payload
        extra = f" ({p['challenge_verdict']})" if p.get("challenge_verdict") else ""
        ref = (p.get("rule_reference") or {}).get("stance")
        ref_txt = f" · reglas: {ref}" if ref and ref != p.get("stance") else ""
        return f"{p.get('stance')} conf. {p.get('confidence')}{extra}{ref_txt}"
