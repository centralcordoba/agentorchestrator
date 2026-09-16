"""Pasarela de IA: la única puerta hacia un LLM."""
from __future__ import annotations

import asyncio
import logging
import time
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable

from ...application.ports import AgentRequest, AgentResult, ToolRegistry, ToolSpec
from ...domain.agents import AGENTS
from ...domain.enums import PhiIdentifier, ProviderId
from ...domain.errors import (
    BudgetExceededError,
    InvalidAgentOutputError,
    PolicyViolationError,
    ProviderError,
    ProviderNotConfiguredError,
    ProviderRefusalError,
    ToolNotAllowedError,
)
from ...domain.policies import RunBudget, check_agent_provider
from ...domain.privacy import Detection, redact, redact_value
from ...domain.run import LLMCall, Usage
from .catalog import usage_for
from .providers import LLMProvider, ProviderRequest, build_provider
from .schema import validate

log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    """Reintentos ante fallos transitorios del proveedor."""

    attempts: int = 3
    base_delay_s: float = 0.5
    max_delay_s: float = 8.0

    def delay_for(self, attempt: int) -> float:
        return min(self.base_delay_s * (2 ** (attempt - 1)), self.max_delay_s)


class AIGateway:
    """Implementa el puerto `AgentGateway`."""

    def __init__(
        self,
        providers: dict[ProviderId, LLMProvider] | None = None,
        *,
        max_attempts: int = 2,
        retry: RetryPolicy | None = None,
        budget: RunBudget | None = None,
        tools: ToolRegistry | None = None,
        timeout_s: float = 120.0,
        max_output_tokens: int = 16_000,
        credentials: dict[str, str] | None = None,
        scrub: Callable[[str], str] | None = None,
    ) -> None:
        self._providers = providers or {}
        self._max_attempts = max(1, max_attempts)
        self._retry = retry or RetryPolicy()
        self._budget = budget or RunBudget()
        self._tools = tools
        self._timeout_s = timeout_s
        self._max_output_tokens = max_output_tokens
        self._credentials = credentials or {}
        self._scrub = scrub or (lambda text: text)
        self._spent: dict[str, Usage] = {}
        self._log: dict[str, list[LLMCall]] = {}
        self._redacted: dict[str, Counter[PhiIdentifier]] = {}

    def provider(self, provider_id: ProviderId) -> LLMProvider:
        if provider_id not in self._providers:
            self._providers[provider_id] = build_provider(
                provider_id,
                anthropic_api_key=self._credentials.get("anthropic", ""),
                openrouter_api_key=self._credentials.get("openrouter", ""),
                openrouter_base_url=self._credentials.get("openrouter_base_url")
                or "https://openrouter.ai/api/v1",
                mock_delay_ms=int(self._credentials.get("mock_delay_ms") or 0),
                mock_rich=self._credentials.get("mock_rich") == "1",
            )
        return self._providers[provider_id]

    def spent(self, run_id: str) -> Usage:
        """Consumo acumulado de una ejecución."""
        return self._spent.get(run_id, Usage())

    def calls(self, run_id: str) -> tuple[LLMCall, ...]:
        """Registro de todas las llamadas de la ejecución, incluidas las que fallaron."""
        return tuple(self._log.get(run_id, ()))

    def redactions(self, run_id: str) -> dict[PhiIdentifier, int]:
        """Identificadores sustituidos en la ejecución, por tipo. Nunca valores."""
        return dict(self._redacted.get(run_id, Counter()))

    def _note_redactions(self, run_id: str, detections: tuple[Detection, ...]) -> None:
        if not detections:
            return
        counter = self._redacted.setdefault(run_id, Counter())
        counter.update(d.identifier for d in detections)
        log.info(
            "PHI redactada antes de salir hacia el proveedor: %s",
            ", ".join(f"{k.value}×{v}" for k, v in Counter(d.identifier for d in detections).items()),
        )

    async def run_agent(self, request: AgentRequest) -> AgentResult:
        definition = AGENTS[request.agent_id]

        blocked = check_agent_provider(request.agent_id, request.profile.provider, request.phi)
        if blocked:
            raise PolicyViolationError(blocked)

        exceeded = self._budget.exceeded_by(self.spent(request.run_id))
        if exceeded:
            raise BudgetExceededError(exceeded)

        used: list[str] = []
        rejected: list[str] = []
        detected: list[Detection] = []

        def note(detections: tuple[Detection, ...]) -> None:
            detected.extend(detections)
            self._note_redactions(request.run_id, detections)

        async def run_tool(name: str, arguments: dict[str, Any]) -> str:
            """Ejecuta una herramienta solo si el agente la declara."""
            if not definition.allows_tool(name):
                rejected.append(name)
                log.warning("%s intentó usar «%s», no declarada", request.agent_id.value, name)
                raise ToolNotAllowedError(
                    f"{definition.label} no tiene autorizada la herramienta «{name}»."
                )
            if self._tools is None:
                rejected.append(name)
                raise ToolNotAllowedError(f"No hay ninguna implementación de «{name}» registrada.")
            used.append(name)
            result = await self._tools.execute(
                request.agent_id, name, arguments, run_id=request.run_id
            )
            # Lo que devuelve una herramienta vuelve al modelo: también se redacta.
            redaction = redact(result, file=str(arguments.get("file") or arguments.get("path") or ""))
            note(redaction.detections)
            return redaction.text

        specs = self._specs_for(request, definition.tools)
        system_prompt, task_prompt, context, payload_detections = self._redacted_payload(request)
        note(payload_detections)
        provider_request = ProviderRequest(
            agent_id=request.agent_id,
            model=request.profile.model,
            system_prompt=system_prompt,
            task_prompt=task_prompt,
            context=context,
            output_schema=definition.output_schema,
            temperature=request.profile.temperature,
            max_steps=request.profile.max_steps,
            max_output_tokens=self._max_output_tokens,
            timeout_s=self._timeout_s,
            tools=specs,
            run_tool=run_tool if specs else None,
        )

        provider = self.provider(request.profile.provider)
        calls: list[LLMCall] = []
        errors: list[str] = []

        for attempt in range(1, self._max_attempts + 1):
            started = time.monotonic()
            try:
                response, provider_attempts = await self._call_with_retries(
                    provider, provider_request
                )
            except (ProviderError, ToolNotAllowedError) as exc:
                calls.append(
                    self._charge(
                        request,
                        self._record(
                            request,
                            Usage(),
                            started,
                            attempts=attempt,
                            used=used,
                            rejected=rejected,
                            error=str(exc),
                        ),
                    )
                )
                raise

            usage = usage_for(
                request.profile.provider,
                request.profile.model,
                tokens_in=response.tokens_in,
                tokens_out=response.tokens_out,
            )
            calls.append(
                self._charge(
                    request,
                    self._record(
                        request,
                        usage,
                        started,
                        attempts=provider_attempts,
                        used=used or list(response.tools_used),
                        rejected=rejected,
                    ),
                )
            )

            errors = validate(response.output, definition.output_schema)
            if not errors:
                exceeded = self._budget.exceeded_by(self.spent(request.run_id))
                if exceeded:
                    # Se registra el gasto antes de cortar: la llamada ya se pagó.
                    raise BudgetExceededError(exceeded)
                return AgentResult(
                    agent_id=request.agent_id,
                    output=response.output,
                    usage=usage,
                    steps=response.steps,
                    tools_used=tuple(used or response.tools_used),
                    calls=tuple(calls),
                    redactions=dict(Counter(d.identifier for d in detected)),
                )

            log.warning(
                "salida inválida de %s (intento %s/%s): %s",
                request.agent_id.value,
                attempt,
                self._max_attempts,
                "; ".join(errors[:3]),
            )

        raise InvalidAgentOutputError(
            f"{definition.label} no devolvió una salida válida tras {self._max_attempts} intento(s): "
            + "; ".join(errors[:3])
        )

    def _redacted_payload(
        self, request: AgentRequest
    ) -> tuple[str, str, dict[str, Any], tuple[Detection, ...]]:
        """Prompt y contexto con los identificadores ya sustituidos.

        Se aplica siempre, no solo con `phi = "si"`: la clasificación es el juicio de una persona
        sobre lo que el requerimiento *debería* tocar, y el código puede llevar PHI igualmente.
        """
        # Primero los secretos y después la PHI: un token pegado por error tampoco sale.
        system = redact(self._scrub(request.system_prompt))
        task = redact(self._scrub(request.task_prompt))
        context, context_detections = redact_value(_scrub_deep(request.context, self._scrub))
        detections = system.detections + task.detections + context_detections
        return system.text, task.text, context, detections  # type: ignore[return-value]

    async def _call_with_retries(
        self, provider: LLMProvider, request: ProviderRequest
    ) -> tuple[Any, int]:
        """Reintenta solo lo que puede mejorar con el tiempo."""
        last: Exception | None = None
        for attempt in range(1, self._retry.attempts + 1):
            try:
                return await provider.complete(request), attempt
            except (ProviderNotConfiguredError, ProviderRefusalError, ToolNotAllowedError):
                raise
            except ProviderError as exc:
                last = exc
                if attempt == self._retry.attempts:
                    break
                delay = self._retry.delay_for(attempt)
                log.warning(
                    "proveedor falló (intento %s/%s): %s · reintento en %.1fs",
                    attempt,
                    self._retry.attempts,
                    exc,
                    delay,
                )
                await asyncio.sleep(delay)
        raise ProviderError(
            f"El proveedor falló tras {self._retry.attempts} intento(s): {last}"
        ) from last

    def _specs_for(self, request: AgentRequest, declared: tuple[str, ...]) -> tuple[ToolSpec, ...]:
        """Herramientas con implementación registrada, cruzadas con las que el agente declara."""
        if self._tools is None:
            return ()
        available = self._tools.specs_for(request.agent_id)
        return tuple(spec for spec in available if spec.name in declared)

    def _record(
        self,
        request: AgentRequest,
        usage: Usage,
        started: float,
        *,
        attempts: int,
        used: list[str],
        rejected: list[str],
        error: str = "",
    ) -> LLMCall:
        return LLMCall(
            agent_id=request.agent_id,
            provider=request.profile.provider,
            model=request.profile.model,
            prompt_version=request.profile.prompt_version,
            usage=usage,
            duration_ms=int((time.monotonic() - started) * 1000),
            attempts=attempts,
            tools_used=tuple(used),
            tools_rejected=tuple(rejected),
            at=datetime.now(timezone.utc),
            error=error,
        )

    def _charge(self, request: AgentRequest, call: LLMCall) -> LLMCall:
        """Suma el consumo de la llamada al acumulado y la deja en el registro."""
        self._spent[request.run_id] = self.spent(request.run_id) + call.usage
        self._log.setdefault(request.run_id, []).append(call)
        return call


def _scrub_deep(value: Any, scrub: Callable[[str], str]) -> Any:
    """Aplica el tachado a cualquier texto dentro de una estructura anidada."""
    if isinstance(value, str):
        return scrub(value)
    if isinstance(value, dict):
        return {k: _scrub_deep(v, scrub) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        limpio = [_scrub_deep(v, scrub) for v in value]
        return tuple(limpio) if isinstance(value, tuple) else limpio
    return value
