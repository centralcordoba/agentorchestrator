"use client";

// Lo que un agente no produjo no se rellena: se dice qué falta y por qué, en vez de enseñar
// un ejemplo que parezca real.
import { EmptyState, SeverityBadge, Stat, VerdictBadge, fmtDuration } from "@/components/rq/ui";
import { AGENTS } from "@/lib/rq/agents";
import type { Deliverables, Finding } from "@/lib/api/types";
import type { AgentId, Severity } from "@/lib/rq/types";

export type DeliverableTab = "codigo" | "tests" | "kiuwan" | "sql" | "uiux" | "privacidad" | "vtr" | "dictamen";

/** Envoltorio común: informe presente, o el motivo por el que no está. */
function Report({
  agent,
  missing,
  present,
  children,
}: {
  agent: AgentId;
  missing: Record<string, string> | undefined;
  present: boolean;
  children: React.ReactNode;
}) {
  if (present) return <div className="space-y-4">{children}</div>;
  const reason = missing?.[agent];
  return (
    <EmptyState title={`${AGENTS[agent]?.label ?? agent} no produjo informe`}>
      {reason
        ? `Motivo: ${reason}`
        : "Este agente no estaba activo en la ejecución seleccionada."}
    </EmptyState>
  );
}

function Findings({ findings }: { findings: Finding[] | undefined }) {
  if (!findings?.length) {
    return <p className="panel px-4 py-3 text-[13px] text-ink-500">Sin hallazgos.</p>;
  }
  return (
    <ul className="panel divide-y divide-line">
      {findings.map((finding) => (
        <li key={finding.id} className="space-y-1 px-4 py-3 text-[13px]">
          <p className="flex flex-wrap items-center gap-2">
            <SeverityBadge severity={finding.severity as Severity} />
            <span className="font-medium text-ink-900">{finding.title}</span>
            {finding.file && (
              <span className="font-mono text-[11.5px] text-ink-400">
                {finding.file}
                {finding.line ? `:${finding.line}` : ""}
              </span>
            )}
          </p>
          {finding.detail && <p className="text-ink-600">{finding.detail}</p>}
          {finding.suggestion && (
            <p className="text-[12px] text-ink-500">Sugerencia: {finding.suggestion}</p>
          )}
        </li>
      ))}
    </ul>
  );
}

