"""Casos de uso: el flujo mínimo extremo a extremo con proveedor mock."""
from __future__ import annotations

import pytest

from orq.api.container import Container
from orq.application.ports import AgentRequest, AgentResult
from orq.application.run_executor import RunExecutor
from orq.application.use_cases import (
    CreateRequirementCommand,
    NewAttachment,
    StartRunCommand,
)
from orq.domain.enums import (
    AgentId,
    AgentRunStatus,
    AttachmentKind,
    PhiClassification,
    ProviderId,
    RunStatus,
    TraceEventType,
    Verdict,
)
from orq.domain.errors import NotFoundError, PlanBlockedError
from orq.domain.run import Usage
from orq.infrastructure.ai.gateway import AIGateway

from .conftest import make_container, run_async

CRITERIOS = ("El pago se concilia el mismo día", "El portal muestra el estado")


def _create(container: Container, *, phi=PhiClassification.DESCONOCIDO, kinds=None) -> str:
    """Alta de un requerimiento de prueba (envuelve el caso de uso asíncrono)."""
    kinds = kinds if kinds is not None else (
        AttachmentKind.REPO,
        AttachmentKind.VTR_TEMPLATE,
        AttachmentKind.KIUWAN_CSV,
    )
    requirement = run_async(container.create_requirement()(
        CreateRequirementCommand(
            title="Conciliación de pagos del portal",
            description="Ajustar la pantalla de pagos y la consulta de la tabla de conciliación.",
            owner="ana",
            acceptance_criteria=CRITERIOS,
            phi=phi,
            attachments=tuple(NewAttachment(kind=k, name=f"adjunto-{k.value}") for k in kinds),
        )
    ))
    return requirement.id


def test_create_requirement_normalises_and_stores(container: Container) -> None:
    requirement_id = _create(container)
    requirement = run_async(container.get_requirement()(requirement_id))
    assert requirement.id.startswith("REQ-")
    assert requirement.acceptance_criteria == CRITERIOS
    assert len(requirement.attachments) == 3
    assert run_async(container.list_requirements()()) == [requirement]


def test_unknown_requirement_raises(container: Container) -> None:
    with pytest.raises(NotFoundError):
        run_async(container.get_requirement()("REQ-999"))


def test_suggest_plan_activates_what_it_proposes(container: Container) -> None:
    requirement_id = _create(container)
    view = run_async(container.suggest_plan()(requirement_id))
    assert view.blocked is False
    assert set(view.plan.enabled_agents) == {
        AgentId.CODE,
        AgentId.TESTS,
        AgentId.KIUWAN,
        AgentId.SQL,
        AgentId.UIUX,
        AgentId.PRIVACY,
        AgentId.VTR,
    }
    # El plan queda guardado y se puede volver a consultar.
    assert run_async(container.get_plan()(requirement_id)).plan.enabled_agents == view.plan.enabled_agents


def test_full_flow_with_mock_provider(container: Container) -> None:
    requirement_id = _create(container)
    run_async(container.suggest_plan()(requirement_id))

    run = run_async(
        container.start_run()(StartRunCommand(requirement_id=requirement_id, started_by="ana", wait=True))
    )

    assert run.status is RunStatus.COMPLETADA
    # Los no opcionales entran siempre, aunque el plan no los liste.
    assert AgentId.ORCHESTRATOR in run.enabled_agents
    assert AgentId.VERDICT in run.enabled_agents
    assert AgentId.CHAT not in run.enabled_agents

    for agent_id in run.enabled_agents:
        assert run.execution(agent_id).status is AgentRunStatus.COMPLETADO, agent_id

    view = run_async(container.get_run()(run.id, with_events=True))
    assert view.deliverables.verdict is not None
    assert view.deliverables.code is not None
    assert view.deliverables.privacy is not None

    types = [e.type for e in view.events]
    assert types[0] is TraceEventType.RUN_STARTED
    assert types[-1] is TraceEventType.RUN_COMPLETED
    assert [e.seq for e in view.events] == sorted(e.seq for e in view.events)


def test_run_freezes_provider_model_and_prompt_version(container: Container) -> None:
    requirement_id = _create(container)
    run = run_async(
        container.start_run()(StartRunCommand(requirement_id=requirement_id, started_by="ana", wait=True))
    )
    for agent_id in run.enabled_agents:
        snapshot = run.profile(agent_id)
        assert snapshot.provider is ProviderId.MOCK
        assert snapshot.prompt_version == 1

    # Cambiar el perfil después no reescribe lo congelado.
    profiles = run_async(container.profiles.defaults())
    run_async(
        container.profiles.save_default(
            profiles[AgentId.CODE].with_model(provider=ProviderId.MOCK, model="otro")
        )
    )
    assert run_async(container.get_run()(run.id)).run.profile(AgentId.CODE).model == "mock"


