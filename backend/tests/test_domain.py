"""Reglas puras del dominio: entidades, políticas y hallazgos."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from orq.domain.agents import AGENTS, AGENT_ORDER, ALL_AGENTS
from orq.domain.enums import (
    AgentId,
    AttachmentKind,
    PhiClassification,
    ProviderId,
    Severity,
    Verdict,
)
from orq.domain.errors import DomainError
from orq.domain.findings import Finding, count_by_severity, dedupe
from orq.domain.orchestration import execution_waves, missing_dependencies
from orq.domain.policies import (
    apply_phi_guardrail,
    check_agent_provider,
    handles_phi,
    privacy_required,
    verdict_from_findings,
)
from orq.domain.profiles import AgentProfile

from .conftest import make_requirement


def test_requirement_requires_title_and_owner() -> None:
    with pytest.raises(DomainError):
        make_requirement(title="   ")


def test_unclassified_requirement_is_treated_as_phi() -> None:
    assert make_requirement(phi=PhiClassification.DESCONOCIDO).handles_phi is True
    assert make_requirement(phi=PhiClassification.SI).handles_phi is True
    assert make_requirement(phi=PhiClassification.NO).handles_phi is False


def test_attachment_lookup() -> None:
    requirement = make_requirement(kinds=(AttachmentKind.REPO,))
    assert requirement.has_attachment(AttachmentKind.REPO)
    assert not requirement.has_attachment(AttachmentKind.KIUWAN_CSV)
    assert requirement.repo is None  # adjunto sin repositorio conectado de verdad


def test_registry_is_consistent() -> None:
    assert set(ALL_AGENTS) == set(AGENTS)
    assert AgentId.CHAT not in AGENT_ORDER  # el asistente no participa en el flujo
    for definition in AGENTS.values():
        assert definition.tools, f"{definition.id} no declara herramientas"
        assert definition.output_schema["type"] == "object"
        for dependency in definition.depends_on:
            assert dependency in AGENTS


def test_waves_follow_the_product_flow() -> None:
    """El orden sale del grafo, no de una lista escrita a mano."""
    waves = execution_waves(AGENT_ORDER)
    assert waves[0] == (AgentId.ORCHESTRATOR,)
    assert waves[1] == (AgentId.CODE,)
    # La etapa intermedia va entera en paralelo.
    assert set(waves[2]) == {
        AgentId.TESTS,
        AgentId.KIUWAN,
        AgentId.SQL,
        AgentId.UIUX,
        AgentId.PRIVACY,
    }
    assert waves[3] == (AgentId.VTR,)
    assert waves[4] == (AgentId.VERDICT,)


def test_waves_adapt_to_the_agents_that_are_on() -> None:
    waves = execution_waves((AgentId.ORCHESTRATOR, AgentId.CODE, AgentId.PRIVACY, AgentId.VERDICT))
    assert waves == (
        (AgentId.ORCHESTRATOR,),
        (AgentId.CODE,),
        (AgentId.PRIVACY,),
        (AgentId.VERDICT,),
    )
    # Sin el agente Código, sus dependientes no esperan a nadie.
    waves = execution_waves((AgentId.ORCHESTRATOR, AgentId.TESTS, AgentId.VERDICT))
    assert waves == ((AgentId.ORCHESTRATOR,), (AgentId.TESTS,), (AgentId.VERDICT,))


def test_verdict_always_goes_last_and_orchestrator_first() -> None:
    for enabled in (
        (AgentId.VERDICT, AgentId.ORCHESTRATOR),
        (AgentId.VERDICT, AgentId.UIUX, AgentId.ORCHESTRATOR, AgentId.CODE),
    ):
        waves = execution_waves(enabled)
        assert waves[0] == (AgentId.ORCHESTRATOR,)
        assert waves[-1] == (AgentId.VERDICT,)


def test_missing_dependencies_are_reported() -> None:
    assert missing_dependencies(AgentId.TESTS, frozenset()) == (AgentId.CODE,)
    assert missing_dependencies(AgentId.TESTS, frozenset({AgentId.CODE})) == ()
    assert missing_dependencies(AgentId.VTR, frozenset({AgentId.CODE})) == (AgentId.TESTS,)


def test_output_schema_is_read_only() -> None:
    """El esquema no es editable: de él dependen el consolidador y los guardarraíles."""
    with pytest.raises(TypeError):
        AGENTS[AgentId.CODE].output_schema["type"] = "array"  # type: ignore[index]


def test_chat_agent_has_no_write_tools() -> None:
    tools = AGENTS[AgentId.CHAT].tools
    assert all(tool.startswith("get_") for tool in tools), tools


def test_phi_requires_provider_with_baa() -> None:
    blocked = check_agent_provider(AgentId.CODE, ProviderId.OPENROUTER, PhiClassification.SI)
    assert blocked and "BAA" in blocked
    assert check_agent_provider(AgentId.CODE, ProviderId.ANTHROPIC, PhiClassification.SI) is None
    assert check_agent_provider(AgentId.CODE, ProviderId.MOCK, PhiClassification.SI) is None
    # Sin PHI no hay restricción de proveedor.
    assert check_agent_provider(AgentId.CODE, ProviderId.OPENROUTER, PhiClassification.NO) is None


def test_agents_that_do_not_process_phi_are_not_blocked() -> None:
    assert check_agent_provider(AgentId.VERDICT, ProviderId.OPENROUTER, PhiClassification.SI) is None


def test_privacy_is_mandatory_with_phi() -> None:
    assert privacy_required(PhiClassification.SI, (AgentId.CODE,)) is True
    assert privacy_required(PhiClassification.DESCONOCIDO, (AgentId.CODE,)) is True
    assert privacy_required(PhiClassification.SI, (AgentId.PRIVACY,)) is False
    assert privacy_required(PhiClassification.NO, (AgentId.CODE,)) is False
    assert handles_phi(PhiClassification.NO) is False


def _finding(severity: Severity, title: str = "x", file: str = "a.py", line: int = 1) -> Finding:
    return Finding(
        id=f"{severity.value}-{title}",
        severity=severity,
        title=title,
        detail="",
        source=AgentId.CODE,
        file=file,
        line=line,
    )


def test_verdict_thresholds_are_deterministic() -> None:
    assert verdict_from_findings(()) is Verdict.APROBADO
    assert verdict_from_findings((_finding(Severity.INFO),)) is Verdict.APROBADO
    assert verdict_from_findings((_finding(Severity.MEDIA),)) is Verdict.APROBADO_CON_OBSERVACIONES
    assert verdict_from_findings((_finding(Severity.CRITICA),)) is Verdict.RECHAZADO
    tres_altas = tuple(_finding(Severity.ALTA, title=f"t{i}", line=i) for i in range(3))
    assert verdict_from_findings(tres_altas) is Verdict.RECHAZADO


def test_approval_needs_privacy_report_when_phi() -> None:
    corrected, guardrail = apply_phi_guardrail(
        Verdict.APROBADO, phi=PhiClassification.SI, privacy_executed=False
    )
    assert corrected is Verdict.APROBADO_CON_OBSERVACIONES
    assert guardrail is not None

    unchanged, none = apply_phi_guardrail(
        Verdict.APROBADO, phi=PhiClassification.SI, privacy_executed=True
    )
    assert unchanged is Verdict.APROBADO and none is None

    sin_phi, none = apply_phi_guardrail(
        Verdict.APROBADO, phi=PhiClassification.NO, privacy_executed=False
    )
    assert sin_phi is Verdict.APROBADO and none is None


def test_dedupe_keeps_the_most_severe() -> None:
    findings = (
        _finding(Severity.MEDIA, title="Consulta sin índice"),
        _finding(Severity.ALTA, title="consulta sin índice"),
        _finding(Severity.BAJA, title="Otro", file="b.py"),
    )
    result = dedupe(findings)
    assert len(result) == 2
    assert result[0].severity is Severity.ALTA


def test_count_by_severity_covers_every_level() -> None:
    counts = count_by_severity((_finding(Severity.ALTA),))
    assert counts[Severity.ALTA] == 1
    assert set(counts) == set(Severity)


def test_profile_validates_its_parameters() -> None:
    with pytest.raises(DomainError):
        AgentProfile(
            agent_id=AgentId.CODE,
            provider=ProviderId.MOCK,
            model="mock",
            system_prompt="s",
            task_prompt="t",
            temperature=9.0,
        )


def test_new_prompt_version_keeps_history() -> None:
    profile = AgentProfile(
        agent_id=AgentId.CODE,
        provider=ProviderId.MOCK,
        model="mock",
        system_prompt="s1",
        task_prompt="t1",
    )
    updated = profile.with_prompt(
        system_prompt="s2",
        task_prompt="t2",
        author="ana",
        note="ajuste",
        at=datetime(2026, 9, 15, tzinfo=timezone.utc),
    )
    assert updated.prompt_version == 2
    assert updated.versions[-1].system_prompt == "s2"
    assert profile.prompt_version == 1  # el original no se muta
