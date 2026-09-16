"""Proveedor de pruebas: determinista, sin red y sin coste."""
from __future__ import annotations

import asyncio
from typing import Any

from ....domain.enums import AgentId, ProviderId, Severity
from ....domain.findings import Finding
from ....domain.policies import verdict_from_findings
from . import demo_data as demo
from .base import ProviderRequest, ProviderResponse


class MockLLMProvider:
    """Devuelve una salida válida para el esquema de cada agente.

    Dos modos:

    - **Normal** (el de las pruebas): no inventa nada. Donde no hay análisis, no hay resultado.
    - **Demo** (`AI_MOCK_RICH=1`): rellena los informes con contenido de ejemplo coherente entre
      agentes, para poder enseñar el flujo. Cada texto lleva su marca de origen y el dictamen sale
      con confianza 0, porque detrás no hay ningún análisis.

    En los dos casos el texto deja claro que la salida es simulada: nunca debe confundirse con
    una revisión real.
    """

    id = ProviderId.MOCK
    NOTE = "Salida simulada del proveedor mock: no hay análisis real."

    def __init__(self, delay_ms: int = 0, *, rich: bool = False) -> None:
        self._delay_s = max(0, delay_ms) / 1000
        self._rich = rich

    async def complete(self, request: ProviderRequest) -> ProviderResponse:
        if self._delay_s:
            await asyncio.sleep(self._delay_s)
        builder = getattr(self, f"_{request.agent_id.value}", None)
        output = builder(request.context) if builder else {}

        tools_used: tuple[str, ...] = ()
        steps = 1
        # El mock no dice haber usado una herramienta que no existe.
        if request.tools and request.run_tool is not None:
            tool = request.tools[0]
            await request.run_tool(tool.name, {})
            tools_used = (tool.name,)
            steps = 2

        tokens_in = len(request.system_prompt) + len(request.task_prompt) + len(str(request.context))
        return ProviderResponse(
            output=output,
            tokens_in=tokens_in // 4,
            tokens_out=len(str(output)) // 4,
            steps=steps,
            tools_used=tools_used,
        )

    def _orchestrator(self, context: dict[str, Any]) -> dict[str, Any]:
        items = context.get("plan") or []
        return {
            "items": [
                {
                    "agent": str(item.get("agent", "")),
                    "suggested": bool(item.get("suggested", False)),
                    "reason": str(item.get("reason", "")),
                }
                for item in items
            ]
        }

    def _code(self, context: dict[str, Any]) -> dict[str, Any]:
        if self._rich:
            texto = str(context.get("title", ""))
            return {
                "summary": (
                    "5 archivos tocados: la lógica de conciliación, la vista del portal y una "
                    f"migración de base de datos. {demo.NOTE}"
                ),
                "stack": "Python 3.12 · React · PostgreSQL",
                "change_map": demo.change_map(),
                "findings": demo.code_findings(texto),
            }
        repo = context.get("repo") or {}
        files = repo.get("files") or []
        change_map = [
            {
                "file": str(f.get("path", "")),
                "change": _change_of(str(f.get("status", "modified"))),
                "added": 0,
                "removed": 0,
                "symbols": [],
                "criteria": [],
            }
            for f in files
        ]
        summary = (
            f"{len(change_map)} archivo(s) en el diff de {repo.get('full_name', 'sin repositorio')}. {self.NOTE}"
            if change_map
            else f"Sin repositorio conectado. {self.NOTE}"
        )
        return {"summary": summary, "stack": "", "change_map": change_map, "findings": []}

    def _tests(self, context: dict[str, Any]) -> dict[str, Any]:
        if self._rich:
            return demo.tests_report(str(context.get("title", "")))
        return {"framework": "", "command": "", "tests": [], "coverage": 0, "findings": []}

    def _kiuwan(self, context: dict[str, Any]) -> dict[str, Any]:
        attachment = _attachment(context, "kiuwan_csv")
        if self._rich:
            return demo.kiuwan_report(
                str(context.get("title", "")),
                attachment.get("name", "kiuwan.csv") if attachment else "kiuwan.csv",
            )
        return {
            "file_name": attachment.get("name", "") if attachment else "",
            "rows": 0,
            "defects": [],
            "findings": [],
        }

    def _sql(self, context: dict[str, Any]) -> dict[str, Any]:
        if self._rich:
            return demo.sql_report()
        scripts = [
            {"file": entry.get("file", ""), "statements": 0, "kind": ""}
            for entry in context.get("change_map") or []
            if str(entry.get("file", "")).lower().endswith(".sql")
        ]
        return {"engine": "", "scripts": scripts, "findings": []}

    def _uiux(self, context: dict[str, Any]) -> dict[str, Any]:
        if self._rich:
            return demo.uiux_report()
        return {"base_url": "", "scenarios": [], "findings": []}

    def _privacy(self, context: dict[str, Any]) -> dict[str, Any]:
        if self._rich:
            return demo.privacy_report(str(context.get("phi", "desconocido")))
        # Sin análisis real no se afirma que se cumple: todo queda sin evidencia.
        safeguards = [
            {"id": safeguard, "status": "sin_evidencia", "evidence": self.NOTE}
            for safeguard in ("acceso", "auditoria", "integridad", "autenticacion", "transmision")
        ]
        return {
            "detections": [],
            "safeguards": safeguards,
            "minimum_necessary": self.NOTE,
            "findings": [],
        }

    def _vtr(self, context: dict[str, Any]) -> dict[str, Any]:
        attachment = _attachment(context, "vtr_template")
        sources = sorted(str(k) for k in (context.get("agent_outputs") or {}))
        if self._rich:
            return demo.vtr_report(attachment.get("name", "") if attachment else "", sources)
        return {
            "template_name": attachment.get("name", "") if attachment else "",
            "output_name": "",
            "sections": [
                {
                    "title": "Sin plantilla procesada",
                    "status": "vacia",
                    "content": self.NOTE,
                    "sources": sources,
                }
            ],
        }

    def _verdict(self, context: dict[str, Any]) -> dict[str, Any]:
        findings = _findings_from(context.get("agent_outputs") or {})
        verdict = verdict_from_findings(findings)
        return {
            "verdict": verdict.value,
            "confidence": 0.0,
            "rationale": (
                f"{len(findings)} hallazgo(s) de los agentes ejecutados. {self.NOTE} "
                "La confianza es 0 porque ningún agente hizo análisis real."
            ),
            "guardrails": [],
        }

    # Sin modo demo a propósito: el veredicto lo calculan las reglas del dominio.

    def _chat(self, context: dict[str, Any]) -> dict[str, Any]:
        return {"answer": self.NOTE, "citations": [], "fallback": True}


def _change_of(status: str) -> str:
    return {"added": "nuevo", "removed": "eliminado"}.get(status, "modificado")


def _attachment(context: dict[str, Any], kind: str) -> dict[str, Any] | None:
    for attachment in context.get("attachments") or []:
        if attachment.get("kind") == kind:
            return attachment
    return None


def _findings_from(outputs: dict[str, Any]) -> tuple[Finding, ...]:
    """Recoge los hallazgos de los demás agentes para aplicar los umbrales del dictamen."""
    collected: list[Finding] = []
    for agent, output in outputs.items():
        if not isinstance(output, dict):
            continue
        try:
            source = AgentId(agent)
        except ValueError:
            continue
        for index, row in enumerate(output.get("findings") or [], start=1):
            if not isinstance(row, dict):
                continue
            try:
                severity = Severity(row["severity"])
            except (KeyError, ValueError):
                continue
            collected.append(
                Finding(
                    id=f"{agent}-{index}",
                    severity=severity,
                    title=str(row.get("title", "")),
                    detail=str(row.get("detail", "")),
                    source=source,
                    file=str(row.get("file", "")),
                    line=row.get("line") if isinstance(row.get("line"), int) else None,
                )
            )
    return tuple(collected)
