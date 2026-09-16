"""Configuración tipada, leída del entorno."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

from .domain.enums import ProviderId

BACKEND_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BACKEND_DIR / ".env", override=False)

PER_PROFILE = "perfil"


def _env(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()


def _env_int(name: str, default: int) -> int:
    try:
        return int(_env(name) or default)
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(_env(name) or default)
    except ValueError:
        return default


def _provider(name: str, default: ProviderId | None) -> ProviderId | None:
    raw = _env(name).lower()
    if not raw:
        return default
    if raw == PER_PROFILE:
        return None
    try:
        return ProviderId(raw)
    except ValueError:
        return default


@dataclass(frozen=True, slots=True)
class Settings:
    ai_provider: ProviderId | None = field(
        default_factory=lambda: _provider("AI_PROVIDER", ProviderId.MOCK)
    )
    ai_max_attempts: int = field(default_factory=lambda: _env_int("AI_MAX_ATTEMPTS", 2))
    ai_retry_attempts: int = field(default_factory=lambda: _env_int("AI_RETRY_ATTEMPTS", 3))
    ai_retry_base_delay_s: float = field(
        default_factory=lambda: _env_float("AI_RETRY_BASE_DELAY_S", 0.5)
    )
    ai_timeout_s: float = field(default_factory=lambda: _env_float("AI_TIMEOUT_S", 120.0))
    ai_max_output_tokens: int = field(
        default_factory=lambda: _env_int("AI_MAX_OUTPUT_TOKENS", 16_000)
    )
    #: Retardo del proveedor `mock`: con 0 la ejecución entera termina en milisegundos y no
    #: da tiempo a ver la traza en vivo.
    ai_mock_delay_ms: int = field(default_factory=lambda: _env_int("AI_MOCK_DELAY_MS", 0))
    ai_mock_rich: bool = field(default_factory=lambda: _env("AI_MOCK_RICH") in {"1", "true", "on"})

    run_max_tokens: int = field(default_factory=lambda: _env_int("RUN_MAX_TOKENS", 2_000_000))
    run_max_cost_usd: float = field(default_factory=lambda: _env_float("RUN_MAX_COST_USD", 5.0))

    database_url: str = field(default_factory=lambda: _env("DATABASE_URL"))
    db_encryption_key: str = field(default_factory=lambda: _env("DB_ENCRYPTION_KEY"))
    retention_days: int = field(default_factory=lambda: _env_int("RETENTION_DAYS", 0))

    anthropic_api_key: str = field(default_factory=lambda: _env("ANTHROPIC_API_KEY"))
    openrouter_api_key: str = field(default_factory=lambda: _env("OPENROUTER_API_KEY"))
    openrouter_base_url: str = field(
        default_factory=lambda: _env("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    )

    git_tokens: str = field(default_factory=lambda: _env("GIT_TOKENS"))
    #: Clonado parcial: mucho más rápido en repositorios grandes. Vacío = clonar entero.
    #: Si el servidor no lo admite, el cliente reintenta entero automáticamente.
    git_clone_filter: str = field(
        default_factory=lambda: _env("GIT_CLONE_FILTER", "blob:none")
    )
    git_max_files: int = field(default_factory=lambda: _env_int("GIT_MAX_FILES", 300))
    git_max_diff_bytes: int = field(
        default_factory=lambda: _env_int("GIT_MAX_DIFF_BYTES", 4_000_000)
    )
    git_clone_timeout_s: float = field(
        default_factory=lambda: _env_float("GIT_CLONE_TIMEOUT_S", 300.0)
    )

    admin_email: str = field(default_factory=lambda: _env("ADMIN_EMAIL"))
    admin_password: str = field(default_factory=lambda: _env("ADMIN_PASSWORD"))
    session_max_age_minutes: int = field(
        default_factory=lambda: _env_int("SESSION_MAX_AGE_MINUTES", 12 * 60)
    )
    session_idle_minutes: int = field(
        default_factory=lambda: _env_int("SESSION_IDLE_MINUTES", 30)
    )
    #: `Secure` en la cookie: solo por HTTPS. Se apaga en desarrollo, que sirve por HTTP.
    session_cookie_secure: bool = field(
        default_factory=lambda: _env("SESSION_COOKIE_SECURE") in {"1", "true", "on"}
    )
    login_max_attempts: int = field(default_factory=lambda: _env_int("LOGIN_MAX_ATTEMPTS", 5))
    login_lock_minutes: int = field(default_factory=lambda: _env_int("LOGIN_LOCK_MINUTES", 15))

    cors_origins: tuple[str, ...] = field(
        default_factory=lambda: tuple(
            origin.strip()
            for origin in _env("CORS_ORIGINS", "http://localhost:3000").split(",")
            if origin.strip()
        )
    )

    @property
    def forced_provider(self) -> ProviderId | None:
        """`None` = cada agente usa el proveedor de su perfil."""
        return self.ai_provider

    def credentials(self) -> dict[str, str]:
        """Credenciales para construir los proveedores. No se registran en ningún log."""
        return {
            "anthropic": self.anthropic_api_key,
            "openrouter": self.openrouter_api_key,
            "openrouter_base_url": self.openrouter_base_url,
            "mock_delay_ms": str(self.ai_mock_delay_ms),
            "mock_rich": "1" if self.ai_mock_rich else "0",
        }

    def describe(self) -> dict[str, object]:
        """Resumen seguro para `/health`: ningún valor de credencial."""
        return {
            "aiProvider": self.ai_provider.value if self.ai_provider else PER_PROFILE,
            "aiMockDelayMs": self.ai_mock_delay_ms,
            "aiMockRich": self.ai_mock_rich,
            "aiMaxAttempts": self.ai_max_attempts,
            "aiRetryAttempts": self.ai_retry_attempts,
            "aiTimeoutS": self.ai_timeout_s,
            "runMaxTokens": self.run_max_tokens,
            "runMaxCostUsd": self.run_max_cost_usd,
            "database": "postgres" if self.database_url else "memoria",
            "retentionDays": self.retention_days,
            "anthropicKeyConfigured": bool(self.anthropic_api_key),
            "openrouterKeyConfigured": bool(self.openrouter_api_key),
            "gitHostsConfigured": self.git_hosts,
            "sessionIdleMinutes": self.session_idle_minutes,
            "sessionMaxAgeMinutes": self.session_max_age_minutes,
            "adminConfigured": bool(self.admin_email),
        }

    @property
    def git_hosts(self) -> tuple[str, ...]:
        """Hosts para los que hay credencial de git. Son nombres, no secretos."""
        return tuple(
            sorted(
                {
                    parte.split("=", 1)[0].strip().lower()
                    for parte in self.git_tokens.split(",")
                    if "=" in parte
                }
            )
        )


def load_settings() -> Settings:
    return Settings()
