"""Configuración centralizada (variables de entorno)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    try:
        return int(raw) if raw else default
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    # Proveedores: "mock" funciona sin red ni claves; "anthropic"/"yfinance" usan servicios reales.
    llm_provider: str = field(default_factory=lambda: os.getenv("LLM_PROVIDER", "mock").lower())
    market_data_provider: str = field(
        default_factory=lambda: os.getenv("MARKET_DATA_PROVIDER", "mock").lower()
    )

    # Anthropic
    anthropic_model: str = field(default_factory=lambda: os.getenv("ANTHROPIC_MODEL", "claude-opus-5"))
    anthropic_effort: str = field(default_factory=lambda: os.getenv("ANTHROPIC_EFFORT", "low"))
    anthropic_max_tokens: int = field(default_factory=lambda: _env_int("ANTHROPIC_MAX_TOKENS", 2048))
    anthropic_timeout_s: int = field(default_factory=lambda: _env_int("ANTHROPIC_TIMEOUT_S", 60))
    # Fallback en servidor ante `stop_reason == "refusal"` (solo Claude API directa).
    anthropic_enable_fallbacks: bool = field(
        default_factory=lambda: _env_bool("ANTHROPIC_ENABLE_FALLBACKS", True)
    )

    # Ejecución
    max_symbols_per_run: int = field(default_factory=lambda: _env_int("MAX_SYMBOLS_PER_RUN", 8))
    max_parallel_symbols: int = field(default_factory=lambda: _env_int("MAX_PARALLEL_SYMBOLS", 3))
    # Retardo artificial (ms) para que el flujo sea visible en la UI con el proveedor mock.
    demo_delay_ms: int = field(default_factory=lambda: _env_int("DEMO_DELAY_MS", 600))
    # Historial: el agente de mercado empieza con el periodo corto; el de riesgo pide el largo.
    initial_history_days: int = field(default_factory=lambda: _env_int("INITIAL_HISTORY_DAYS", 130))
    extended_history_days: int = field(default_factory=lambda: _env_int("EXTENDED_HISTORY_DAYS", 365))
    min_bars_technical: int = 60
    min_bars_risk: int = 200

    # Carpeta con el frontend exportado (npm run build:static). Si existe, FastAPI la sirve en "/".
    frontend_dist: str = field(
        default_factory=lambda: os.getenv(
            "FRONTEND_DIST",
            os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "frontend", "out"),
        )
    )

    cors_origins: list[str] = field(
        default_factory=lambda: [
            o.strip()
            for o in os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")
            if o.strip()
        ]
    )


settings = Settings()