def test_disabled_agent_is_not_executed(container: Container) -> None:
    requirement_id = _create(container, phi=PhiClassification.NO)
    run_async(container.suggest_plan()(requirement_id))
    run = run_async(
        container.start_run()(
            StartRunCommand(
                requirement_id=requirement_id,
                started_by="ana",
                enabled_agents=(AgentId.CODE, AgentId.VTR),
                wait=True,
            )
        )
    )
    assert AgentId.UIUX not in run.enabled_agents
    assert run_async(container.get_run()(run.id)).deliverables.uiux is None


def test_plan_blocked_when_phi_and_privacy_disabled(container: Container) -> None:
    requirement_id = _create(container, phi=PhiClassification.SI)
    run_async(container.suggest_plan()(requirement_id))
    with pytest.raises(PlanBlockedError) as error:
        run_async(
            container.start_run()(
                StartRunCommand(
                    requirement_id=requirement_id,
                    started_by="ana",
                    enabled_agents=(AgentId.CODE, AgentId.VTR),
                )
            )
        )
    assert any("PHI" in reason for reason in error.value.reasons)


def test_missing_attachment_blocks_the_run(container: Container) -> None:
    requirement_id = _create(container, kinds=())
    with pytest.raises(PlanBlockedError):
        run_async(container.start_run()(StartRunCommand(requirement_id=requirement_id, started_by="ana", wait=True)))


def test_deliverables_report_what_is_missing(container: Container) -> None:
    requirement_id = _create(container, phi=PhiClassification.NO)
    run_async(container.suggest_plan()(requirement_id))
    run = run_async(
        container.start_run()(
            StartRunCommand(
                requirement_id=requirement_id,
                started_by="ana",
                enabled_agents=(AgentId.CODE, AgentId.VTR),
                wait=True,
            )
        )
    )
    deliverables = run_async(container.get_run()(run.id)).deliverables
    assert deliverables.tests is None
    assert deliverables.kiuwan is None
    # Lo que no se ejecutó no se rellena con ejemplos: se declara.
    assert AgentId.TESTS not in deliverables.missing or deliverables.missing[AgentId.TESTS]


class _FailingPrivacyGateway:
    """Pasarela que falla solo en el agente de Privacidad."""

    def __init__(self) -> None:
        self._real = AIGateway()

    async def run_agent(self, request: AgentRequest) -> AgentResult:
        if request.agent_id is AgentId.PRIVACY:
            raise RuntimeError("proveedor caído")
        return await self._real.run_agent(request)


def test_failed_agent_does_not_stop_the_run_and_blocks_approval(settings) -> None:
    container = make_container(settings, gateway=_FailingPrivacyGateway())
    requirement_id = _create(container, phi=PhiClassification.SI)
    run_async(container.suggest_plan()(requirement_id))

    run = run_async(
        container.start_run()(StartRunCommand(requirement_id=requirement_id, started_by="ana", wait=True))
    )

    assert run.status is RunStatus.COMPLETADA
    assert run.execution(AgentId.PRIVACY).status is AgentRunStatus.FALLIDO
    assert run.execution(AgentId.VERDICT).status is AgentRunStatus.COMPLETADO

    view = run_async(container.get_run()(run.id, with_events=True))
    verdict = view.deliverables.verdict
    assert verdict is not None
    # Con PHI y sin informe de Privacidad, el guardarraíl impide APROBADO.
    assert verdict.verdict is Verdict.APROBADO_CON_OBSERVACIONES
    assert verdict.guardrails
    assert any(e.type is TraceEventType.GUARDRAIL_APPLIED for e in view.events)
    assert any(e.type is TraceEventType.AGENT_FAILED for e in view.events)


def test_usage_is_the_sum_of_its_agents(container: Container) -> None:
    requirement_id = _create(container)
    run = run_async(
        container.start_run()(StartRunCommand(requirement_id=requirement_id, started_by="ana", wait=True))
    )
    total = Usage()
    for execution in run.executions.values():
        total = total + execution.usage
    assert run.usage == total


def test_every_agent_leaves_its_call_log(container: Container) -> None:
    """El coste de la ejecución cuadra con la suma de las llamadas registradas."""
    requirement_id = _create(container)
    run = run_async(
        container.start_run()(StartRunCommand(requirement_id=requirement_id, started_by="ana", wait=True))
    )

    calls = [call for execution in run.executions.values() for call in execution.calls]
    assert len(calls) == len(run.enabled_agents)
    assert round(sum(c.usage.cost_usd for c in calls), 6) == run.usage.cost_usd
    assert all(c.prompt_version == 1 and c.provider is ProviderId.MOCK for c in calls)
    assert all(c.duration_ms >= 0 for c in calls)
