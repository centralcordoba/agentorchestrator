"""Capa de IA: guardarraíles, herramientas, esquema, reintentos, presupuesto y registro."""
from __future__ import annotations

import pytest

from orq.application.ports import AgentRequest
from orq.domain.agents import AGENTS
from orq.domain.enums import AgentId, PhiClassification, ProviderId
from orq.domain.errors import (
    BudgetExceededError,
    InvalidAgentOutputError,
    PolicyViolationError,
    ProviderError,
    ProviderNotConfiguredError,
    ProviderRefusalError,
    ToolNotAllowedError,
)
from orq.domain.policies import RunBudget
from orq.domain.run import ProfileSnapshot
from orq.infrastructure.ai.catalog import usage_for
from orq.infrastructure.ai.gateway import AIGateway, RetryPolicy
from orq.infrastructure.ai.providers import MockLLMProvider, ProviderRequest, ProviderResponse
from orq.infrastructure.ai.schema import validate
from orq.infrastructure.ai.tools import InMemoryToolRegistry

from .conftest import run_async

CODE_OUTPUT = {"summary": "", "change_map": [], "findings": []}
NO_RETRY = RetryPolicy(attempts=1, base_delay_s=0.0)


def _request(
    agent_id: AgentId = AgentId.CODE,
    *,
    provider: ProviderId = ProviderId.MOCK,
    model: str = "mock",
    phi: PhiClassification = PhiClassification.DESCONOCIDO,
    context: dict | None = None,
    max_steps: int = 4,
    run_id: str = "RUN-001",
) -> AgentRequest:
    return AgentRequest(
        run_id=run_id,
        agent_id=agent_id,
        profile=ProfileSnapshot(
            provider=provider, model=model, prompt_version=1, max_steps=max_steps
        ),
        system_prompt="s",
        task_prompt="t",
        context=context or {},
        phi=phi,
    )


class _FixedProvider:
    """Doble que devuelve siempre lo mismo."""

    id = ProviderId.MOCK

    def __init__(self, response: ProviderResponse) -> None:
        self._response = response
        self.calls = 0
        self.last: ProviderRequest | None = None

    async def complete(self, request: ProviderRequest) -> ProviderResponse:
        self.calls += 1
        self.last = request
        return self._response


class _FlakyProvider:
    """Falla las primeras veces y luego responde."""

    id = ProviderId.MOCK

    def __init__(self, failures: int, error: Exception | None = None) -> None:
        self._failures = failures
        self._error = error or ProviderError("502 del proveedor")
        self.calls = 0

    async def complete(self, request: ProviderRequest) -> ProviderResponse:
        self.calls += 1
        if self.calls <= self._failures:
            raise self._error
        return ProviderResponse(output=CODE_OUTPUT, tokens_in=10, tokens_out=5)


def test_schema_validator_reports_what_is_wrong() -> None:
    schema = AGENTS[AgentId.VERDICT].output_schema
    assert validate({"verdict": "APROBADO", "confidence": 0.5, "rationale": "ok"}, schema) == []
    assert validate({"verdict": "QUIZA", "confidence": 0.5, "rationale": "ok"}, schema)
    assert validate({"verdict": "APROBADO", "confidence": 0.5}, schema)  # falta rationale
    assert validate({"verdict": "APROBADO", "confidence": 0.5, "rationale": "ok", "x": 1}, schema)


def test_booleans_are_not_numbers() -> None:
    assert validate(True, {"type": "number"})


def test_invalid_output_never_reaches_the_consumer() -> None:
    provider = _FixedProvider(ProviderResponse(output={"verdict": "QUIZA"}))
    gateway = AIGateway({ProviderId.MOCK: provider}, max_attempts=2, retry=NO_RETRY)
    with pytest.raises(InvalidAgentOutputError):
        run_async(gateway.run_agent(_request(AgentId.VERDICT)))
    assert provider.calls == 2  # reintenta una vez y se rinde con un error claro


def test_transient_failures_are_retried() -> None:
    provider = _FlakyProvider(failures=2)
    gateway = AIGateway(
        {ProviderId.MOCK: provider}, retry=RetryPolicy(attempts=3, base_delay_s=0.0)
    )
    result = run_async(gateway.run_agent(_request()))
    assert provider.calls == 3
    assert result.calls[0].attempts == 3


