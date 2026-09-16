"""Proveedor OpenRouter (API compatible con OpenAI) sobre httpx."""
from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from ....domain.enums import ProviderId
from ....domain.errors import ProviderError, ProviderNotConfiguredError
from .base import ProviderRequest, ProviderResponse, user_content

log = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"


class OpenRouterProvider:
    id = ProviderId.OPENROUTER

    def __init__(
        self,
        *,
        api_key: str = "",
        base_url: str = DEFAULT_BASE_URL,
        client: httpx.AsyncClient | None = None,
        app_title: str = "Orquestador de revisión de requerimientos",
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._client = client
        self._app_title = app_title

    def _ensure_client(self, timeout_s: float) -> httpx.AsyncClient:
        if self._client is not None:
            return self._client
        if not self._api_key:
            raise ProviderNotConfiguredError(
                "Falta OPENROUTER_API_KEY para usar el proveedor «openrouter»."
            )
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=timeout_s,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "X-Title": self._app_title,
            },
        )
        return self._client

    async def complete(self, request: ProviderRequest) -> ProviderResponse:
        client = self._ensure_client(request.timeout_s)
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": request.system_prompt},
            {"role": "user", "content": user_content(request)},
        ]
        tools = [
            {
                "type": "function",
                "function": {
                    "name": spec.name,
                    "description": spec.description,
                    "parameters": spec.input_schema,
                },
            }
            for spec in request.tools
        ]

        tokens_in = 0
        tokens_out = 0
        tools_used: list[str] = []

        for step in range(1, max(1, request.max_steps) + 1):
            payload: dict[str, Any] = {
                "model": request.model,
                "messages": messages,
                "temperature": request.temperature,
                "max_tokens": request.max_output_tokens,
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {
                        "name": f"{request.agent_id.value}_output",
                        "strict": True,
                        "schema": _plain(request.output_schema),
                    },
                },
            }
            if tools:
                payload["tools"] = tools

            data = await _post(client, "/chat/completions", payload)
            usage = data.get("usage") or {}
            tokens_in += int(usage.get("prompt_tokens", 0) or 0)
            tokens_out += int(usage.get("completion_tokens", 0) or 0)

            choices = data.get("choices") or []
            if not choices:
                raise ProviderError("OpenRouter devolvió una respuesta sin opciones.")
            message = choices[0].get("message") or {}
            calls = message.get("tool_calls") or []

            if calls and request.run_tool is not None:
                messages.append(message)
                for call in calls:
                    function = call.get("function") or {}
                    name = str(function.get("name", ""))
                    tools_used.append(name)
                    try:
                        arguments = json.loads(function.get("arguments") or "{}")
                    except json.JSONDecodeError:
                        arguments = {}
                    try:
                        result = await request.run_tool(name, arguments)
                    except Exception as exc:  # el modelo debe enterarse del fallo
                        result = f"Error: {exc}"
                    messages.append(
                        {"role": "tool", "tool_call_id": call.get("id", ""), "content": result}
                    )
                continue

            content = message.get("content") or ""
            if not content:
                raise ProviderError("OpenRouter devolvió un mensaje sin contenido.")
            try:
                output = json.loads(content)
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


async def _post(client: httpx.AsyncClient, path: str, payload: dict[str, Any]) -> dict[str, Any]:
    try:
        response = await client.post(path, json=payload)
    except httpx.TimeoutException as exc:
        raise ProviderError(f"OpenRouter no respondió a tiempo: {exc}") from exc
    except httpx.HTTPError as exc:
        raise ProviderError(f"No se pudo contactar con OpenRouter: {exc}") from exc

    if response.status_code == 401:
        raise ProviderNotConfiguredError("Credencial de OpenRouter inválida o ausente.")
    if response.status_code >= 400:
        raise ProviderError(f"OpenRouter respondió {response.status_code}: {response.text[:200]}")

    try:
        return response.json()
    except ValueError as exc:
        raise ProviderError(f"OpenRouter devolvió algo que no es JSON: {exc}") from exc


def _plain(schema: Any) -> Any:
    from collections.abc import Mapping

    if isinstance(schema, Mapping):
        return {k: _plain(v) for k, v in schema.items()}
    if isinstance(schema, (list, tuple)):
        return [_plain(v) for v in schema]
    return schema
