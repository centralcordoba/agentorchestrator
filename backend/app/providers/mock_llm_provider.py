"""Proveedor LLM simulado: genera explicaciones deterministas a partir de los hechos.

Permite ejecutar la demo sin red ni claves. Imita la forma de la salida real
(JSON con summary / facts_used / caveats) y solo usa los hechos recibidos.
"""
from __future__ import annotations

import asyncio
from typing import Any

from ..config import settings
from .llm_provider import LLMProvider, LLMRequest


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

    async def complete_json(self, request: LLMRequest) -> dict[str, Any]:
        await asyncio.sleep(settings.demo_delay_ms / 1000)
        handler = {
            "technical_explanation": self._technical,
            "risk_explanation": self._risk,
            "skeptic_review": self._skeptic,
            "decision_rationale": self._decision,
        }.get(request.task, self._generic)
        return handler(request.facts)

    # ------------------------------------------------------------------ tareas
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
        return {
            "summary": " ".join(parts),
            "facts_used": ["last_close", "sma_20", "sma_50", "rsi_14", "macd_histogram", "score", "stance"],
            "caveats": caveats[:3],
        }

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
        return {
            "summary": summary,
            "facts_used": ["annualized_volatility", "max_drawdown", "bars_used", "atr_pct", "risk_level"],
            "caveats": caveats,
        }

    def _skeptic(self, f: dict[str, Any]) -> dict[str, Any]:
        agrees = f.get("agrees")
        counter = f.get("counterarguments") or []
        if agrees:
            summary = (
                f"La postura técnica ({f.get('technical_stance')}, confianza {_fmt(f.get('technical_confidence'))}) "
                f"es coherente con el nivel de riesgo {f.get('risk_level')}. No se detectan contradicciones relevantes."
            )
        else:
            summary = (
                f"Discrepo de la postura técnica ({f.get('technical_stance')}): "
                + " ".join(counter)
                + f" Propongo tratar la señal como {f.get('suggested_stance')}."
            )
        return {
            "summary": summary,
            "facts_used": ["technical_stance", "technical_confidence", "risk_level", "agrees", "suggested_stance"],
            "caveats": ["El escéptico solo revisa coherencia interna; no aporta datos nuevos."],
        }

    def _decision(self, f: dict[str, Any]) -> dict[str, Any]:
        agrees = f.get("skeptic_agrees")
        skeptic_txt = (
            "sin revisión del escéptico"
            if agrees is None
            else ("escéptico de acuerdo" if agrees else "escéptico en desacuerdo")
        )
        summary = (
            f"Decisión {f.get('decision')} (confianza {_fmt(f.get('confidence'))}). "
            f"Técnico: {f.get('technical_stance')}; riesgo: {f.get('risk_level') or 'sin dato'}; "
            f"{skeptic_txt}. Regla aplicada: {f.get('rule')}."
        )
        return {
            "summary": summary,
            "facts_used": ["decision", "confidence", "technical_stance", "risk_level", "skeptic_agrees", "rule"],
            "caveats": ["Señal experimental derivada de datos históricos; no es una recomendación."],
        }

    def _generic(self, f: dict[str, Any]) -> dict[str, Any]:
        return {"summary": "Sin plantilla para esta tarea.", "facts_used": [], "caveats": []}