export function CodePanel({ deliverables: d }: { deliverables: Deliverables }) {
  const report = d.code;
  return (
    <Report agent="code" missing={d.missing} present={Boolean(report)}>
      {report && (
        <>
          <p className="panel px-4 py-3 text-[13px] leading-6 text-ink-700">{report.summary}</p>
          {report.changeMap?.length ? (
            <div className="panel overflow-x-auto">
              <table className="w-full min-w-[620px] text-left text-[13px]">
                <thead className="bg-sunken text-[11px] uppercase tracking-[0.06em] text-ink-500">
                  <tr>
                    <th className="px-4 py-2 font-semibold">Archivo</th>
                    <th className="px-4 py-2 font-semibold">Cambio</th>
                    <th className="px-4 py-2 font-semibold">Líneas</th>
                    <th className="px-4 py-2 font-semibold">Símbolos</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {report.changeMap.map((entry) => (
                    <tr key={entry.file}>
                      <td className="px-4 py-2 font-mono text-[11.5px] text-ink-700">{entry.file}</td>
                      <td className="px-4 py-2">{entry.change}</td>
                      <td className="px-4 py-2 font-mono text-[11.5px]">
                        <span className="text-ok">+{entry.added ?? 0}</span>{" "}
                        <span className="text-danger">−{entry.removed ?? 0}</span>
                      </td>
                      <td className="px-4 py-2 text-[12px] text-ink-500">
                        {(entry.symbols ?? []).join(", ") || "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="panel px-4 py-3 text-[13px] text-ink-500">
              El informe no trae mapa del cambio.
            </p>
          )}
          <Findings findings={report.findings} />
        </>
      )}
    </Report>
  );
}

export function TestsPanel({ deliverables: d }: { deliverables: Deliverables }) {
  const report = d.tests;
  return (
    <Report agent="tests" missing={d.missing} present={Boolean(report)}>
      {report && (
        <>
          <div className="grid gap-3 sm:grid-cols-3">
            <Stat label="Framework" value={report.framework || "—"} />
            <Stat label="Pruebas" value={report.tests?.length ?? 0} />
            <Stat
              label="Cobertura"
              value={report.coverage ? `${Math.round(report.coverage)} %` : "—"}
            />
          </div>
          {report.tests?.length ? (
            <ul className="panel divide-y divide-line text-[13px]">
              {report.tests.map((test) => (
                <li key={`${test.file}:${test.name}`} className="flex items-baseline gap-3 px-4 py-2">
                  <span
                    className={`chip ${test.status === "paso" ? "border-ok/30 bg-ok-soft text-ok" : "border-danger/30 bg-danger-soft text-danger"}`}
                  >
                    {test.status === "paso" ? "✓ pasa" : "✕ falla"}
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block text-ink-900">{test.name}</span>
                    <span className="block font-mono text-[11.5px] text-ink-400">{test.file}</span>
                    {test.failureReason && (
                      <span className="block text-[12px] text-danger">{test.failureReason}</span>
                    )}
                  </span>
                  {test.durationMs ? (
                    <span className="font-mono text-[11.5px] text-ink-400">
                      {fmtDuration(test.durationMs)}
                    </span>
                  ) : null}
                </li>
              ))}
            </ul>
          ) : (
            <p className="panel px-4 py-3 text-[13px] text-ink-500">
              El agente no generó pruebas en esta ejecución.
            </p>
          )}
          <Findings findings={report.findings} />
        </>
      )}
    </Report>
  );
}

export function KiuwanPanel({ deliverables: d }: { deliverables: Deliverables }) {
  const report = d.kiuwan;
  return (
    <Report agent="kiuwan" missing={d.missing} present={Boolean(report)}>
      {report && (
        <>
          <div className="grid gap-3 sm:grid-cols-3">
            <Stat label="Archivo" value={report.fileName || "—"} />
            <Stat label="Filas" value={report.rows ?? 0} />
            <Stat label="Defectos" value={report.defects?.length ?? 0} />
          </div>
          {report.defects?.length ? (
            <div className="panel overflow-x-auto">
              <table className="w-full min-w-[640px] text-left text-[13px]">
                <thead className="bg-sunken text-[11px] uppercase tracking-[0.06em] text-ink-500">
                  <tr>
                    <th className="px-4 py-2 font-semibold">Severidad</th>
                    <th className="px-4 py-2 font-semibold">Regla</th>
                    <th className="px-4 py-2 font-semibold">Ubicación</th>
                    <th className="px-4 py-2 font-semibold">Nota</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {report.defects.map((defect, index) => (
                    <tr key={`${defect.ruleId}-${index}`} className={defect.falsePositive ? "opacity-60" : ""}>
                      <td className="px-4 py-2">
                        <SeverityBadge severity={defect.severity as Severity} />
                      </td>
                      <td className="px-4 py-2">
                        <span className="block text-ink-900">{defect.rule || defect.ruleId}</span>
                        <span className="block text-[11.5px] text-ink-400">{defect.ruleId}</span>
                      </td>
                      <td className="px-4 py-2 font-mono text-[11.5px] text-ink-600">
                        {defect.file}
                        {defect.line ? `:${defect.line}` : ""}
                      </td>
                      <td className="px-4 py-2 text-[12px] text-ink-500">
                        {defect.falsePositive && (
                          <span className="chip chip-neutral mr-1">falso positivo</span>
                        )}
                        {defect.note || "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="panel px-4 py-3 text-[13px] text-ink-500">
              El CSV no trajo defectos, o todavía no se procesa de verdad (ORQ-24).
            </p>
          )}
          <Findings findings={report.findings} />
        </>
      )}
    </Report>
  );
}

export function SqlPanel({ deliverables: d }: { deliverables: Deliverables }) {
  const report = d.sql;
  return (
    <Report agent="sql" missing={d.missing} present={Boolean(report)}>
      {report && (
        <>
          <div className="grid gap-3 sm:grid-cols-2">
            <Stat label="Motor" value={report.engine || "—"} />
            <Stat label="Scripts" value={report.scripts?.length ?? 0} />
          </div>
          {report.scripts?.length ? (
            <ul className="panel divide-y divide-line text-[13px]">
              {report.scripts.map((script) => (
                <li key={script.file} className="flex items-baseline justify-between px-4 py-2">
                  <span className="font-mono text-[12px] text-ink-700">{script.file}</span>
                  <span className="text-ink-500">
                    {script.statements ?? 0} sentencia(s) {script.kind ? `· ${script.kind}` : ""}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="panel px-4 py-3 text-[13px] text-ink-500">
              No se encontraron scripts SQL en el cambio.
            </p>
          )}
          <Findings findings={report.findings} />
        </>
      )}
    </Report>
  );
}

export function UiuxPanel({ deliverables: d }: { deliverables: Deliverables }) {
  const report = d.uiux;
  return (
    <Report agent="uiux" missing={d.missing} present={Boolean(report)}>
      {report && (
        <>
          <Stat label="URL base" value={report.baseUrl || "sin configurar"} />
          {report.scenarios?.length ? (
            <ul className="panel divide-y divide-line text-[13px]">
              {report.scenarios.map((scenario) => (
                <li key={scenario.name} className="space-y-1 px-4 py-3">
                  <p className="flex items-center gap-2">
                    <span
                      className={`chip ${scenario.status === "paso" ? "border-ok/30 bg-ok-soft text-ok" : "border-danger/30 bg-danger-soft text-danger"}`}
                    >
                      {scenario.status === "paso" ? "✓" : "✕"} {scenario.status}
                    </span>
                    <span className="font-medium text-ink-900">{scenario.name}</span>
                    {scenario.browser && (
                      <span className="text-[11.5px] text-ink-400">{scenario.browser}</span>
                    )}
                  </p>
                  {(scenario.steps ?? []).length > 0 && (
                    <ol className="list-decimal space-y-0.5 pl-5 text-[12px] text-ink-600">
                      {(scenario.steps ?? []).map((step) => (
                        <li key={step}>{step}</li>
                      ))}
                    </ol>
                  )}
                  {scenario.failureReason && (
                    <p className="text-[12px] text-danger">{scenario.failureReason}</p>
                  )}
                </li>
              ))}
            </ul>
          ) : (
            <p className="panel px-4 py-3 text-[13px] text-ink-500">
              Sin escenarios: las pruebas con Playwright llegan en ORQ-6.
            </p>
          )}
          <Findings findings={report.findings} />
        </>
      )}
    </Report>
  );
}

export function PrivacyPanel({ deliverables: d }: { deliverables: Deliverables }) {
  const report = d.privacy;
  return (
    <Report agent="privacy" missing={d.missing} present={Boolean(report)}>
      {report && (
        <>
          <div className="grid gap-3 sm:grid-cols-2">
            <Stat
              label="Identificadores detectados"
              value={report.detections?.length ?? 0}
              hint="solo tipo, archivo y línea"
            />
            <Stat label="Salvaguardas evaluadas" value={report.safeguards?.length ?? 0} />
          </div>
          {report.safeguards?.length ? (
            <ul className="panel divide-y divide-line text-[13px]">
              {report.safeguards.map((safeguard) => (
                <li key={safeguard.id} className="flex items-baseline gap-3 px-4 py-2">
                  <span className="w-32 shrink-0 capitalize text-ink-900">{safeguard.id}</span>
                  <span className="chip chip-neutral">{safeguard.status.replace("_", " ")}</span>
                  <span className="min-w-0 flex-1 text-[12px] text-ink-500">
                    {safeguard.evidence}
                  </span>
                </li>
              ))}
            </ul>
          ) : null}
          {report.detections?.length ? (
            <ul className="panel divide-y divide-line text-[13px]">
              {report.detections.map((detection, index) => (
                <li key={`${detection.file}-${index}`} className="flex items-baseline gap-3 px-4 py-2">
                  <span className="chip border-teal/30 bg-teal-soft text-teal">
                    {detection.identifier}
                  </span>
                  <span className="font-mono text-[11.5px] text-ink-600">
                    {detection.file}
                    {detection.line ? `:${detection.line}` : ""}
                  </span>
                  <span className="text-[12px] text-ink-500">{detection.where}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="panel px-4 py-3 text-[13px] text-ink-500">
              Sin identificadores detectados. El valor de un identificador nunca se guarda ni se
              muestra: solo tipo, archivo y línea.
            </p>
          )}
          {report.minimumNecessary && (
            <p className="panel px-4 py-3 text-[13px] leading-6 text-ink-700">
              <span className="font-medium">Mínimo necesario:</span> {report.minimumNecessary}
            </p>
          )}
          <Findings findings={report.findings} />
        </>
      )}
    </Report>
  );
}

export function VtrPanel({ deliverables: d }: { deliverables: Deliverables }) {
  const report = d.vtr;
  return (
    <Report agent="vtr" missing={d.missing} present={Boolean(report)}>
      {report && (
        <>
          <div className="grid gap-3 sm:grid-cols-2">
            <Stat label="Plantilla" value={report.templateName || "sin plantilla"} />
            <Stat label="Documento" value={report.outputName || "no generado"} />
          </div>
          <ul className="panel divide-y divide-line text-[13px]">
            {(report.sections ?? []).map((section) => (
              <li key={section.title} className="space-y-1 px-4 py-3">
                <p className="flex items-center gap-2">
                  <span className="chip chip-neutral">{section.status}</span>
                  <span className="font-medium text-ink-900">{section.title}</span>
                </p>
                <p className="whitespace-pre-line text-ink-600">{section.content}</p>
                {(section.sources ?? []).length > 0 && (
                  <p className="text-[11.5px] text-ink-400">
                    fuentes: {(section.sources ?? []).join(", ")}
                  </p>
                )}
              </li>
            ))}
          </ul>
        </>
      )}
    </Report>
  );
}

export function VerdictPanel({ deliverables: d }: { deliverables: Deliverables }) {
  const report = d.verdict;
  const missing = Object.entries(d.missing ?? {});
  return (
    <Report agent="verdict" missing={d.missing} present={Boolean(report)}>
      {report && (
        <>
          <div className="panel flex flex-wrap items-center gap-4 p-4">
            <VerdictBadge verdict={report.verdict as never} large />
            <span className="text-[13px] text-ink-500">
              confianza {Math.round((report.confidence ?? 0) * 100)} %
            </span>
          </div>
          <p className="panel px-4 py-3 text-[13px] leading-6 text-ink-700">{report.rationale}</p>
          {(report.guardrails ?? []).length > 0 && (
            <ul className="panel space-y-1 px-4 py-3 text-[13px] text-accent">
              {(report.guardrails ?? []).map((guardrail) => (
                <li key={guardrail}>⛨ {guardrail}</li>
              ))}
            </ul>
          )}
          {missing.length > 0 && (
            <div className="panel px-4 py-3 text-[13px]">
              <p className="font-medium text-ink-900">Agentes sin resultado</p>
              <ul className="mt-1 space-y-0.5 text-ink-600">
                {missing.map(([agent, reason]) => (
                  <li key={agent}>
                    <span className="text-ink-900">{AGENTS[agent as AgentId]?.label ?? agent}:</span>{" "}
                    {reason}
                  </li>
                ))}
              </ul>
              <p className="mt-2 text-[12px] text-ink-500">
                El dictamen se emitió sin lo que estos agentes habrían aportado.
              </p>
            </div>
          )}
          <Findings findings={d.findings} />
        </>
      )}
    </Report>
  );
}
