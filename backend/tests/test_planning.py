"""Sugerencia de plan y avisos: las reglas deterministas portadas del prototipo."""
from __future__ import annotations

from orq.domain.enums import AgentId, AttachmentKind, PhiClassification, WarningLevel
from orq.domain.planning import locked_reason, plan_warnings, suggest_plan

from .conftest import START, make_requirement


def _suggestion(requirement, agent_id: AgentId):
    plan = suggest_plan(requirement, now=START)
    item = plan.item(agent_id)
    assert item is not None
    return item


def test_code_and_tests_need_a_repository() -> None:
    sin_repo = make_requirement(kinds=())
    assert _suggestion(sin_repo, AgentId.CODE).suggested is False
    assert _suggestion(sin_repo, AgentId.TESTS).suggested is False

    con_repo = make_requirement(kinds=(AttachmentKind.REPO,))
    assert _suggestion(con_repo, AgentId.CODE).suggested is True
    assert _suggestion(con_repo, AgentId.TESTS).suggested is True


def test_kiuwan_needs_its_csv() -> None:
    assert _suggestion(make_requirement(kinds=()), AgentId.KIUWAN).suggested is False
    assert _suggestion(make_requirement(kinds=(AttachmentKind.KIUWAN_CSV,)), AgentId.KIUWAN).suggested


def test_sql_is_suggested_when_the_text_mentions_the_database() -> None:
    requirement = make_requirement(
        kinds=(), description="Hay que revisar la consulta de la tabla de conciliación."
    )
    item = _suggestion(requirement, AgentId.SQL)
    assert item.suggested is True
    assert "consulta" in item.reason or "tabla" in item.reason


def test_accents_do_not_break_word_detection() -> None:
    """El límite de palabra propio existe porque \\b no entiende las tildes."""
    requirement = make_requirement(kinds=(), description="Falta la migración del índice.")
    assert _suggestion(requirement, AgentId.SQL).suggested is True

    # «consultar» no es «consulta»: no debe disparar por coincidencia parcial.
    otro = make_requirement(kinds=(), title="Permitir consultarlo", description="Sin base.")
    assert _suggestion(otro, AgentId.SQL).suggested is False


def test_privacy_is_suggested_unless_classified_without_phi() -> None:
    assert _suggestion(make_requirement(phi=PhiClassification.SI), AgentId.PRIVACY).suggested
    assert _suggestion(make_requirement(phi=PhiClassification.DESCONOCIDO), AgentId.PRIVACY).suggested
    assert not _suggestion(make_requirement(phi=PhiClassification.NO), AgentId.PRIVACY).suggested


def test_vtr_is_always_suggested_and_asks_for_the_template() -> None:
    item = _suggestion(make_requirement(kinds=()), AgentId.VTR)
    assert item.suggested is True
    assert "plantilla" in item.reason.lower()


def test_missing_attachment_blocks_the_plan() -> None:
    requirement = make_requirement(kinds=())
    plan = suggest_plan(requirement, now=START)
    warnings = plan_warnings(requirement, plan)
    blocking = [w for w in warnings if w.level is WarningLevel.BLOQUEO]
    assert any(w.agent_id is AgentId.VTR for w in blocking)


def test_disabled_dependency_is_only_a_warning() -> None:
    requirement = make_requirement()
    plan = suggest_plan(requirement, now=START)
    plan = plan.toggled(AgentId.CODE, enabled=False, by="ana")
    warnings = plan_warnings(requirement, plan)
    dependientes = [w for w in warnings if w.agent_id is AgentId.TESTS]
    assert dependientes and all(w.level is WarningLevel.AVISO for w in dependientes)


def test_privacy_cannot_be_dropped_when_phi() -> None:
    requirement = make_requirement(phi=PhiClassification.SI)
    plan = suggest_plan(requirement, now=START).toggled(AgentId.PRIVACY, enabled=False, by="ana")
    warnings = plan_warnings(requirement, plan)
    assert any(w.agent_id is AgentId.PRIVACY and w.blocks for w in warnings)
    assert locked_reason(requirement, AgentId.PRIVACY) is not None
    assert locked_reason(make_requirement(phi=PhiClassification.NO), AgentId.PRIVACY) is None
