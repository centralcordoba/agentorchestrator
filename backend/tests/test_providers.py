"""Proveedores reales, con dobles: ni una petición sale a la red."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

import httpx
import pytest

from orq.domain.agents import AGENTS
from orq.domain.enums import AgentId, ProviderId
from orq.domain.errors import ProviderError, ProviderNotConfiguredError, ProviderRefusalError
from orq.infrastructure.ai.providers import (
    AnthropicProvider,
    OpenRouterProvider,
    ProviderRequest,
    build_provider,
)
from orq.infrastructure.ai.providers.anthropic_provider import _thinking_for
from orq.infrastructure.ai.schema import validate

from .conftest import run_async

CODE_SCHEMA = AGENTS[AgentId.CODE].output_schema
CODE_OUTPUT = {"summary": "un cambio", "stack": "python", "change_map": [], "findings": []}


def _request(**overrides: Any) -> ProviderRequest:
    base = {
        "agent_id": AgentId.CODE,
        "model": "claude-sonnet-5",
        "system_prompt": "Eres un revisor de código.",
        "task_prompt": "Revisa el diff.",
        "context": {"requirement_id": "REQ-001"},
        "output_schema": CODE_SCHEMA,
        "max_steps": 3,
    }
    base.update(overrides)
    return ProviderRequest(**base)  # type: ignore[arg-type]


@dataclass
class _Block:
    type: str
    text: str = ""
    name: str = ""
    input: dict[str, Any] = field(default_factory=dict)
    id: str = "tool-1"


@dataclass
class _Usage:
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass
class _Response:
    content: list[_Block]
    usage: _Usage = field(default_factory=_Usage)
    stop_reason: str = "end_turn"
    stop_details: Any = None


class _Messages:
    def __init__(self, responses: list[_Response]) -> None:
        self._responses = responses
        self.params: list[dict[str, Any]] = []

    async def create(self, **params: Any) -> _Response:
        self.params.append(params)
        return self._responses[min(len(self.params) - 1, len(self._responses) - 1)]


class _FakeAnthropicClient:
    def __init__(self, responses: list[_Response]) -> None:
        self.messages = _Messages(responses)


def _text(payload: dict[str, Any], **kwargs: Any) -> _Response:
    return _Response(
        content=[_Block(type="text", text=json.dumps(payload))],
        usage=_Usage(input_tokens=100, output_tokens=20),
        **kwargs,
    )


def test_anthropic_returns_the_parsed_output() -> None:
    client = _FakeAnthropicClient([_text(CODE_OUTPUT)])
    provider = AnthropicProvider(client=client)
    response = run_async(provider.complete(_request()))

    assert response.output == CODE_OUTPUT
    assert validate(response.output, CODE_SCHEMA) == []
    assert (response.tokens_in, response.tokens_out) == (100, 20)


def test_anthropic_asks_for_structured_output_and_adaptive_thinking() -> None:
    client = _FakeAnthropicClient([_text(CODE_OUTPUT)])
    run_async(AnthropicProvider(client=client).complete(_request()))

    params = client.messages.params[0]
    assert params["model"] == "claude-sonnet-5"
    assert params["output_config"]["format"]["type"] == "json_schema"
    # El esquema viaja como estructura normal, no como el objeto de solo lectura del registro.
    assert isinstance(params["output_config"]["format"]["schema"], dict)
    assert params["thinking"] == {"type": "adaptive"}
    assert params["system"].startswith("Eres un revisor")
    assert "tools" not in params  # sin herramientas registradas no se declara ninguna


def test_haiku_keeps_the_fixed_budget_mode() -> None:
    """Haiku todavía no acepta pensamiento adaptativo: ahí se omite el parámetro."""
    assert _thinking_for("claude-haiku-4-5") is None
    assert _thinking_for("claude-sonnet-5") == {"type": "adaptive"}


def test_anthropic_refusal_becomes_a_domain_error() -> None:
    refusal = _Response(content=[], stop_reason="refusal")
    provider = AnthropicProvider(client=_FakeAnthropicClient([refusal]))
    with pytest.raises(ProviderRefusalError):
        run_async(provider.complete(_request()))


def test_anthropic_truncated_response_is_an_error_not_a_half_output() -> None:
    truncated = _Response(content=[_Block(type="text", text="{")], stop_reason="max_tokens")
    provider = AnthropicProvider(client=_FakeAnthropicClient([truncated]))
    with pytest.raises(ProviderError):
        run_async(provider.complete(_request()))


def test_anthropic_runs_the_tool_loop() -> None:
    tool_turn = _Response(
        content=[_Block(type="tool_use", name="git_diff", input={"branch": "main"})],
        usage=_Usage(input_tokens=50, output_tokens=10),
        stop_reason="tool_use",
    )
    client = _FakeAnthropicClient([tool_turn, _text(CODE_OUTPUT)])
    executed: list[tuple[str, dict[str, Any]]] = []

    async def run_tool(name: str, arguments: dict[str, Any]) -> str:
        executed.append((name, arguments))
        return "diff…"

    response = run_async(
        AnthropicProvider(client=client).complete(_request(run_tool=run_tool))
    )

    assert executed == [("git_diff", {"branch": "main"})]
    assert response.steps == 2
    assert response.tools_used == ("git_diff",)
    assert response.tokens_in == 150  # suma de las dos vueltas
    # La segunda petición lleva el resultado de la herramienta.
    second = client.messages.params[1]["messages"]
    assert second[-1]["content"][0]["type"] == "tool_result"


def test_anthropic_tool_failure_is_reported_back_to_the_model() -> None:
    tool_turn = _Response(
        content=[_Block(type="tool_use", name="git_diff")], stop_reason="tool_use"
    )
    client = _FakeAnthropicClient([tool_turn, _text(CODE_OUTPUT)])

    async def run_tool(name: str, arguments: dict[str, Any]) -> str:
        raise RuntimeError("el repositorio no responde")

    run_async(AnthropicProvider(client=client).complete(_request(run_tool=run_tool)))
    result = client.messages.params[1]["messages"][-1]["content"][0]
    assert result["is_error"] is True
    assert "el repositorio no responde" in result["content"]


def test_anthropic_without_key_fails_before_calling() -> None:
    with pytest.raises(ProviderNotConfiguredError):
        run_async(AnthropicProvider(api_key="").complete(_request()))


def test_anthropic_gives_up_after_max_steps() -> None:
    tool_turn = _Response(
        content=[_Block(type="tool_use", name="git_diff")], stop_reason="tool_use"
    )
    client = _FakeAnthropicClient([tool_turn])

    async def run_tool(name: str, arguments: dict[str, Any]) -> str:
        return "otra vez"

    with pytest.raises(ProviderError):
        run_async(
            AnthropicProvider(client=client).complete(_request(max_steps=2, run_tool=run_tool))
        )
    assert len(client.messages.params) == 2


def _openrouter(handler) -> OpenRouterProvider:
    client = httpx.AsyncClient(
        base_url="https://openrouter.test/api/v1", transport=httpx.MockTransport(handler)
    )
    return OpenRouterProvider(api_key="clave", client=client)


def test_openrouter_returns_the_parsed_output() -> None:
    seen: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": json.dumps(CODE_OUTPUT)}}],
                "usage": {"prompt_tokens": 80, "completion_tokens": 12},
            },
        )

    response = run_async(_openrouter(handler).complete(_request(model="anthropic/claude-sonnet-5")))

    assert response.output == CODE_OUTPUT
    assert (response.tokens_in, response.tokens_out) == (80, 12)
    payload = seen[0]
    assert payload["response_format"]["json_schema"]["strict"] is True
    assert payload["response_format"]["json_schema"]["schema"]["type"] == "object"
    assert payload["messages"][0]["role"] == "system"


def test_openrouter_runs_the_tool_loop() -> None:
    turns = [
        {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "tool_calls": [
                            {
                                "id": "call-1",
                                "function": {"name": "git_diff", "arguments": '{"branch": "main"}'},
                            }
                        ],
                    }
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 2},
        },
        {
            "choices": [{"message": {"content": json.dumps(CODE_OUTPUT)}}],
            "usage": {"prompt_tokens": 20, "completion_tokens": 4},
        },
    ]
    sent: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(json.loads(request.content))
        return httpx.Response(200, json=turns[min(len(sent) - 1, len(turns) - 1)])

    executed: list[str] = []

    async def run_tool(name: str, arguments: dict[str, Any]) -> str:
        executed.append(name)
        assert arguments == {"branch": "main"}
        return "diff…"

    response = run_async(_openrouter(handler).complete(_request(run_tool=run_tool)))

    assert executed == ["git_diff"]
    assert response.steps == 2
    assert response.tokens_in == 30
    assert sent[1]["messages"][-1]["role"] == "tool"


def test_openrouter_translates_http_errors() -> None:
    def unauthorized(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "no"})

    with pytest.raises(ProviderNotConfiguredError):
        run_async(_openrouter(unauthorized).complete(_request()))

    def server_error(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="mantenimiento")

    with pytest.raises(ProviderError):
        run_async(_openrouter(server_error).complete(_request()))


def test_openrouter_rejects_a_non_json_answer() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"choices": [{"message": {"content": "lo siento"}}]})

    with pytest.raises(ProviderError):
        run_async(_openrouter(handler).complete(_request()))


def test_openrouter_without_key_fails_before_calling() -> None:
    with pytest.raises(ProviderNotConfiguredError):
        run_async(OpenRouterProvider(api_key="").complete(_request()))


def test_factory_returns_one_provider_per_id() -> None:
    assert build_provider(ProviderId.MOCK).id is ProviderId.MOCK
    assert build_provider(ProviderId.ANTHROPIC, anthropic_api_key="x").id is ProviderId.ANTHROPIC
    assert build_provider(ProviderId.OPENROUTER, openrouter_api_key="x").id is ProviderId.OPENROUTER
