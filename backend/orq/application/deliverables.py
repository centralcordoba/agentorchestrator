"""Construye los entregables a partir de las salidas ya validadas de cada agente."""
from __future__ import annotations

from typing import Any, Iterable

from ..domain.deliverables import (
    CodeReport,
    Deliverables,
    GeneratedTest,
    KiuwanDefect,
    KiuwanReport,
    PhiDetection,
    PrivacyReport,
    SafeguardCheck,
    SqlReport,
    SqlScript,
    TestsReport,
    UiScenario,
    UiuxReport,
    VerdictReport,
    VtrReport,
    VtrSection,
)
from ..domain.enums import AgentId, AgentRunStatus, SafeguardId, Severity, Verdict
from ..domain.findings import ChangeMapEntry, Finding
from ..domain.run import Run


def _rows(output: dict[str, Any] | None, key: str) -> list[dict[str, Any]]:
    if not output:
        return []
    value = output.get(key)
    if not isinstance(value, list):
        return []
    return [row for row in value if isinstance(row, dict)]


def _findings(output: dict[str, Any] | None, source: AgentId) -> tuple[Finding, ...]:
    out: list[Finding] = []
    for index, row in enumerate(_rows(output, "findings"), start=1):
        try:
            severity = Severity(row["severity"])
        except (KeyError, ValueError):
            continue
        safeguard = None
        raw_safeguard = row.get("safeguard")
        if raw_safeguard:
            try:
                safeguard = SafeguardId(raw_safeguard)
            except ValueError:
                safeguard = None
        out.append(
            Finding(
                id=f"{source.value}-{index}",
                severity=severity,
                title=str(row.get("title", "")),
                detail=str(row.get("detail", "")),
                source=source,
                file=str(row.get("file", "")),
                line=row.get("line") if isinstance(row.get("line"), int) else None,
                suggestion=str(row.get("suggestion", "")),
                safeguard=safeguard,
            )
        )
    return tuple(out)


def _ints(values: Any) -> tuple[int, ...]:
    if not isinstance(values, Iterable) or isinstance(values, (str, bytes)):
        return ()
    return tuple(v for v in values if isinstance(v, int))


def _strings(values: Any) -> tuple[str, ...]:
    if not isinstance(values, Iterable) or isinstance(values, (str, bytes)):
        return ()
    return tuple(str(v) for v in values)


def build_deliverables(run: Run) -> Deliverables:
    outputs = {
        agent_id: execution.output
        for agent_id, execution in run.executions.items()
        if execution.status is AgentRunStatus.COMPLETADO and execution.output is not None
    }
    missing = {
        agent_id: execution.reason or execution.error or "No se ejecutó."
        for agent_id, execution in run.executions.items()
        if agent_id not in outputs and agent_id is not AgentId.ORCHESTRATOR
    }

    return Deliverables(
        code=_code(outputs.get(AgentId.CODE)),
        tests=_tests(outputs.get(AgentId.TESTS)),
        kiuwan=_kiuwan(outputs.get(AgentId.KIUWAN)),
        sql=_sql(outputs.get(AgentId.SQL)),
        uiux=_uiux(outputs.get(AgentId.UIUX)),
        privacy=_privacy(outputs.get(AgentId.PRIVACY)),
        vtr=_vtr(outputs.get(AgentId.VTR)),
        verdict=_verdict(outputs.get(AgentId.VERDICT)),
        missing=missing,
    )


def _code(output: dict[str, Any] | None) -> CodeReport | None:
    if output is None:
        return None
    change_map = tuple(
        ChangeMapEntry(
            file=str(row.get("file", "")),
            change=str(row.get("change", "modificado")),
            added=int(row.get("added", 0) or 0),
            removed=int(row.get("removed", 0) or 0),
            symbols=_strings(row.get("symbols")),
            criteria=_ints(row.get("criteria")),
        )
        for row in _rows(output, "change_map")
    )
    return CodeReport(
        summary=str(output.get("summary", "")),
        stack=str(output.get("stack", "")),
        change_map=change_map,
        findings=_findings(output, AgentId.CODE),
    )


def _tests(output: dict[str, Any] | None) -> TestsReport | None:
    if output is None:
        return None
    tests = tuple(
        GeneratedTest(
            name=str(row.get("name", "")),
            file=str(row.get("file", "")),
            status=str(row.get("status", "fallo")),
            kind=str(row.get("kind", "unitario")),
            criterion=row.get("criterion") if isinstance(row.get("criterion"), int) else None,
            duration_ms=int(row.get("duration_ms", 0) or 0),
            code=str(row.get("code", "")),
            failure_reason=str(row.get("failure_reason", "")),
        )
        for row in _rows(output, "tests")
    )
    return TestsReport(
        framework=str(output.get("framework", "")),
        command=str(output.get("command", "")),
        tests=tests,
        coverage=float(output.get("coverage", 0) or 0),
        findings=_findings(output, AgentId.TESTS),
    )


