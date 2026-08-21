"""RiskAgent: volatilidad, drawdown y ATR → nivel de riesgo BAJO / MEDIO / ALTO.

Patrón pedagógico clave: si la serie recibida es corta, este agente NO adivina; pide
historial ampliado al MarketDataAgent con un INFO_REQUEST y continúa con la respuesta.

- Modo reglas: el umbral de sesiones dispara la petición y las reglas fijan el nivel.
- Modo llm: el modelo dispone de `compute_risk_metrics` y `request_history`; decide él
  cuándo pedir más datos. Guardarraíl: no puede declarar un riesgo dos niveles por debajo
  del que indican las reglas (se corrige al nivel de las reglas).
"""
from __future__ import annotations

from typing import Any

from ..models import AgentMessage, AgentName, AgentOpinion, Evidence, LLMExplanation, MessageType, RiskLevel
from ..providers.llm_provider import LLMError, ToolSpec
from ..providers.market_data_provider import MarketSeries
from ..services import indicators as ind
from ..services.validation import evidence_summary, validate_agent_output
from .base_agent import BaseAgent, Tool

RULES_INSTRUCTIONS = (
    "Explica en 2-3 frases el perfil de riesgo histórico (volatilidad anualizada, drawdown "
    "máximo, ATR relativo) y por qué la regla asigna el `risk_level` indicado. No cambies el nivel."
)

LLM_INSTRUCTIONS = (
    "Eres el analista de riesgo. Debes asignar un nivel de riesgo (BAJO, MEDIO o ALTO) a la serie descrita "
    "en <facts>. Invoca `compute_risk_metrics` para obtener volatilidad anualizada, drawdown máximo y ATR "
    "relativo (no los estimes). Si `bars_used` es inferior a `min_bars_recommended`, la medición del drawdown "
    "no es fiable: pide historial ampliado con `request_history` (hasta `extended_history_days` días) y vuelve "
    "a calcular. Referencias orientativas: volatilidad >45 % o drawdown peor que −35 % → ALTO; volatilidad "
    "<20 % y drawdown mejor que −15 % → BAJO. Cita cada métrica usada en `evidence` con su nombre exacto."
)

RISK_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "risk_level": {"type": "string", "enum": ["BAJO", "MEDIO", "ALTO"]},
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
    "required": ["risk_level", "confidence", "evidence", "summary", "caveats"],
    "additionalProperties": False,
}

SEVERITY = {"BAJO": 0, "MEDIO": 1, "ALTO": 2}
THRESHOLDS = {"alto_vol": 0.45, "alto_drawdown": -0.35, "bajo_vol": 0.20, "bajo_drawdown": -0.15}


# --------------------------------------------------------------------------- cálculo
def risk_metrics(closes: list[float], highs: list[float], lows: list[float]) -> dict[str, Any]:
    """Solo números: lo que devuelve la herramienta `compute_risk_metrics`."""
    vol = ind.annualized_volatility(closes)
    dd = ind.max_drawdown(closes)
    atr14 = ind.atr(highs, lows, closes, 14)
    last = closes[-1]
    return {
        "bars_used": len(closes),
        "annualized_volatility": ind.round_or_none(vol, 4),
        "max_drawdown": ind.round_or_none(dd, 4),
        "atr_14": ind.round_or_none(atr14, 4),
        "atr_pct": ind.round_or_none((atr14 / last) if (atr14 is not None and last) else None, 4),
    }


def rule_risk_level(m: dict[str, Any]) -> str:
    vol, dd = m.get("annualized_volatility"), m.get("max_drawdown")
    if (vol is not None and vol > THRESHOLDS["alto_vol"]) or (dd is not None and dd < THRESHOLDS["alto_drawdown"]):
        return RiskLevel.ALTO.value
    if (vol is not None and vol < THRESHOLDS["bajo_vol"]) and (dd is not None and dd > THRESHOLDS["bajo_drawdown"]):
        return RiskLevel.BAJO.value
    return RiskLevel.MEDIO.value


def rule_evidence(m: dict[str, Any]) -> list[dict[str, str]]:
    out = []
    if m.get("annualized_volatility") is not None:
        out.append({"fact": "annualized_volatility", "observation": f"volatilidad anualizada {m['annualized_volatility']}"})
    if m.get("max_drawdown") is not None:
        out.append({"fact": "max_drawdown", "observation": f"drawdown máximo {m['max_drawdown']}"})
    if m.get("atr_pct") is not None:
        out.append({"fact": "atr_pct", "observation": f"ATR relativo {m['atr_pct']}"})
    return out


