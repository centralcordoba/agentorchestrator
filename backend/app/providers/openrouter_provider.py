"""Proveedor LLM sobre OpenRouter (API compatible con OpenAI Chat Completions).

- Endpoint: https://openrouter.ai/api/v1/chat/completions
- Autenticación: cabecera `Authorization: Bearer <OPENROUTER_API_KEY>`
- Salida estructurada: se pide `response_format` de tipo `json_schema` (con `provider.require_parameters`
  para enrutar solo a proveedores que lo soportan). Si el modelo/proveedor lo rechaza, se reintenta con
  `json_object` y, en última instancia, se extrae el JSON del texto. En todos los casos la salida pasa
  después por la validación "no inventar datos" del agente.
- Herramientas (modo llm): `tools` / `tool_calls` según la especificación de OpenAI.
"""
from __future__ import annotations

import json
import logging
from typing import Any

import httpx

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
    with_cost,
)

log = logging.getLogger(__name__)

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"


class OpenRouterProvider(LLMProvider):
    name = "openrouter"
    supports_tools = True

    def __init__(self) -> None:
        if not settings.openrouter_api_key:
            log.warning("OPENROUTER_API_KEY no definida: todas las llamadas fallarán y se usará el fallback por reglas.")
        self._model = settings.openrouter_model
        self._max_tokens = settings.openrouter_max_tokens
        self._temperature = settings.openrouter_temperature
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(float(settings.openrouter_timeout_s), connect=10.0),
            headers={
                "Authorization": f"Bearer {settings.openrouter_api_key}",
                "Content-Type": "application/json",
                # Cabeceras opcionales de atribución de OpenRouter (aparecen en su panel de uso).
                "HTTP-Referer": settings.openrouter_app_url,
                "X-Title": settings.openrouter_app_name,
            },
        )
        self.name = f"openrouter:{self._model}"
        # Precios (USD/token) del catálogo de OpenRouter; se cargan una sola vez y solo si hacen falta.
        self._pricing: tuple[float, float] | None = None
        self._pricing_loaded = False

    async def _load_pricing(self) -> tuple[float, float] | None:
        if self._pricing_loaded:
            return self._pricing
        self._pricing_loaded = True
        try:
            resp = await self._client.get(OPENROUTER_MODELS_URL, timeout=15.0)
            if resp.status_code == 200:
                for m in resp.json().get("data", []):
                    if m.get("id") == self._model:
                        pr = m.get("pricing") or {}
                        self._pricing = (float(pr.get("prompt", 0)) * 1e6, float(pr.get("completion", 0)) * 1e6)
                        break
        except Exception as e:  # sin catálogo no hay estimación; no es un error de la demo
            log.info("OpenRouter: no se pudo leer el catálogo de precios (%s).", e)
        return self._pricing

    async def _usage(self, data: dict[str, Any], mode: str) -> dict[str, Any]:
        usage = data.get("usage") or {}
        base = {
            "input_tokens": usage.get("prompt_tokens"),
            "output_tokens": usage.get("completion_tokens"),
            "model": data.get("model", self._model),
            "provider": data.get("provider"),
            "mode": mode,
        }
        cost = usage.get("cost")
        if isinstance(cost, (int, float)):
            return with_cost(base, provider_cost_usd=float(cost))
        pricing = await self._load_pricing()
        if pricing:
            return with_cost(base, price_input_per_mtok=pricing[0], price_output_per_mtok=pricing[1])
        return with_cost(base)

    # ------------------------------------------------------------ modo reglas
    @staticmethod
    def _render_user_prompt(request: LLMRequest) -> str:
        return (
            f"Agente: {request.agent}\nTarea: {request.task}\n\n"
            f"Instrucciones:\n{request.instructions}\n\n"
            f"<facts>\n{json.dumps(request.facts, ensure_ascii=False, indent=2, default=str)}\n</facts>\n\n"
            "Responde ÚNICAMENTE con un objeto JSON que cumpla este esquema (sin texto adicional, sin bloques de código):\n"
            f"{json.dumps(request.schema, ensure_ascii=False)}"
        )

    async def complete_json(self, request: LLMRequest) -> dict[str, Any]:
        if not settings.openrouter_api_key:
            raise LLMError("OPENROUTER_API_KEY no configurada.")
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": self._render_user_prompt(request)},
        ]
        data, mode = await self._request_with_ladder(messages, tools=None, schema=request.schema, name=request.task)
        choice = data["choices"][0]
        content = _content_text(choice)
        parsed = extract_json_object(content)
        if parsed is None:
            raise LLMError("OpenRouter: la respuesta del modelo no es JSON válido.")
        parsed["_usage"] = await self._usage(data, mode)
        return parsed

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
        if not settings.openrouter_api_key:
            raise LLMError("OPENROUTER_API_KEY no configurada.")
        oa_messages: list[dict[str, Any]] = [{"role": "system", "content": system}]
        for m in messages:
            oa_messages.append(_to_openai_message(m))
        oa_tools = [
            {"type": "function", "function": {"name": t.name, "description": t.description, "parameters": t.parameters}}
            for t in tools
        ]
        data, mode = await self._request_with_ladder(oa_messages, tools=oa_tools or None, schema=schema, name=task)
        choice = data["choices"][0]
        msg = choice.get("message") or {}
        content = _content_text(choice)

        calls: list[ToolCall] = []
        for raw in msg.get("tool_calls") or []:
            fn = raw.get("function") or {}
            args_raw = fn.get("arguments") or "{}"
            try:
                args = json.loads(args_raw) if isinstance(args_raw, str) else dict(args_raw)
            except ValueError:
                args = {"_raw": args_raw}
            calls.append(ToolCall(id=str(raw.get("id") or f"call_{len(calls)}"), name=str(fn.get("name")), arguments=args))

        assistant = ChatMessage(role="assistant", content=content or None, tool_calls=calls)
        usage = await self._usage(data, mode)
        if calls:
            return LLMTurn(assistant=assistant, tool_calls=calls, output=None, usage=usage)
        output = extract_json_object(content)
        if output is None:
            raise LLMError("OpenRouter: el modelo terminó sin devolver el JSON final.")
        return LLMTurn(assistant=assistant, tool_calls=[], output=output, usage=usage)

    # ------------------------------------------------------------------ http
    async def _request_with_ladder(
        self, messages: list[dict[str, Any]], *, tools: list[dict[str, Any]] | None, schema: dict[str, Any], name: str
    ) -> tuple[dict[str, Any], str]:
        """Intenta json_schema → json_object → texto libre, según lo que acepte el modelo/proveedor."""
        last_error: LLMError | None = None
        for mode in ("json_schema", "json_object", "text"):
            body: dict[str, Any] = {
                "model": self._model,
                "max_tokens": self._max_tokens,
                "temperature": self._temperature,
                "messages": messages,
                # Pide a OpenRouter que incluya el coste exacto (USD) en `usage`.
                "usage": {"include": True},
            }
            if tools:
                body["tools"] = tools
                body["tool_choice"] = "auto"
            if mode == "json_schema":
                body["response_format"] = {
                    "type": "json_schema",
                    "json_schema": {"name": f"{name}_output", "strict": True, "schema": schema},
                }
                body["provider"] = {"require_parameters": True}
            elif mode == "json_object":
                body["response_format"] = {"type": "json_object"}
            try:
                return await self._post(body, mode), mode
            except _RetryWithLowerMode as e:
                last_error = LLMError(str(e))
                log.info("OpenRouter: modo %s no aceptado (%s); reintentando con el siguiente.", mode, e)
        raise last_error or LLMError("OpenRouter: no se pudo obtener una respuesta.")

    async def _post(self, body: dict[str, Any], mode: str) -> dict[str, Any]:
        try:
            resp = await self._client.post(OPENROUTER_URL, json=body)
        except httpx.TimeoutException as e:
            raise LLMError(f"Timeout llamando a OpenRouter ({settings.openrouter_timeout_s}s).") from e
        except httpx.HTTPError as e:
            raise LLMError(f"No se pudo conectar con OpenRouter: {e.__class__.__name__}.") from e

        if resp.status_code != 200:
            detail = _error_detail(resp)
            if resp.status_code == 401:
                raise LLMError("OpenRouter: clave API inválida o ausente (401).")
            if resp.status_code == 402:
                raise LLMError("OpenRouter: sin crédito suficiente (402).")
            if resp.status_code == 404:
                raise LLMError(f"OpenRouter: modelo '{self._model}' no encontrado (404). {detail}".strip())
            if resp.status_code == 429:
                raise LLMError("OpenRouter: límite de tasa alcanzado (429).")
            if resp.status_code == 400 and mode != "text" and _mentions_response_format(detail):
                raise _RetryWithLowerMode(detail)
            if resp.status_code >= 500:
                raise LLMError(f"OpenRouter: error del servidor ({resp.status_code}).")
            raise LLMError(f"OpenRouter: petición rechazada ({resp.status_code}). {detail}".strip())

        try:
            data = resp.json()
        except ValueError as e:
            raise LLMError("OpenRouter: respuesta no es JSON.") from e

        # OpenRouter puede devolver 200 con un objeto `error` (p. ej. fallo del proveedor upstream).
        if isinstance(data, dict) and data.get("error"):
            msg = str(data["error"].get("message") if isinstance(data["error"], dict) else data["error"])
            if mode != "text" and _mentions_response_format(msg):
                raise _RetryWithLowerMode(msg)
            raise LLMError(f"OpenRouter: {msg}")

        choices = data.get("choices") or []
        if not choices:
            raise LLMError("OpenRouter: respuesta sin 'choices'.")
        finish = choices[0].get("finish_reason")
        if finish == "length":
            raise LLMError("OpenRouter: la respuesta se truncó por max_tokens.")
        if finish == "content_filter":
            raise LLMError("OpenRouter: la respuesta fue bloqueada por el filtro de contenido del proveedor.")
        return data


