"""Proveedor Anthropic (Claude API) con el SDK oficial."""
from __future__ import annotations

import json
import logging
from typing import Any

from ....domain.enums import ProviderId
from ....domain.errors import ProviderError, ProviderNotConfiguredError, ProviderRefusalError
from .base import ProviderRequest, ProviderResponse, user_content

log = logging.getLogger(__name__)


class AnthropicProvider:
    id = ProviderId.ANTHROPIC

    def __init__(self, *, api_key: str = "", client: Any = None) -> None:
        self._client = client
        self._api_key = api_key

    def _ensure_client(self, timeout_s: float) -> Any:
        if self._client is not None:
            return self._client
        try:
            from anthropic import AsyncAnthropic
        except ImportError as exc:  # pragma: no cover - depende del entorno
            raise ProviderNotConfiguredError(
                "Falta el paquete «anthropic». Instálalo o usa AI_PROVIDER=mock."
            ) from exc
        if not self._api_key:
            raise ProviderNotConfiguredError(
                "Falta ANTHROPIC_API_KEY para usar el proveedor «anthropic»."
            )
        # max_retries=0: los reintentos los decide la pasarela.
        self._client = AsyncAnthropic(api_key=self._api_key, timeout=timeout_s, max_retries=0)
        return self._client

    async def complete(self, request: ProviderRequest) -> ProviderResponse:
        client = self._ensure_client(request.timeout_s)
        messages: list[dict[str, Any]] = [{"role": "user", "content": user_content(request)}]
        tools = [
            {
                "name": spec.name,
                "description": spec.description,
                "strict": True,
                "input_schema": spec.input_schema,
            }
            for spec in request.tools
        ]

        tokens_in = 0
        tokens_out = 0
        tools_used: list[str] = []

        for step in range(1, max(1, request.max_steps) + 1):
            params: dict[str, Any] = {
                "model": request.model,
                "max_tokens": request.max_output_tokens,
                "system": request.system_prompt,
                "messages": messages,
                "output_config": {
                    "format": {"type": "json_schema", "schema": _plain(request.output_schema)}
                },
            }
            thinking = _thinking_for(request.model)
            if thinking is not None:
                params["thinking"] = thinking
            if tools:
                params["tools"] = tools

            response = await _call(client, params)

            usage = getattr(response, "usage", None)
            tokens_in += int(getattr(usage, "input_tokens", 0) or 0)
            tokens_out += int(getattr(usage, "output_tokens", 0) or 0)

            stop_reason = getattr(response, "stop_reason", None)
            if stop_reason == "refusal":
                details = getattr(response, "stop_details", None)
                raise ProviderRefusalError(
                    "El modelo se negó a responder"
                    + (f" ({getattr(details, 'category', '')})" if details else "")
                )
            if stop_reason == "max_tokens":
                raise ProviderError(
                    f"La respuesta se cortó por max_tokens ({request.max_output_tokens})."
                )

            blocks = list(getattr(response, "content", []) or [])
            tool_calls = [b for b in blocks if getattr(b, "type", "") == "tool_use"]

            if tool_calls and request.run_tool is not None:
                messages.append({"role": "assistant", "content": blocks})
                results = []
                for block in tool_calls:
                    name = getattr(block, "name", "")
                    arguments = getattr(block, "input", {}) or {}
                    tools_used.append(name)
                    try:
                        result = await request.run_tool(name, dict(arguments))
                        results.append(
                            {"type": "tool_result", "tool_use_id": block.id, "content": result}
                        )
                    except Exception as exc:  # el modelo debe enterarse del fallo
                        results.append(
                            {
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": f"Error: {exc}",
                                "is_error": True,
                            }
                        )
                messages.append({"role": "user", "content": results})
                continue

            text = next((b.text for b in blocks if getattr(b, "type", "") == "text"), "")
            if not text:
                raise ProviderError("La respuesta no trae ningún bloque de texto con el JSON.")
            try:
                output = json.loads(text)
            except json.JSONDecodeError as exc:
                raise ProviderError(f"La respuesta no es JSON válido: {exc}") from exc
            if not isinstance(output, dict):
                raise ProviderError("La respuesta JSON no es un objeto.")

            return ProviderResponse(
                output=output,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                steps=step,
                tools_used=tuple(tools_used),
            )

        raise ProviderError(
            f"El agente superó sus {request.max_steps} paso(s) sin devolver una salida final."
        )


async def _call(client: Any, params: dict[str, Any]) -> Any:
    """Llama al SDK traduciendo sus errores a errores del dominio."""
    try:
        return await client.messages.create(**params)
    except Exception as exc:
        raise _translate(exc) from exc


def _translate(exc: Exception) -> Exception:
    """Traduce la jerarquía de errores del SDK, de lo más concreto a lo más general."""
    try:
        import anthropic
    except ImportError:  # pragma: no cover
        return ProviderError(str(exc))

    if isinstance(exc, anthropic.NotFoundError):
        return ProviderNotConfiguredError(f"Modelo o recurso inexistente: {exc}")
    if isinstance(exc, anthropic.AuthenticationError):
        return ProviderNotConfiguredError("Credencial de Anthropic inválida o ausente.")
    if isinstance(exc, anthropic.RateLimitError):
        return ProviderError(f"Límite de peticiones de Anthropic: {exc}")
    if isinstance(exc, anthropic.APIStatusError):
        return ProviderError(f"Anthropic respondió {exc.status_code}: {exc}")
    if isinstance(exc, (anthropic.APITimeoutError, anthropic.APIConnectionError)):
        return ProviderError(f"No se pudo contactar con Anthropic: {exc}")
    return ProviderError(str(exc))


def _thinking_for(model: str) -> dict[str, str] | None:
    """Pensamiento adaptativo salvo en los modelos que aún usan presupuesto fijo."""
    if "haiku" in model.lower():
        return None
    return {"type": "adaptive"}


def _plain(schema: Any) -> Any:
    """Convierte los esquemas de solo lectura del registro en estructuras serializables."""
    from collections.abc import Mapping

    if isinstance(schema, Mapping):
        return {k: _plain(v) for k, v in schema.items()}
    if isinstance(schema, (list, tuple)):
        return [_plain(v) for v in schema]
    return schema
