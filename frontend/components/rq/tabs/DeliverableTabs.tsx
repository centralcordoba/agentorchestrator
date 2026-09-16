"use client";

import { useState } from "react";
import { AGENTS } from "@/lib/rq/agents";
import type { RunView } from "@/lib/rq/derive";
import { SEVERITY_LABELS, consolidatedFindings, sortFindings } from "@/lib/rq/scenarios";
import type { AgentId, Requirement, Severity } from "@/lib/rq/types";
import SignoffPanel from "../SignoffPanel";
import { AgentChip, EmptyState, FindingList, SeverityBadge, SourceNote, Stat, VerdictBadge, fmtDuration } from "../ui";

export function Gate({ view, agent, children }: { view: RunView | null; agent: AgentId; children: React.ReactNode }) {
  if (!view) return <EmptyState title="Sin ejecuciones">Ejecuta la revisión para ver este entregable.</EmptyState>;
  if (!view.run.enabledAgents.includes(agent))
    return <EmptyState title={`${AGENTS[agent].label} no se ejecutó`}>El agente estaba desactivado en esta ejecución. Actívalo en el plan y vuelve a ejecutar.</EmptyState>;
  if (!view.completed.includes(agent))
    return (
      <EmptyState title={view.state === "cancelado" ? "Ejecución cancelada antes de terminar" : `${AGENTS[agent].label} está trabajando…`}>
        {view.state === "cancelado" ? "Este entregable no llegó a generarse." : "El entregable aparecerá en cuanto el agente termine. Puedes seguirlo en la pestaña Ejecución."}
      </EmptyState>
    );
  return <>{children}</>;
}