def _kiuwan(output: dict[str, Any] | None) -> KiuwanReport | None:
    if output is None:
        return None
    defects: list[KiuwanDefect] = []
    for row in _rows(output, "defects"):
        try:
            severity = Severity(row["severity"])
        except (KeyError, ValueError):
            continue
        defects.append(
            KiuwanDefect(
                rule_id=str(row.get("rule_id", "")),
                severity=severity,
                file=str(row.get("file", "")),
                rule=str(row.get("rule", "")),
                category=str(row.get("category", "")),
                line=row.get("line") if isinstance(row.get("line"), int) else None,
                false_positive=bool(row.get("false_positive", False)),
                note=str(row.get("note", "")),
            )
        )
    return KiuwanReport(
        file_name=str(output.get("file_name", "")),
        rows=int(output.get("rows", 0) or 0),
        defects=tuple(defects),
        findings=_findings(output, AgentId.KIUWAN),
    )


def _sql(output: dict[str, Any] | None) -> SqlReport | None:
    if output is None:
        return None
    scripts = tuple(
        SqlScript(
            file=str(row.get("file", "")),
            statements=int(row.get("statements", 0) or 0),
            kind=str(row.get("kind", "")),
        )
        for row in _rows(output, "scripts")
    )
    return SqlReport(
        engine=str(output.get("engine", "")),
        scripts=scripts,
        findings=_findings(output, AgentId.SQL),
    )


def _uiux(output: dict[str, Any] | None) -> UiuxReport | None:
    if output is None:
        return None
    scenarios = tuple(
        UiScenario(
            name=str(row.get("name", "")),
            status=str(row.get("status", "fallo")),
            browser=str(row.get("browser", "")),
            duration_ms=int(row.get("duration_ms", 0) or 0),
            steps=_strings(row.get("steps")),
            a11y_issues=int(row.get("a11y_issues", 0) or 0),
            failure_reason=str(row.get("failure_reason", "")),
        )
        for row in _rows(output, "scenarios")
    )
    return UiuxReport(
        base_url=str(output.get("base_url", "")),
        scenarios=scenarios,
        findings=_findings(output, AgentId.UIUX),
    )


def _privacy(output: dict[str, Any] | None) -> PrivacyReport | None:
    if output is None:
        return None
    detections = tuple(
        PhiDetection(
            identifier=str(row.get("identifier", "")),
            file=str(row.get("file", "")),
            where=str(row.get("where", "codigo")),
            line=row.get("line") if isinstance(row.get("line"), int) else None,
            # `masked` nunca debe traer el valor real; se recorta por si acaso.
            masked=str(row.get("masked", ""))[:24],
        )
        for row in _rows(output, "detections")
    )
    safeguards: list[SafeguardCheck] = []
    for row in _rows(output, "safeguards"):
        try:
            safeguard_id = SafeguardId(row["id"])
        except (KeyError, ValueError):
            continue
        safeguards.append(
            SafeguardCheck(
                id=safeguard_id,
                status=str(row.get("status", "sin_evidencia")),
                evidence=str(row.get("evidence", "")),
            )
        )
    return PrivacyReport(
        detections=detections,
        safeguards=tuple(safeguards),
        minimum_necessary=str(output.get("minimum_necessary", "")),
        findings=_findings(output, AgentId.PRIVACY),
    )


def _vtr(output: dict[str, Any] | None) -> VtrReport | None:
    if output is None:
        return None
    sections: list[VtrSection] = []
    for row in _rows(output, "sections"):
        sources: list[AgentId] = []
        for raw in _strings(row.get("sources")):
            try:
                sources.append(AgentId(raw))
            except ValueError:
                continue
        sections.append(
            VtrSection(
                title=str(row.get("title", "")),
                status=str(row.get("status", "vacia")),
                content=str(row.get("content", "")),
                sources=tuple(sources),
            )
        )
    return VtrReport(
        template_name=str(output.get("template_name", "")),
        output_name=str(output.get("output_name", "")),
        sections=tuple(sections),
    )


def _verdict(output: dict[str, Any] | None) -> VerdictReport | None:
    if output is None:
        return None
    try:
        verdict = Verdict(output["verdict"])
    except (KeyError, ValueError):
        return None
    return VerdictReport(
        verdict=verdict,
        confidence=float(output.get("confidence", 0) or 0),
        rationale=str(output.get("rationale", "")),
        guardrails=_strings(output.get("guardrails")),
    )
