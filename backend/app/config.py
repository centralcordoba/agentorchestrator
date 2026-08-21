"""Configuración centralizada (variables de entorno)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

# Carga backend/.env (si existe) sin sobrescribir variables ya definidas en el entorno.
load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=False)


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


def _env_float(name: str) -> Optional[float]:
    raw = os.getenv(name)
    try:
        return float(raw) if raw else None
    except ValueError:
        return None


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

    # OpenRouter (API compatible con OpenAI). LLM_PROVIDER=openrouter
    openrouter_api_key: str = field(default_factory=lambda: os.getenv("OPENROUTER_API_KEY", "").strip())
    openrouter_model: str = field(
        default_factory=lambda: os.getenv("OPENROUTER_MODEL", "anthropic/claude-sonnet-4.6").strip()
    )
    openrouter_max_tokens: int = field(default_factory=lambda: _env_int("OPENROUTER_MAX_TOKENS", 1024))
    openrouter_temperature: float = field(
        default_factory=lambda: float(os.getenv("OPENROUTER_TEMPERATURE", "0.2") or 0.2)
    )
    openrouter_timeout_s: int = field(default_factory=lambda: _env_int("OPENROUTER_TIMEOUT_S", 60))
    openrouter_app_name: str = field(default_factory=lambda: os.getenv("OPENROUTER_APP_NAME", "Demo educativa multiagente"))
    openrouter_app_url: str = field(default_factory=lambda: os.getenv("OPENROUTER_APP_URL", "http://localhost:8000"))
    # Máximo de llamadas LLM simultáneas (protege cuotas y límites de tasa).
    llm_max_concurrency: int = field(default_factory=lambda: _env_int("LLM_MAX_CONCURRENCY", 4))
    # Precios manuales (USD por millón de tokens) para estimar coste cuando el proveedor no lo informa.
    # Vacío → se usa el catálogo del proveedor (OpenRouter) o la tabla interna (Anthropic).
    llm_price_input_per_mtok: Optional[float] = field(default_factory=lambda: _env_float("LLM_PRICE_INPUT_PER_MTOK"))
    llm_price_output_per_mtok: Optional[float] = field(default_factory=lambda: _env_float("LLM_PRICE_OUTPUT_PER_MTOK"))

    # Modo de los agentes por defecto: "llm" (el modelo razona con herramientas; las reglas vigilan)
    # o "rules" (las reglas deciden; el LLM solo redacta). Cada ejecución puede sobrescribirlo.
    agent_mode: str = field(default_factory=lambda: os.getenv("AGENT_MODE", "llm").strip().lower())
    # Máximo de turnos LLM por agente y tarea en modo llm (cada turno puede invocar herramientas).
    agent_max_steps: int = field(default_factory=lambda: _env_int("AGENT_MAX_STEPS", 8))
    # Carpeta donde se persisten las ejecuciones (JSON). Vacío → solo memoria.
    runs_dir: str = field(
        default_factory=lambda: os.getenv(
            "RUNS_DIR", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "runs")
        )
    )

    # Ejecución
    max_symbols_per_run: int = field(default_factory=lambda: _env_int("MAX_SYMBOLS_PER_RUN", 8))
    max_parallel_symbols: int = field(default_factory=lambda: _env_int("MAX_PARALLEL_SYMBOLS", 3))
    # Retardo artificial (ms) de los proveedores mock (simula la latencia de LLM y datos).
    demo_delay_ms: int = field(default_factory=lambda: _env_int("DEMO_DELAY_MS", 600))
    # Retardo (ms) aplicado a CADA mensaje entre agentes, para que el flujo se aprecie en la UI.
    # Es el valor por defecto; cada ejecución puede sobrescribirlo (POST /api/runs → message_delay_ms).
    message_delay_ms: int = field(default_factory=lambda: _env_int("MESSAGE_DELAY_MS", 800))
    max_message_delay_ms: int = 5000
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