def test_retries_give_up_with_a_clear_error() -> None:
    provider = _FlakyProvider(failures=99)
    gateway = AIGateway(
        {ProviderId.MOCK: provider}, retry=RetryPolicy(attempts=2, base_delay_s=0.0)
    )
    with pytest.raises(ProviderError) as error:
        run_async(gateway.run_agent(_request()))
    assert "2 intento" in str(error.value)
    assert provider.calls == 2


def test_refusal_and_missing_credentials_are_not_retried() -> None:
    """Un rechazo o una credencial inválida no mejoran esperando."""
    for exc in (ProviderRefusalError("rechazado"), ProviderNotConfiguredError("sin clave")):
        provider = _FlakyProvider(failures=99, error=exc)
        gateway = AIGateway(
            {ProviderId.MOCK: provider}, retry=RetryPolicy(attempts=3, base_delay_s=0.0)
        )
        with pytest.raises(type(exc)):
            run_async(gateway.run_agent(_request()))
        assert provider.calls == 1


def test_backoff_grows_and_has_a_ceiling() -> None:
    policy = RetryPolicy(attempts=5, base_delay_s=0.5, max_delay_s=2.0)
    assert [policy.delay_for(i) for i in range(1, 5)] == [0.5, 1.0, 2.0, 2.0]


def _echo_registry() -> InMemoryToolRegistry:
    registry = InMemoryToolRegistry()

    async def handler(agent_id: AgentId, arguments: dict) -> str:
        return f"diff de {agent_id.value}"

    registry.register(
        "git_diff",
        description="Devuelve el diff de la rama",
        input_schema={"type": "object", "properties": {}, "additionalProperties": False},
        handler=handler,
    )
    return registry


class _RecordingMock:
    """Proveedor mock que además recuerda la última petición recibida."""

    id = ProviderId.MOCK

    def __init__(self) -> None:
        self._inner = MockLLMProvider()
        self.last: ProviderRequest | None = None

    async def complete(self, request: ProviderRequest) -> ProviderResponse:
        self.last = request
        # Sin `run_tool` para que el mock no ejercite el bucle en esta prueba.
        return await self._inner.complete(
            ProviderRequest(
                agent_id=request.agent_id,
                model=request.model,
                system_prompt=request.system_prompt,
                task_prompt=request.task_prompt,
                context=request.context,
                output_schema=request.output_schema,
            )
        )


def test_only_registered_and_declared_tools_reach_the_model() -> None:
    provider = _RecordingMock()
    gateway = AIGateway({ProviderId.MOCK: provider}, tools=_echo_registry(), retry=NO_RETRY)

    run_async(gateway.run_agent(_request(AgentId.CODE)))
    assert provider.last is not None
    assert [spec.name for spec in provider.last.tools] == ["git_diff"]

    # El agente de Privacidad no declara `git_diff`: no la ve.
    run_async(gateway.run_agent(_request(AgentId.PRIVACY)))
    assert provider.last.tools == ()


def test_registering_a_tool_no_agent_declares_is_rejected() -> None:
    registry = InMemoryToolRegistry()

    async def handler(agent_id: AgentId, arguments: dict) -> str:
        return ""

    with pytest.raises(ToolNotAllowedError):
        registry.register(
            "borrar_repositorio", description="", input_schema={}, handler=handler
        )


class _ToolCallingProvider:
    """Pide una herramienta y devuelve la salida final."""

    id = ProviderId.MOCK

    def __init__(self, tool: str) -> None:
        self._tool = tool
        self.result = ""
        self.error = ""

    async def complete(self, request: ProviderRequest) -> ProviderResponse:
        assert request.run_tool is not None
        try:
            self.result = await request.run_tool(self._tool, {})
        except ToolNotAllowedError as exc:
            self.error = str(exc)
            raise
        return ProviderResponse(output=CODE_OUTPUT, tokens_in=1, tokens_out=1, steps=2)


