"""Catálogo de modelos y cálculo de coste."""
from __future__ import annotations

from dataclasses import dataclass

from ...domain.enums import ProviderId
from ...domain.run import Usage


@dataclass(frozen=True, slots=True)
class ModelInfo:
    id: str
    label: str
    in_per_m: float
    out_per_m: float


MODEL_CATALOG: dict[ProviderId, tuple[ModelInfo, ...]] = {
    ProviderId.OPENROUTER: (
        ModelInfo("google/gemini-3.5-flash-lite", "Gemini 3.5 Flash Lite", 0.3, 2.5),
        ModelInfo("google/gemini-3.5-flash", "Gemini 3.5 Flash", 1.5, 9.0),
        ModelInfo("anthropic/claude-sonnet-5", "Claude Sonnet 5", 2.0, 10.0),
        ModelInfo("anthropic/claude-opus-5", "Claude Opus 5", 5.0, 25.0),
        ModelInfo("openai/gpt-5.3-codex", "GPT-5.3 Codex", 1.75, 14.0),
        ModelInfo("deepseek/deepseek-v4-flash", "DeepSeek V4 Flash", 0.084, 0.168),
    ),
    ProviderId.ANTHROPIC: (
        ModelInfo("claude-opus-5", "Claude Opus 5", 5.0, 25.0),
        ModelInfo("claude-sonnet-5", "Claude Sonnet 5", 2.0, 10.0),
        # El prototipo escribió este identificador con sufijo de fecha; el real no lo lleva.
        ModelInfo("claude-haiku-4-5", "Claude Haiku 4.5", 1.0, 5.0),
    ),
    ProviderId.MOCK: (ModelInfo("mock", "Mock (sin coste)", 0.0, 0.0),),
}


def model_info(provider: ProviderId, model: str) -> ModelInfo:
    """Modelo del catálogo. Uno desconocido se devuelve con coste cero y se marca como tal."""
    for info in MODEL_CATALOG.get(provider, ()):
        if info.id == model:
            return info
    return ModelInfo(id=model, label=f"{model} (fuera del catálogo)", in_per_m=0.0, out_per_m=0.0)


def usage_for(provider: ProviderId, model: str, *, tokens_in: int, tokens_out: int) -> Usage:
    info = model_info(provider, model)
    cost = (tokens_in / 1_000_000) * info.in_per_m + (tokens_out / 1_000_000) * info.out_per_m
    return Usage(tokens_in=tokens_in, tokens_out=tokens_out, cost_usd=round(cost, 6))