// ------------------------------------------------------------------ Código y Tests
export function CodeTab({ req, view }: { req: Requirement; view: RunView | null }) {
  const [openTest, setOpenTest] = useState<string | null>(null);
  return (
    <div className="space-y-5">
      <Gate view={view} agent="code">
        {view && (
          <>
            {view.deliverables.realRepo && (
              <SourceNote real>
                Mapa del cambio leído de GitHub ({view.deliverables.realRepo.fullName} · {view.deliverables.realRepo.rangeLabel}). Los hallazgos salen de reglas deterministas sobre las líneas añadidas; la revisión con LLM llegará con el backend.
              </SourceNote>
            )}
            <section className="panel">
              <div className="panel-title">
                <span>Mapa del cambio</span>
                <span className="font-mono normal-case tracking-normal text-ink-400">{view.deliverables.code.stack}</span>
              </div>
              <p className="border-b border-line px-4 py-3 text-[13.5px] leading-6 text-ink-700">{view.deliverables.code.summary}</p>
              <div className="overflow-x-auto">
                <table className="w-full min-w-[640px] text-left text-[12.5px]">
                  <thead className="bg-sunken text-[11px] uppercase tracking-[0.06em] text-ink-500">
                    <tr>
                      <th className="px-4 py-1.5 font-semibold">Archivo</th>
                      <th className="px-4 py-1.5 font-semibold">Cambio</th>
                      <th className="px-4 py-1.5 text-right font-semibold">Líneas</th>
                      <th className="px-4 py-1.5 font-semibold">Criterios</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-line">
                    {view.deliverables.code.changeMap.map((c) => (
                      <tr key={c.file}>
                        <td className="px-4 py-2">
                          {view.deliverables.realRepo ? (
                            <a href={`${view.deliverables.realRepo.htmlUrl}/blob/${view.deliverables.realRepo.headSha}/${c.file}`} target="_blank" rel="noreferrer" className="block font-mono text-[12px] text-ink-900 hover:text-accent hover:underline">
                              {c.file}
                            </a>
                          ) : (
                            <span className="block font-mono text-[12px] text-ink-900">{c.file}</span>
                          )}
                          {c.symbols.length > 0 && <span className="font-mono text-[11px] text-ink-400">{c.symbols.join(", ")}</span>}
                        </td>
                        <td className="px-4 py-2">
                          <span className="chip chip-neutral">{c.change}</span>
                        </td>
                        <td className="px-4 py-2 text-right font-mono">
                          <span className="text-ok">+{c.added}</span> <span className="text-danger">−{c.removed}</span>
                        </td>
                        <td className="px-4 py-2">
                          <span className="flex gap-1">
                            {!c.criteria.length && (
                              <span className="text-ink-300" title="Relacionar archivos con criterios requiere el LLM">
                                —
                              </span>
                            )}
                            {c.criteria.map((i) => (
                              <span key={i} title={req.acceptanceCriteria[i]} className="flex h-5 w-5 items-center justify-center rounded-full bg-accent-soft font-mono text-[10.5px] font-semibold text-accent">
                                {i + 1}
                              </span>
                            ))}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
            <section className="panel">
              <div className="panel-title">
                <span>Hallazgos de código</span>
                <span className="font-mono normal-case tracking-normal text-ink-400">{view.deliverables.code.findings.length}</span>
              </div>
              <FindingList findings={sortFindings(view.deliverables.code.findings)} />
            </section>
          </>
        )}
      </Gate>

      <Gate view={view} agent="tests">
        {view && (
          <section className="panel">
            {view.deliverables.realRepo && (
              <div className="border-b border-line p-3">
                <SourceNote real={false}>Estas pruebas son del escenario de ejemplo: generarlas y ejecutarlas sobre {view.deliverables.realRepo.fullName} requiere el backend.</SourceNote>
              </div>
            )}
            <div className="panel-title">
              <span>Pruebas generadas y ejecutadas en local</span>
              <span className="font-mono normal-case tracking-normal text-ink-400">
                {view.deliverables.tests.framework} · cobertura {view.deliverables.tests.coverage} %
              </span>
            </div>
            <div className="border-b border-line bg-sunken/60 px-4 py-2 font-mono text-[11.5px] text-ink-700">$ {view.deliverables.tests.command}</div>
            <ul className="divide-y divide-line">
              {view.deliverables.tests.tests.map((t) => (
                <li key={t.name} className="px-4 py-2.5">
                  <button className="flex w-full flex-wrap items-center gap-2 text-left" onClick={() => setOpenTest(openTest === t.name ? null : t.name)} aria-expanded={openTest === t.name}>
                    <span className={`chip ${t.status === "paso" ? "border-ok/30 bg-ok-soft text-ok" : "border-danger/30 bg-danger-soft text-danger"}`}>
                      {t.status === "paso" ? "✓ pasa" : "✕ falla"}
                    </span>
                    <span className="font-mono text-[12.5px] text-ink-900">{t.name}</span>
                    <span className="chip chip-neutral">{t.kind}</span>
                    <span title={req.acceptanceCriteria[t.criterion]} className="text-[11.5px] text-ink-500">
                      criterio {t.criterion + 1}
                    </span>
                    <span className="ml-auto font-mono text-[11px] text-ink-400">
                      {t.file} · {t.durationMs} ms {openTest === t.name ? "▾" : "▸"}
                    </span>
                  </button>
                  {t.failureReason && <p className="mt-1 text-[12.5px] leading-5 text-danger">{t.failureReason}</p>}
                  {openTest === t.name && <pre className="mt-2 overflow-x-auto rounded-lg bg-ink-900 px-3 py-2 font-mono text-[11.5px] leading-5 text-white">{t.code}</pre>}
                </li>
              ))}
            </ul>
          </section>
        )}
      </Gate>
    </div>
  );
}

// ------------------------------------------------------------------ Kiuwan
const SEVS: Severity[] = ["critica", "alta", "media", "baja", "info"];

export function KiuwanTab({ view }: { view: RunView | null }) {
  const [hideFp, setHideFp] = useState(false);
  return (
    <Gate view={view} agent="kiuwan">
      {view && (
        <div className="space-y-4">
          <SourceNote real={false}>Defectos del escenario de ejemplo. El análisis del CSV adjunto se conectará cuando esté el formato de doc/kiwuan.</SourceNote>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <Stat label="Filas del CSV" value={view.deliverables.kiuwan.rows} hint={view.deliverables.kiuwan.fileName} />
            <Stat label="Críticos reales" value={view.deliverables.kiuwan.defects.filter((d) => d.severity === "critica" && !d.falsePositive).length} hint="bloquean el dictamen" />
            <Stat label="Falsos positivos" value={view.deliverables.kiuwan.defects.filter((d) => d.falsePositive).length} hint="confirmados con Código" />
            <Stat label="Relevantes" value={view.deliverables.kiuwan.defects.length} hint="tras agrupar repetidos" />
          </div>
          <section className="panel">
            <div className="panel-title">
              <span>Defectos priorizados</span>
              <label className="flex items-center gap-1.5 normal-case tracking-normal">
                <input type="checkbox" checked={hideFp} onChange={(e) => setHideFp(e.target.checked)} />
                ocultar falsos positivos
              </label>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[720px] text-left text-[12.5px]">
                <thead className="bg-sunken text-[11px] uppercase tracking-[0.06em] text-ink-500">
                  <tr>
                    <th className="px-4 py-1.5 font-semibold">Severidad</th>
                    <th className="px-4 py-1.5 font-semibold">Regla</th>
                    <th className="px-4 py-1.5 font-semibold">Ubicación</th>
                    <th className="px-4 py-1.5 font-semibold">Análisis del agente</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {[...view.deliverables.kiuwan.defects]
                    .sort((a, b) => SEVS.indexOf(a.severity) - SEVS.indexOf(b.severity))
                    .filter((d) => !hideFp || !d.falsePositive)
                    .map((d) => (
                      <tr key={d.ruleId + d.line} className={d.falsePositive ? "opacity-60" : ""}>
                        <td className="px-4 py-2">
                          <SeverityBadge severity={d.severity} />
                        </td>
                        <td className="px-4 py-2">
                          <span className="block text-ink-900">{d.rule}</span>
                          <span className="font-mono text-[10.5px] text-ink-400">
                            {d.ruleId} · {d.category}
                          </span>
                        </td>
                        <td className="px-4 py-2 font-mono text-[11.5px] text-ink-700">
                          {d.file}:{d.line}
                        </td>
                        <td className="px-4 py-2 text-ink-700">
                          {d.falsePositive && <span className="chip chip-neutral mr-1">falso positivo</span>}
                          {d.note || "—"}
                        </td>
                      </tr>
                    ))}
                </tbody>
              </table>
            </div>
          </section>
        </div>
      )}
    </Gate>
  );
}

// ------------------------------------------------------------------ SQL
export function SqlTab({ view }: { view: RunView | null }) {
  return (
    <Gate view={view} agent="sql">
      {view && (
        <div className="space-y-4">
          {view.deliverables.realRepo && <SourceNote real>Scripts SQL detectados en el diff de {view.deliverables.realRepo.fullName}, revisados con reglas deterministas.</SourceNote>}
          <section className="panel">
            <div className="panel-title">
              <span>Scripts analizados</span>
              <span className="font-mono normal-case tracking-normal text-ink-400">{view.deliverables.sql.engine}</span>
            </div>
            {view.deliverables.sql.scripts.length ? (
              <ul className="divide-y divide-line">
                {view.deliverables.sql.scripts.map((s) => (
                  <li key={s.file} className="flex flex-wrap items-center gap-2 px-4 py-2 text-[12.5px]">
                    <span className="font-mono text-ink-900">{s.file}</span>
                    <span className="chip chip-neutral">{s.kind}</span>
                    <span className="ml-auto text-ink-500">{s.statements} sentencias</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="px-4 py-6 text-center text-[13px] text-ink-500">No se encontraron scripts ni consultas SQL en el cambio.</p>
            )}
          </section>
          <section className="panel">
            <div className="panel-title">
              <span>Hallazgos SQL</span>
            </div>
            <FindingList findings={sortFindings(view.deliverables.sql.findings)} />
          </section>
        </div>
      )}
    </Gate>
  );
}

// ------------------------------------------------------------------ UI/UX
export function UiuxTab({ view }: { view: RunView | null }) {
  return (
    <Gate view={view} agent="uiux">
      {view && (
        <div className="space-y-4">
          <SourceNote real={false}>Escenarios de ejemplo. Ejecutar Playwright contra la aplicación requiere el backend.</SourceNote>
          <section className="panel">
            <div className="panel-title">
              <span>Escenarios Playwright</span>
              <span className="font-mono normal-case tracking-normal text-ink-400">{view.deliverables.uiux.baseUrl}</span>
            </div>
            {view.deliverables.uiux.scenarios.length ? (
              <div className="grid gap-px bg-line md:grid-cols-2">
                {view.deliverables.uiux.scenarios.map((s) => (
                  <article key={s.name} className="space-y-2 bg-surface p-4">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className={`chip ${s.status === "paso" ? "border-ok/30 bg-ok-soft text-ok" : "border-danger/30 bg-danger-soft text-danger"}`}>
                        {s.status === "paso" ? "✓ pasa" : "✕ falla"}
                      </span>
                      <span className="text-[13.5px] font-medium text-ink-900">{s.name}</span>
                    </div>
                    {/* marcador de captura: en el backend real sería la imagen generada por Playwright */}
                    <div className="flex h-32 max-w-full items-center justify-center rounded-lg border border-dashed border-line-strong bg-sunken font-mono text-[11px] text-ink-400">
                      captura · {s.browser}
                    </div>
                    <ol className="list-decimal space-y-0.5 pl-5 text-[12.5px] text-ink-700">
                      {s.steps.map((st) => (
                        <li key={st}>{st}</li>
                      ))}
                    </ol>
                    {s.failureReason && <p className="text-[12.5px] leading-5 text-danger">{s.failureReason}</p>}
                    <p className="font-mono text-[11px] text-ink-400">
                      {s.browser} · {fmtDuration(s.durationMs)} · {s.a11yIssues} incidencias de accesibilidad
                    </p>
                  </article>
                ))}
              </div>
            ) : (
              <p className="px-4 py-6 text-center text-[13px] text-ink-500">No se detectaron pantallas afectadas por el cambio.</p>
            )}
          </section>
          <section className="panel">
            <div className="panel-title">
              <span>Hallazgos de UI/UX</span>
            </div>
            <FindingList findings={sortFindings(view.deliverables.uiux.findings)} />
          </section>
        </div>
      )}
    </Gate>
  );
}

// ------------------------------------------------------------------ VTR
const SECTION_CLASS = {
  completa: "border-ok/30 bg-ok-soft text-ok",
  parcial: "border-warn/30 bg-warn-soft text-warn",
  vacia: "chip-neutral text-ink-500",
} as const;

export function VtrTab({ view }: { view: RunView | null }) {
  const [notice, setNotice] = useState(false);
  return (
    <Gate view={view} agent="vtr">
      {view && (
        <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_280px]">
          <section className="panel">
            <div className="panel-title">
              <span>{view.deliverables.vtr.outputName}</span>
              <span className="font-mono normal-case tracking-normal text-ink-400">plantilla {view.deliverables.vtr.templateName}</span>
            </div>
            <div className="mx-auto max-w-[720px] space-y-5 px-5 py-6">
              {view.deliverables.vtr.sections.map((s) => (
                <div key={s.title}>
                  <div className="flex flex-wrap items-center gap-2">
                    <h3 className="font-serif text-[16px] text-ink-900">{s.title}</h3>
                    <span className={`chip ${SECTION_CLASS[s.status]}`}>{s.status}</span>
                    <span className="ml-auto flex gap-1">
                      {s.sources.map((a) => (
                        <AgentChip key={a} id={a} />
                      ))}
                    </span>
                  </div>
                  <p className="mt-1 text-[13.5px] leading-6 text-ink-700">{s.content}</p>
                </div>
              ))}
            </div>
          </section>
          <aside className="space-y-3">
            <SourceNote real={Boolean(view.deliverables.realRepo)}>
              {view.deliverables.realRepo ? "Las secciones 2, 3 y 4 usan el diff real; el resto es de ejemplo." : "Contenido del escenario de ejemplo."}
            </SourceNote>
            <div className="panel space-y-3 p-4">
              <Stat label="Secciones completas" value={`${view.deliverables.vtr.sections.filter((s) => s.status === "completa").length}/${view.deliverables.vtr.sections.length}`} />
              <button className="btn-primary w-full" onClick={() => setNotice(true)}>
                Descargar .docx
              </button>
              {notice && <p className="text-[12px] leading-5 text-ink-500">En el prototipo no se genera el archivo: la descarga llegará con el backend (python-docx sobre la plantilla).</p>}
            </div>
            <p className="px-1 text-[12px] leading-5 text-ink-500">Cada sección indica qué agentes aportaron su contenido. Las secciones sin fuente quedan como parciales o vacías para completarlas a mano.</p>
          </aside>
        </div>
      )}
    </Gate>
  );
}

// ------------------------------------------------------------------ Dictamen
export function VerdictTab({ req, view }: { req: Requirement; view: RunView | null }) {
  return (
    <Gate view={view} agent="verdict">
      {view && (
        <div className="space-y-4">
          <SignoffPanel req={req} view={view} />
          <section className="panel space-y-3 p-5">
            <div className="flex flex-wrap items-center gap-3">
              <span className="text-[11px] font-semibold uppercase tracking-[0.08em] text-ink-500">Recomendación de la IA</span>
              <VerdictBadge verdict={view.deliverables.verdict.verdict} large />
              <span className="font-mono text-[12px] text-ink-500">confianza {Math.round(view.deliverables.verdict.confidence * 100)} %</span>
            </div>
            <p className="max-w-3xl font-serif text-[18px] leading-7 text-ink-900">{view.deliverables.verdict.rationale}</p>
            {view.deliverables.verdict.guardrails.length > 0 && (
              <ul className="space-y-1">
                {view.deliverables.verdict.guardrails.map((g) => (
                  <li key={g} className="flex gap-2 text-[12.5px] leading-5 text-accent">
                    <span aria-hidden>⚑</span>
                    {g}
                  </li>
                ))}
              </ul>
            )}
          </section>
          <SeveritySummary view={view} />
          <section className="panel">
            <div className="panel-title">
              <span>Hallazgos consolidados (sin duplicados)</span>
              <span className="font-mono normal-case tracking-normal text-ink-400">{consolidatedFindings(view.deliverables, view.completed).length}</span>
            </div>
            <FindingList findings={consolidatedFindings(view.deliverables, view.completed)} />
          </section>
        </div>
      )}
    </Gate>
  );
}

function SeveritySummary({ view }: { view: RunView }) {
  const f = consolidatedFindings(view.deliverables, view.completed);
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
      {SEVS.map((s) => (
        <Stat key={s} label={SEVERITY_LABELS[s]} value={f.filter((x) => x.severity === s).length} />
      ))}
    </div>
  );
}