def test_declared_tool_runs_and_is_recorded() -> None:
    provider = _ToolCallingProvider("git_diff")
    gateway = AIGateway({ProviderId.MOCK: provider}, tools=_echo_registry(), retry=NO_RETRY)
    result = run_async(gateway.run_agent(_request(AgentId.CODE)))
    assert provider.result == "diff de code"
    assert result.tools_used == ("git_diff",)
    assert result.calls[0].tools_used == ("git_diff",)
    assert result.calls[0].tools_rejected == ()


def test_undeclared_tool_is_blocked_and_logged_as_rejected() -> None:
    provider = _ToolCallingProvider("run_tests")  # el agente Código no la declara
    gateway = AIGateway({ProviderId.MOCK: provider}, tools=_echo_registry(), retry=NO_RETRY)
    with pytest.raises(ToolNotAllowedError):
        run_async(gateway.run_agent(_request(AgentId.CODE, run_id="RUN-TOOL")))

    assert "no tiene autorizada" in provider.error
    # El intento rechazado queda en el registro de la ejecución, con su motivo.
    registered = gateway.calls("RUN-TOOL")
    assert registered and registered[-1].tools_rejected == ("run_tests",)
    assert "run_tests" in registered[-1].error


def test_provider_without_baa_is_blocked_for_phi() -> None:
    gateway = AIGateway()
    with pytest.raises(PolicyViolationError):
        run_async(
            gateway.run_agent(
                _request(
                    provider=ProviderId.OPENROUTER,
                    model="google/gemini-3.5-flash-lite",
                    phi=PhiClassification.SI,
                )
            )
        )


def test_real_provider_without_credentials_fails_explicitly() -> None:
    """Sin clave no se simula una respuesta: se falla con un motivo claro."""
    gateway = AIGateway(retry=NO_RETRY, credentials={})
    with pytest.raises(ProviderNotConfiguredError):
        run_async(
            gateway.run_agent(
                _request(
                    provider=ProviderId.ANTHROPIC,
                    model="claude-sonnet-5",
                    phi=PhiClassification.NO,
                )
            )
        )


def test_budget_stops_the_run() -> None:
    provider = _FixedProvider(
        ProviderResponse(output=CODE_OUTPUT, tokens_in=1_000_000, tokens_out=0)
    )
    gateway = AIGateway(
        {ProviderId.OPENROUTER: provider},
        budget=RunBudget(max_tokens=10),
        retry=NO_RETRY,
    )
    request = _request(
        provider=ProviderId.OPENROUTER,
        model="google/gemini-3.5-flash-lite",
        phi=PhiClassification.NO,
    )
    # La primera llamada se paga y agota el presupuesto.
    with pytest.raises(BudgetExceededError):
        run_async(gateway.run_agent(request))
    # La siguiente ni siquiera se envía.
    with pytest.raises(BudgetExceededError):
        run_async(gateway.run_agent(request))
    assert provider.calls == 1


def test_cost_budget_is_enforced_too() -> None:
    provider = _FixedProvider(
        ProviderResponse(output=CODE_OUTPUT, tokens_in=1_000_000, tokens_out=1_000_000)
    )
    gateway = AIGateway(
        {ProviderId.OPENROUTER: provider},
        budget=RunBudget(max_cost_usd=0.10),
        retry=NO_RETRY,
    )
    with pytest.raises(BudgetExceededError):
        run_async(
            gateway.run_agent(
                _request(
                    provider=ProviderId.OPENROUTER,
                    model="anthropic/claude-sonnet-5",
                    phi=PhiClassification.NO,
                )
            )
        )


def test_cost_comes_from_the_catalog() -> None:
    usage = usage_for(
        ProviderId.OPENROUTER, "google/gemini-3.5-flash-lite", tokens_in=1_000_000, tokens_out=0
    )
    assert usage.cost_usd == 0.3
    assert usage_for(ProviderId.MOCK, "mock", tokens_in=999, tokens_out=999).cost_usd == 0.0
    # Un modelo fuera del catálogo no inventa precio.
    assert usage_for(ProviderId.OPENROUTER, "desconocido", tokens_in=10, tokens_out=10).cost_usd == 0.0