def compute_risk_facts(closes: list[float], highs: list[float], lows: list[float]) -> dict[str, Any]:
    """Compatibilidad (modo reglas y scripts): métricas + nivel por reglas."""
    m = risk_metrics(closes, highs, lows)
    return {**m, "risk_level": rule_risk_level(m), "thresholds": dict(THRESHOLDS)}


RULE_CONFIDENCE = {"BAJO": 0.8, "MEDIO": 0.6, "ALTO": 0.85}


# ---------------------------------------------------------------------------- agente
class RiskAgent(BaseAgent):
    name = AgentName.RISK
    description = "Volatilidad, drawdown y ATR → nivel de riesgo BAJO/MEDIO/ALTO."

    async def process(self, message: AgentMessage) -> AgentMessage:
        data_ref = message.payload.get("data_ref")
        series = self.ctx.data.get(data_ref or "")
        if series is None:
            return self.error_reply(message, f"No encuentro la serie '{data_ref}'.", code="missing_data")
        if self.llm_mode:
            try:
                return await self._analyze_llm(message, series)
            except LLMError as e:
                return await self._analyze_rules(message, series, fallback_note=f"Modo LLM no disponible ({e}); se usó el modo reglas.")
        return await self._analyze_rules(message, series)

    # --------------------------------------------------------- petición de datos
    async def _request_history(self, message: AgentMessage, symbol: str, days: int, reason: str) -> dict[str, Any]:
        """Pide historial ampliado al agente de datos (mensaje visible en la traza)."""
        info = await self.send(
            AgentName.MARKET_DATA,
            MessageType.INFO_REQUEST,
            {"symbol": symbol, "days": days, "reason": reason},
            symbol=message.symbol,
            in_reply_to=message.id,
        )
        if info.type == MessageType.ERROR:
            return {"error": f"No se pudo ampliar el historial: {info.payload.get('reason')}"}
        return {k: v for k, v in info.payload.items() if k in ("data_ref", "bars", "first_date", "last_date", "last_close", "source")}

    # ------------------------------------------------------------------ reglas
    async def _analyze_rules(self, message: AgentMessage, series: MarketSeries, fallback_note: str | None = None) -> AgentMessage:
        min_bars = self.ctx.settings.min_bars_risk
        extended_requested = False
        if len(series.bars) < min_bars:
            extended_requested = True
            info = await self._request_history(
                message, series.symbol, self.ctx.settings.extended_history_days,
                f"Necesito ≥{min_bars} sesiones para drawdown/volatilidad; tengo {len(series.bars)}.",
            )
            if "error" in info:
                return self.error_reply(message, info["error"], code="insufficient_data")
            extended = self.ctx.data.get(info.get("data_ref", ""))
            if extended is None or len(extended.bars) < min_bars:
                got = len(extended.bars) if extended else 0
                return self.error_reply(message, f"El historial ampliado sigue siendo insuficiente ({got} < {min_bars}).", code="insufficient_data")
            series = extended

        facts = compute_risk_facts(series.closes, series.highs, series.lows)
        facts["extended_data_requested"] = extended_requested
        fallback = (
            f"Riesgo {facts['risk_level']}: volatilidad anualizada {facts['annualized_volatility']}, "
            f"drawdown máximo {facts['max_drawdown']}, ATR relativo {facts['atr_pct']} "
            f"sobre {facts['bars_used']} sesiones."
        )
        explanation = await self.explain(
            symbol=message.symbol, task="risk_explanation", instructions=RULES_INSTRUCTIONS, facts=facts, fallback_summary=fallback
        )
        if fallback_note:
            explanation.validation_warnings.insert(0, fallback_note)
        level = RiskLevel(facts["risk_level"])
        opinion = AgentOpinion(
            agent=self.name,
            risk_level=level,
            confidence=RULE_CONFIDENCE[level.value],
            facts=facts,
            explanation=explanation,
            mode="rules_fallback" if fallback_note else "rules",
            evidence=[Evidence(**e) for e in rule_evidence(facts)],
        )
        return self.reply(message, MessageType.OPINION, opinion.model_dump(mode="json"))

    # --------------------------------------------------------------------- llm
    async def _analyze_llm(self, message: AgentMessage, series: MarketSeries) -> AgentMessage:
        symbol = message.symbol
        state = {"series": series, "requests": 0}   # estado por llamada (el agente es compartido entre símbolos)
        facts = {
            "symbol": series.symbol,
            "data_ref": message.payload["data_ref"],
            **{k: v for k, v in series.summary().items() if k != "symbol"},
            "min_bars_recommended": self.ctx.settings.min_bars_risk,
            "extended_history_days": self.ctx.settings.extended_history_days,
        }

        async def compute_risk_metrics(_: dict[str, Any]) -> dict[str, Any]:
            s = state["series"]
            return {**risk_metrics(s.closes, s.highs, s.lows), "data_ref": f"{s.symbol}:{len(s.bars)}bars"}

        async def request_history(args: dict[str, Any]) -> dict[str, Any]:
            if state["requests"] >= 2:
                return {"error": "Ya se ha pedido historial ampliado dos veces."}
            state["requests"] += 1
            days = int(args.get("days") or self.ctx.settings.extended_history_days)
            days = max(30, min(days, self.ctx.settings.extended_history_days))
            info = await self._request_history(message, series.symbol, days, str(args.get("reason") or "historial ampliado para medir riesgo"))
            if "error" not in info:
                extended = self.ctx.data.get(info.get("data_ref", ""))
                if extended is not None:
                    state["series"] = extended
            return info

        tools = [
            Tool(
                ToolSpec(
                    name="compute_risk_metrics",
                    description="Calcula volatilidad anualizada, drawdown máximo, ATR14 y ATR relativo sobre el historial disponible actualmente.",
                    parameters={"type": "object", "properties": {}, "additionalProperties": False},
                ),
                compute_risk_metrics,
            ),
            Tool(
                ToolSpec(
                    name="request_history",
                    description="Pide al agente de datos de mercado un historial más largo (días naturales). Devuelve el nuevo número de sesiones.",
                    parameters={
                        "type": "object",
                        "properties": {
                            "days": {"type": "integer", "minimum": 30, "maximum": 730},
                            "reason": {"type": "string"},
                        },
                        "required": ["days", "reason"],
                        "additionalProperties": False,
                    },
                ),
                request_history,
            ),
        ]
        output, known, tool_log = await self.run_agent_loop(
            symbol=symbol, task="risk_analysis", instructions=LLM_INSTRUCTIONS, facts=facts, tools=tools, schema=RISK_SCHEMA
        )
        if not self.tool_called(tool_log, "compute_risk_metrics"):
            await self.warn(symbol, "risk_analysis", ["El agente fijó el riesgo sin calcular las métricas; salida descartada."], discarded=True)
            raise LLMError("el modelo no consultó la herramienta compute_risk_metrics")

        clean, warnings, hard = validate_agent_output(output, known, enum_fields={"risk_level": [r.value for r in RiskLevel]})
        await self.warn(symbol, "risk_analysis", warnings + hard, discarded=bool(hard))
        if hard:
            raise LLMError("; ".join(hard))

        final_series = state["series"]
        metrics = risk_metrics(final_series.closes, final_series.highs, final_series.lows)
        ref_level = rule_risk_level(metrics)
        level = RiskLevel(clean["risk_level"])
        confidence = clean["confidence"]
        evidence = clean.get("evidence", [])

        if SEVERITY[level.value] < SEVERITY[ref_level] - 1:
            await self.guardrail(
                symbol, "R1: riesgo subestimado en dos niveles", before=level.value, after=ref_level,
                reason=f"Las reglas indican {ref_level} (vol {metrics['annualized_volatility']}, drawdown {metrics['max_drawdown']}).",
            )
            level = RiskLevel(ref_level)
        if len(final_series.bars) < self.ctx.settings.min_bars_risk:
            warnings.append(f"Nivel fijado con {len(final_series.bars)} sesiones (< {self.ctx.settings.min_bars_risk} recomendadas).")
            confidence = min(confidence, 0.5)

        summary = clean["summary"]
        if "summary" in clean["_ungrounded"] or not summary:
            summary = evidence_summary(f"Riesgo {level.value} (confianza {confidence}).", evidence, known)
            warnings.append("Resumen del modelo sustituido por uno construido con la evidencia validada.")

        opinion_facts = {
            **metrics,
            "thresholds": dict(THRESHOLDS),
            "extended_data_requested": state["requests"] > 0,
            "rule_risk_level": ref_level,
        }
        opinion = AgentOpinion(
            agent=self.name,
            risk_level=level,
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
            rule_reference={"risk_level": ref_level},
        )
        return self.reply(message, MessageType.OPINION, opinion.model_dump(mode="json"))

    def summarize(self, response: AgentMessage) -> str:
        p = response.payload
        ref = (p.get("rule_reference") or {}).get("risk_level")
        ref_txt = f" · reglas: {ref}" if ref and ref != p.get("risk_level") else ""
        return f"riesgo {p.get('risk_level')} (vol {p.get('facts', {}).get('annualized_volatility')}){ref_txt}"
