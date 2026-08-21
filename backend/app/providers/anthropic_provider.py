"""Proveedor LLM real sobre la Claude API (SDK oficial `anthropic`).

Usa salida estructurada (`output_config.format` con JSON Schema) para que la
respuesta sea siempre un JSON válido contra el esquema pedido por el agente.
"""
from __future__ import annotations

import json
import logging
from typing import Any

import anthropic

from ..config import settings
from .llm_provider import SYSTEM_PROMPT, LLMError, LLMProvider, LLMRequest

log = logging.getLogger(__name__)


class AnthropicProvider(LLMProvider):
    name = "anthropic"

    def __init__(self) -> None:
        # Credenciales: ANTHROPIC_API_KEY o perfil de `ant auth login`.
        self._client = anthropic.AsyncAnthropic(timeout=float(settings.anthropic_timeout_s), max_retries=2)
        self._model = settings.anthropic_model
        self._effort = settings.anthropic_effort
        self._max_tokens = settings.anthropic_max_tokens
        self._fallbacks = settings.anthropic_enable_fallbacks
        self.name = f"anthropic:{self._model}"

    @staticmethod
    def _render_user_prompt(request: LLMRequest) -> str:
        return (
            f"Agente: {request.agent}\nTarea: {request.task}\n\n"
            f"Instrucciones:\n{request.instructions}\n\n"
            f"<facts>\n{json.dumps(request.facts, ensure_ascii=False, indent=2, default=str)}\n</facts>"
        )

    async def complete_json(self, request: LLMRequest) -> dict[str, Any]:
        kwargs: dict[str, Any] = dict(
            model=self._model,
            max_tokens=self._max_tokens,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": self._render_user_prompt(request)}],
            output_config={
                "effort": self._effort,
                "format": {"type": "json_schema", "schema": request.schema},
            },
        )
        try:
            if self._fallbacks:
                # Fallback en servidor: si el modelo rechaza por política, la API reintenta
                # la misma petición en otro modelo dentro de la misma llamada.
                response = await self._client.beta.messages.create(
                    betas=["server-side-fallback-2026-07-01"], fallbacks="default", **kwargs
                )
            else:
                response = await self._client.messages.create(**kwargs)
        except anthropic.AuthenticationError as e:
            raise LLMError("Credenciales de Anthropic inválidas o ausentes.") from e
        except anthropic.RateLimitError as e:
            raise LLMError("Límite de tasa de la API de Anthropic alcanzado.") from e
        except anthropic.BadRequestError as e:
            raise LLMError(f"Petición rechazada por la API: {e.message}") from e
        except anthropic.APIStatusError as e:
            raise LLMError(f"Error de la API de Anthropic ({e.status_code}).") from e
        except anthropic.APIConnectionError as e:
            raise LLMError("No se pudo conectar con la API de Anthropic.") from e

        if response.stop_reason == "refusal":
            details = getattr(response, "stop_details", None)
            category = getattr(details, "category", None) if details else None
            raise LLMError(f"El modelo rechazó la petición (categoría: {category or 'desconocida'}).")
        if response.stop_reason == "max_tokens":
            raise LLMError("La respuesta del modelo se truncó por max_tokens.")

        text = next((b.text for b in response.content if b.type == "text"), None)
        if text is None:
            raise LLMError("La respuesta del modelo no contiene texto.")
        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            raise LLMError("La respuesta del modelo no es JSON válido.") from e
        if not isinstance(data, dict):
            raise LLMError("La respuesta del modelo no es un objeto JSON.")
        usage = getattr(response, "usage", None)
        if usage is not None:
            data["_usage"] = {
                "input_tokens": getattr(usage, "input_tokens", None),
                "output_tokens": getattr(usage, "output_tokens", None),
                "model": getattr(response, "model", self._model),
            }
        return data