def test_every_call_is_recorded_without_content() -> None:
    provider = _FixedProvider(ProviderResponse(output=CODE_OUTPUT, tokens_in=40, tokens_out=8))
    gateway = AIGateway({ProviderId.MOCK: provider}, retry=NO_RETRY)
    result = run_async(gateway.run_agent(_request()))

    call = result.calls[0]
    assert call.agent_id is AgentId.CODE
    assert call.provider is ProviderId.MOCK
    assert call.model == "mock"
    assert call.prompt_version == 1
    assert call.usage.tokens_in == 40
    assert call.duration_ms >= 0
    # El registro es de metadatos: no hay ningún campo con el prompt ni la respuesta.
    fields = set(vars(call)) if hasattr(call, "__dict__") else set(call.__slots__)
    assert not fields & {"prompt", "response", "content", "context"}


def test_spent_accumulates_per_run() -> None:
    provider = _FixedProvider(ProviderResponse(output=CODE_OUTPUT, tokens_in=10, tokens_out=2))
    gateway = AIGateway({ProviderId.MOCK: provider}, retry=NO_RETRY)
    run_async(gateway.run_agent(_request(run_id="RUN-A")))
    run_async(gateway.run_agent(_request(run_id="RUN-A")))
    run_async(gateway.run_agent(_request(run_id="RUN-B")))
    assert gateway.spent("RUN-A").tokens_in == 20
    assert gateway.spent("RUN-B").tokens_in == 10


def test_a_failed_call_is_recorded_as_well() -> None:
    provider = _FlakyProvider(failures=99)
    gateway = AIGateway(
        {ProviderId.MOCK: provider}, retry=RetryPolicy(attempts=1, base_delay_s=0.0)
    )
    with pytest.raises(ProviderError):
        run_async(gateway.run_agent(_request(run_id="RUN-C")))
    assert gateway.spent("RUN-C").tokens_in == 0  # no hubo respuesta que pagar


def test_mock_output_is_valid_for_every_agent() -> None:
    provider = MockLLMProvider()
    for agent_id, definition in AGENTS.items():
        response = run_async(
            provider.complete(
                ProviderRequest(
                    agent_id=agent_id,
                    model="mock",
                    system_prompt="s",
                    task_prompt="t",
                    context={},
                    output_schema=definition.output_schema,
                )
            )
        )
        assert validate(response.output, definition.output_schema) == [], agent_id


def test_demo_mode_output_is_also_valid_and_marked() -> None:
    """El modo demo rellena informes para poder enseñar el flujo, sin dejar de ser honesto."""
    provider = MockLLMProvider(rich=True)
    for agent_id, definition in AGENTS.items():
        response = run_async(
            provider.complete(
                ProviderRequest(
                    agent_id=agent_id,
                    model="mock",
                    system_prompt="s",
                    task_prompt="t",
                    context={"title": "Conciliación de pagos", "phi": "si"},
                    output_schema=definition.output_schema,
                )
            )
        )
        assert validate(response.output, definition.output_schema) == [], agent_id

    codigo = run_async(
        provider.complete(
            ProviderRequest(
                agent_id=AgentId.CODE,
                model="mock",
                system_prompt="s",
                task_prompt="t",
                context={"title": "Conciliación de pagos"},
                output_schema=AGENTS[AgentId.CODE].output_schema,
            )
        )
    ).output
    # Tiene contenido…
    assert codigo["change_map"] and codigo["findings"]
    # …pero cada texto dice de dónde sale.
    assert "simulado" in codigo["summary"]
    assert all("simulado" in f["detail"] for f in codigo["findings"])


def test_mock_marks_its_output_as_simulated() -> None:
    provider = MockLLMProvider()
    response = run_async(
        provider.complete(
            ProviderRequest(
                agent_id=AgentId.PRIVACY,
                model="mock",
                system_prompt="s",
                task_prompt="t",
                context={},
                output_schema=AGENTS[AgentId.PRIVACY].output_schema,
            )
        )
    )
    # Sin análisis real, ninguna salvaguarda puede darse por cumplida.
    assert all(s["status"] == "sin_evidencia" for s in response.output["safeguards"])
    assert response.output["detections"] == []
