"""Proveedor LLM simulado: permite ejecutar la demo sin red ni claves.

- Modo reglas: genera explicaciones deterministas a partir de los hechos (plantillas).
- Modo llm: simula un agente con herramientas siguiendo un guion fijo (consulta las
  herramientas de cálculo, pide más historial si hace falta, reta al técnico si hay
  objeciones) y decide con las mismas reglas del modo reglas. Así la forma de la traza
  es idéntica a la de un modelo real, pero reproducible.
"""
from __future__ import annotations

import asyncio
import json
import re
from typing import Any

from ..config import settings
from .llm_provider import ChatMessage, LLMProvider, LLMRequest, LLMTurn, ToolCall, ToolSpec

_FACTS_RE = re.compile(r"<facts>\n(.*?)\n</facts>", re.S)


def _fmt(v: Any, digits: int = 2, pct: bool = False) -> str:
    if v is None:
        return "sin dato"
    if isinstance(v, bool):
        return "sí" if v else "no"
    if isinstance(v, (int, float)):
        return f"{v * 100:.{digits}f}%" if pct else f"{v:.{digits}f}"
    return str(v)


class MockLLMProvider(LLMProvider):
    name = "mock"
    supports_tools = True

    # ================================================================ modo reglas
    async def complete_json(self, request: LLMRequest) -> dict[str, Any]:
        await asyncio.sleep(settings.demo_delay_ms / 1000)
        handler = {
            "technical_explanation": self._technical,
            "risk_explanation": self._risk,
            "skeptic_review": self._skeptic,
            "decision_rationale": self._decision,
        }.get(request.task, self._generic)
        return handler(request.facts)

    def _technical(self, f: dict[str, Any]) -> dict[str, Any]:
        stance = f.get("stance")
        parts = [
            f"Último cierre {_fmt(f.get('last_close'))} frente a SMA20 {_fmt(f.get('sma_20'))} y SMA50 {_fmt(f.get('sma_50'))}.",
            f"RSI(14) en {_fmt(f.get('rsi_14'), 1)}; histograma MACD {_fmt(f.get('macd_histogram'), 3)}.",
            f"La lectura agregada de las reglas es {stance} con puntuación {f.get('score')} sobre 4.",
        ]
        caveats = ["Indicadores calculados solo sobre precios históricos; no predicen el futuro."]
        if f.get("rsi_14") is not None and f["rsi_14"] > 70:
            caveats.append("RSI en zona de sobrecompra: la señal alcista podría estar agotada.")
        if f.get("rsi_14") is not None and f["rsi_14"] < 30:
            caveats.append("RSI en zona de sobreventa: la señal bajista podría estar agotada.")
        return {"summary": " ".join(parts), "facts_used": ["last_close", "sma_20", "sma_50", "rsi_14", "macd_histogram", "score", "stance"], "caveats": caveats[:3]}

    def _risk(self, f: dict[str, Any]) -> dict[str, Any]:
        summary = (
            f"Volatilidad anualizada {_fmt(f.get('annualized_volatility'), 1, pct=True)} y "
            f"drawdown máximo {_fmt(f.get('max_drawdown'), 1, pct=True)} sobre {f.get('bars_used')} sesiones. "
            f"ATR(14) equivale al {_fmt(f.get('atr_pct'), 2, pct=True)} del precio. "
            f"Nivel de riesgo según reglas: {f.get('risk_level')}."
        )
        caveats = ["El riesgo histórico no acota las pérdidas futuras."]
        if f.get("extended_data_requested"):
            caveats.append("Se solicitó historial ampliado al agente de datos para cubrir el periodo mínimo.")
        return {"summary": summary, "facts_used": ["annualized_volatility", "max_drawdown", "bars_used", "atr_pct", "risk_level"], "caveats": caveats}

    def _skeptic(self, f: dict[str, Any]) -> dict[str, Any]:
        agrees = f.get("agrees")
        counter = f.get("counterarguments") or []
        if agrees:
            summary = (
                f"La postura técnica ({f.get('technical_stance')}, confianza {_fmt(f.get('technical_confidence'))}) "
                f"es coherente con el nivel de riesgo {f.get('risk_level')}. No se detectan contradicciones relevantes."
            )
        else:
            summary = f"Discrepo de la postura técnica ({f.get('technical_stance')}): " + " ".join(counter) + f" Propongo tratar la señal como {f.get('suggested_stance')}."
        return {"summary": summary, "facts_used": ["technical_stance", "technical_confidence", "risk_level", "agrees", "suggested_stance"], "caveats": ["El escéptico solo revisa coherencia interna; no aporta datos nuevos."]}

    def _decision(self, f: dict[str, Any]) -> dict[str, Any]:
        agrees = f.get("skeptic_agrees")
        skeptic_txt = "sin revisión del escéptico" if agrees is None else ("escéptico de acuerdo" if agrees else "escéptico en desacuerdo")
        summary = (
            f"Decisión {f.get('decision')} (confianza {_fmt(f.get('confidence'))}). "
            f"Técnico: {f.get('technical_stance')}; riesgo: {f.get('risk_level') or 'sin dato'}; "
            f"{skeptic_txt}. Regla aplicada: {f.get('rule')}."
        )
        return {"summary": summary, "facts_used": ["decision", "confidence", "technical_stance", "risk_level", "skeptic_agrees", "rule"], "caveats": ["Señal experimental derivada de datos históricos; no es una recomendación."]}

    def _generic(self, f: dict[str, Any]) -> dict[str, Any]:
        return {"summary": "Sin plantilla para esta tarea.", "facts_used": [], "caveats": []}

    # ================================================================== modo llm
    async def chat(self, *, task: str, system: str, messages: list[ChatMessage], tools: list[ToolSpec], schema: dict[str, Any]) -> LLMTurn:
        await asyncio.sleep(settings.demo_delay_ms / 1000)
        facts = _facts_from_messages(messages)
        results = _tool_results(messages)
        tool_names = {t.name for t in tools}
        handler = {
            "technical_analysis": self._agent_technical,
            "technical_challenge_response": self._agent_challenge_response,
            "risk_analysis": self._agent_risk,
            "skeptic_review": self._agent_skeptic,
            "decision": self._agent_decision,
        }.get(task)
        if handler is None:
            return _final({"summary": "Sin guion para esta tarea.", "caveats": []})
        return handler(facts, results, tool_names)

    # --- técnico
    def _agent_technical(self, facts, results, tool_names) -> LLMTurn:
        from ..agents.technical_agent import rule_stance

        if "compute_indicators" in tool_names and not results.get("compute_indicators"):
            return _call("compute_indicators", {}, "Consulto los indicadores antes de fijar postura.")
        ind = results["compute_indicators"][-1]
        ref = rule_stance(ind)
        summary = (
            f"Cierre {_fmt(ind.get('last_close'))} frente a SMA20 {_fmt(ind.get('sma_20'))} y SMA50 {_fmt(ind.get('sma_50'))}; "
            f"RSI14 {_fmt(ind.get('rsi_14'), 1)} e histograma MACD {_fmt(ind.get('macd_histogram'), 3)}. "
            f"Postura {ref['stance']}."
        )
        return _final({"stance": ref["stance"], "confidence": ref["confidence"], "evidence": ref["evidence"], "summary": summary,
                       "caveats": ["Lectura basada solo en precios históricos."]})

    def _agent_challenge_response(self, facts, results, tool_names) -> LLMTurn:
        from ..agents.technical_agent import CONCEDE_CODES

        original = facts.get("original_opinion") or {}
        counter = facts.get("counterarguments") or []
        stance = original.get("stance") or "NEUTRAL"
        conf = float(original.get("confidence") or 0.0)
        conceded = [c for c in counter if c.get("code") in CONCEDE_CODES]
        if conceded:
            new_conf = round(max(0.0, conf - 0.25 * len(conceded)), 2)
            new_stance = stance if new_conf >= 0.5 else "NEUTRAL"
            return _final({"verdict": "concedes", "stance": new_stance, "confidence": new_conf,
                           "reply": "Acepto las objeciones sobre " + ", ".join(c["code"] for c in conceded) + "; rebajo la confianza."})
        return _final({"verdict": "maintains", "stance": stance, "confidence": conf,
                       "reply": "Mantengo la postura: las objeciones no afectan a los indicadores usados."})

    # --- riesgo
    def _agent_risk(self, facts, results, tool_names) -> LLMTurn:
        from ..agents.risk_agent import rule_evidence, rule_risk_level

        metrics_runs = results.get("compute_risk_metrics", [])
        requested = results.get("request_history", [])
        if not metrics_runs:
            return _call("compute_risk_metrics", {}, "Calculo las métricas de riesgo.")
        last = metrics_runs[-1]
        min_bars = int(facts.get("min_bars_recommended") or 0)
        if last.get("bars_used", 0) < min_bars and not requested:
            return _call("request_history", {"days": int(facts.get("extended_history_days") or 365),
                                             "reason": f"Tengo {last.get('bars_used')} sesiones y necesito al menos {min_bars} para medir el drawdown."},
                         "Pido historial ampliado.")
        if requested and "error" not in requested[-1] and len(metrics_runs) < 2:
            return _call("compute_risk_metrics", {}, "Recalculo con el historial ampliado.")
        level = rule_risk_level(last)
        summary = (
            f"Volatilidad anualizada {_fmt(last.get('annualized_volatility'), 1, pct=True)}, drawdown máximo "
            f"{_fmt(last.get('max_drawdown'), 1, pct=True)} y ATR relativo {_fmt(last.get('atr_pct'), 2, pct=True)} "
            f"sobre {last.get('bars_used')} sesiones: riesgo {level}."
        )
        caveats = ["El riesgo histórico no acota las pérdidas futuras."]
        if requested and "error" in requested[-1]:
            caveats.append("No se pudo ampliar el historial; el drawdown puede estar subestimado.")
        return _final({"risk_level": level, "confidence": {"BAJO": 0.8, "MEDIO": 0.6, "ALTO": 0.85}[level],
                       "evidence": rule_evidence(last), "summary": summary, "caveats": caveats})

    # --- escéptico
    def _agent_skeptic(self, facts, results, tool_names) -> LLMTurn:
        from ..agents.skeptic_agent import find_counterarguments

        tech = facts.get("technical") or {}
        risk = facts.get("risk") or {}
        tech_for_rules = {"stance": tech.get("stance"), "confidence": tech.get("confidence"), "facts": tech.get("indicators") or {}}
        counter = find_counterarguments(tech_for_rules, {"risk_level": risk.get("risk_level")})
        challenged = results.get("challenge_technical", [])
        if counter and "challenge_technical" in tool_names and not challenged:
            return _call("challenge_technical", {"counterarguments": counter}, "Envío mis objeciones al analista técnico.")
        if not counter:
            return _final({"agrees": True, "counterarguments": [], "suggested_stance": tech.get("stance") or "NEUTRAL", "confidence": 0.8,
                           "summary": f"La postura técnica ({tech.get('stance')}) es coherente con el riesgo {risk.get('risk_level')}; sin contradicciones relevantes.",
                           "caveats": ["Solo se revisa la coherencia interna; no se aportan datos nuevos."]})
        resp = challenged[-1] if challenged else {}
        verdict = resp.get("technical_verdict")
        summary = "Discrepo: " + " ".join(c["text"] for c in counter) + (f" El técnico {'concede' if verdict == 'concedes' else 'mantiene su postura'}." if verdict else "")
        return _final({"agrees": False, "counterarguments": counter, "suggested_stance": "NEUTRAL",
                       "confidence": round(min(1.0, 0.5 + 0.15 * len(counter)), 2), "summary": summary,
                       "caveats": ["Solo se revisa la coherencia interna; no se aportan datos nuevos."]})

    # --- decisión
    def _agent_decision(self, facts, results, tool_names) -> LLMTurn:
        from ..agents.decision_agent import decide

        tech = facts.get("technical") or {}
        after = facts.get("technical_after_challenge") or {}
        risk = facts.get("risk") or {}
        sk = facts.get("skeptic") or {}
        skeptic = {"agrees": sk.get("agrees", True), "technical_response": {"stance": after.get("stance"), "confidence": after.get("confidence"), "challenge_verdict": after.get("verdict")} if after else None}
        d = decide({"stance": tech.get("stance"), "confidence": tech.get("confidence")}, {"risk_level": risk.get("risk_level")}, skeptic, None)
        factors = [f"postura técnica {tech.get('stance')}", f"riesgo {risk.get('risk_level')}", "escéptico de acuerdo" if skeptic["agrees"] else "escéptico en desacuerdo"]
        return _final({"decision": d["decision"], "confidence": d["confidence"],
                       "rationale": f"{d['decision']} (confianza {_fmt(d['confidence'])}): " + ", ".join(factors) + ".", "key_factors": factors})


# ------------------------------------------------------------------ utilidades
def _facts_from_messages(messages: list[ChatMessage]) -> dict[str, Any]:
    for m in messages:
        if m.role == "user" and m.content:
            match = _FACTS_RE.search(m.content)
            if match:
                try:
                    return json.loads(match.group(1))
                except ValueError:
                    return {}
    return {}


def _tool_results(messages: list[ChatMessage]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for m in messages:
        if m.role == "tool" and m.tool_name:
            try:
                out.setdefault(m.tool_name, []).append(json.loads(m.content or "{}"))
            except ValueError:
                out.setdefault(m.tool_name, []).append({"error": "resultado no JSON"})
    return out


_counter = 0


def _call(name: str, arguments: dict[str, Any], thought: str) -> LLMTurn:
    global _counter
    _counter += 1
    call = ToolCall(id=f"mock_call_{_counter}", name=name, arguments=arguments)
    return LLMTurn(assistant=ChatMessage(role="assistant", content=thought, tool_calls=[call]), tool_calls=[call], output=None, usage=None)


def _final(output: dict[str, Any]) -> LLMTurn:
    return LLMTurn(assistant=ChatMessage(role="assistant", content=json.dumps(output, ensure_ascii=False)), tool_calls=[], output=output, usage=None)