class _RetryWithLowerMode(Exception):
    """El modo de salida estructurada pedido no está soportado: probar el siguiente."""


def _to_openai_message(m: ChatMessage) -> dict[str, Any]:
    if m.role == "assistant":
        out: dict[str, Any] = {"role": "assistant", "content": m.content or ""}
        if m.tool_calls:
            out["tool_calls"] = [
                {
                    "id": c.id,
                    "type": "function",
                    "function": {"name": c.name, "arguments": json.dumps(c.arguments, ensure_ascii=False)},
                }
                for c in m.tool_calls
            ]
        return out
    if m.role == "tool":
        return {"role": "tool", "tool_call_id": m.tool_call_id or "", "content": m.content or ""}
    return {"role": "user", "content": m.content or ""}


def _content_text(choice: dict[str, Any]) -> str:
    content = (choice.get("message") or {}).get("content")
    if isinstance(content, list):  # algunos proveedores devuelven partes
        content = "".join(part.get("text", "") for part in content if isinstance(part, dict))
    return content if isinstance(content, str) else ""


def _error_detail(resp: httpx.Response) -> str:
    try:
        body = resp.json()
        err = body.get("error") if isinstance(body, dict) else None
        if isinstance(err, dict):
            return str(err.get("message", ""))[:300]
        return str(err or body)[:300]
    except ValueError:
        return resp.text[:300]


def _mentions_response_format(text: str) -> bool:
    t = (text or "").lower()
    return any(k in t for k in ("response_format", "json_schema", "structured output", "require_parameters", "no endpoints"))


# Compatibilidad con pruebas anteriores.
_parse_json = extract_json_object
