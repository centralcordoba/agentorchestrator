"""Proveedor LLM real sobre la Claude API (SDK oficial `anthropic`).

- Modo reglas: salida estructurada (`output_config.format` con JSON Schema).
- Modo llm: bucle de herramientas con bloques `tool_use` / `tool_result`; la respuesta final se
  pide como JSON en el prompt y se extrae del texto.
"""
from __future__ import annotations

import json
import logging
from typing import Any

import anthropic

from ..config import settings
from .llm_provider import (
    SYSTEM_PROMPT,
    ChatMessage,
    LLMError,
    LLMProvider,
    LLMRequest,
    LLMTurn,
    ToolCall,
    ToolSpec,
    extract_json_object,
)

log = logging.getLogger(__name__)


class AnthropicProvider(LLMProvider):
    name = "anthropic"
    supports_tools = True

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

    async def _create(self, **kwargs: Any) -> Any:
        try:
            if self._fallbacks:
                # Fallback en servidor: si el modelo rechaza por política, la API reintenta
                # la misma petición en otro modelo dentro de la misma llamada.
                return await self._client.beta.messages.create(
                    betas=["server-side-fallback-2026-07-01"], fallbacks="default", **kwargs
                )
            return await self._client.messages.create(**kwargs)
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

    @staticmethod
    def _check_stop(response: Any) -> None:
        if response.stop_reason == "refusal":
            details = getattr(response, "stop_details", None)
            category = getattr(details, "category", None) if details else None
            raise LLMError(f"El modelo rechazó la petición (categoría: {category or 'desconocida'}).")
        if response.stop_reason == "max_tokens":
            raise LLMError("La respuesta del modelo se truncó por max_tokens.")

    @staticmethod
    def _usage(response: Any, model: str) -> dict[str, Any] | None:
        usage = getattr(response, "usage", None)
        if usage is None:
            return None
        return {
            "input_tokens": getattr(usage, "input_tokens", None),
            "output_tokens": getattr(usage, "output_tokens", None),
            "model": getattr(response, "model", model),
        }

    # ------------------------------------------------------------ modo reglas
    async def complete_json(self, request: LLMRequest) -> dict[str, Any]:
        response = await self._create(
            model=self._model,
            max_tokens=self._max_tokens,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": self._render_user_prompt(request)}],
            output_config={
                "effort": self._effort,
                "format": {"type": "json_schema", "schema": request.schema},
            },
        )
        self._check_stop(response)
        text = next((b.text for b in response.content if b.type == "text"), None)
        if text is None:
            raise LLMError("La respuesta del modelo no contiene texto.")
        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            raise LLMError("La respuesta del modelo no es JSON válido.") from e
        if not isinstance(data, dict):
            raise LLMError("La respuesta del modelo no es un objeto JSON.")
        usage = self._usage(response, self._model)
        if usage is not None:
            data["_usage"] = usage
        return data

    # --------------------------------------------------------------- modo llm
    async def chat(
        self,
        *,
        task: str,
        system: str,
        messages: list[ChatMessage],
        tools: list[ToolSpec],
        schema: dict[str, Any],
    ) -> LLMTurn:
        response = await self._create(
            model=self._model,
            max_tokens=self._max_tokens,
            system=system,
            messages=_to_anthropic_messages(messages),
            tools=[{"name": t.name, "description": t.description, "input_schema": t.parameters} for t in tools],
            output_config={"effort": self._effort},
        )
        self._check_stop(response)

        calls: list[ToolCall] = []
        text_parts: list[str] = []
        for block in response.content:
            if block.type == "tool_use":
                calls.append(ToolCall(id=block.id, name=block.name, arguments=dict(block.input or {})))
            elif block.type == "text":
                text_parts.append(block.text)
        content = "".join(text_parts)
        assistant = ChatMessage(role="assistant", content=content or None, tool_calls=calls)
        usage = self._usage(response, self._model)
        if calls:
            return LLMTurn(assistant=assistant, tool_calls=calls, output=None, usage=usage)
        output = extract_json_object(content)
        if output is None:
            raise LLMError("El modelo terminó sin devolver el JSON final.")
        return LLMTurn(assistant=assistant, tool_calls=[], output=output, usage=usage)


def _to_anthropic_messages(messages: list[ChatMessage]) -> list[dict[str, Any]]:
    """Convierte al formato de bloques de Claude. Los resultados de herramientas consecutivos se
    agrupan en UN solo mensaje de usuario (requisito de la API para llamadas paralelas)."""
    out: list[dict[str, Any]] = []
    for m in messages:
        if m.role == "assistant":
            blocks: list[dict[str, Any]] = []
            if m.content:
                blocks.append({"type": "text", "text": m.content})
            for c in m.tool_calls:
                blocks.append({"type": "tool_use", "id": c.id, "name": c.name, "input": c.arguments})
            out.append({"role": "assistant", "content": blocks or [{"type": "text", "text": ""}]})
        elif m.role == "tool":
            block = {"type": "tool_result", "tool_use_id": m.tool_call_id or "", "content": m.content or ""}
            if out and out[-1]["role"] == "user" and isinstance(out[-1]["content"], list) and out[-1]["content"] and out[-1]["content"][0].get("type") == "tool_result":
                out[-1]["content"].append(block)
            else:
                out.append({"role": "user", "content": [block]})
        else:
            out.append({"role": "user", "content": m.content or ""})
    return out
