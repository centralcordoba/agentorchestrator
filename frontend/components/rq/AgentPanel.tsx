"use client";

import { useEffect, useState } from "react";
import { AGENTS, modelLabel } from "@/lib/rq/agents";
import type { RunView } from "@/lib/rq/derive";
import { consolidatedFindings } from "@/lib/rq/scenarios";
import { agentStats } from "@/lib/rq/simulator";
import { useRq } from "@/lib/rq/store";
import type { AgentId, Requirement } from "@/lib/rq/types";
import EventRow from "./EventRow";
import ProfileEditor from "./ProfileEditor";
import { StatusDot, Tabs, VerdictBadge, fmtTokens, fmtUsd } from "./ui";

type PanelTab = "actividad" | "resultado" | "configuracion";

interface Props {
  req: Requirement;
  view: RunView | null;
  agentId: AgentId;
  initialTab?: PanelTab;
  onClose: () => void;
  onOpenDeliverable: (tab: string) => void;
}

const DELIVERABLE_TAB: Partial<Record<AgentId, string>> = {
  code: "codigo",
  tests: "codigo",
  kiuwan: "kiuwan",
  sql: "sql",
  uiux: "uiux",
  vtr: "vtr",
  verdict: "dictamen",
};

export default function AgentPanel({ req, view, agentId, initialTab = "actividad", onClose, onOpenDeliverable }: Props) {
  const { effectiveProfile } = useRq();
  const [tab, setTab] = useState<PanelTab>(initialTab);
  const a = AGENTS[agentId];

  useEffect(() => setTab(initialTab), [agentId, initialTab]);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const enabled = view ? view.run.enabledAgents.includes(agentId) : true;
  const stats = view ? agentStats(view.events, agentId, enabled) : null;
  const events = view ? view.events.filter((e) => e.agent === agentId || e.to === agentId) : [];
  const profile = view ? view.run.profiles[agentId] : effectiveProfile(agentId, req.id);
  const maxSteps = effectiveProfile(agentId, req.id).maxSteps;

  return (
    <div className="fixed inset-0 z-40 flex justify-end bg-ink-900/20" onClick={onClose}>
      <aside
        className="flex h-full w-full max-w-[560px] flex-col border-l border-line bg-surface shadow-pop"
        style={{ paddingTop: "env(safe-area-inset-top, 0px)" }}
        onClick={(e) => e.stopPropagation()}
        aria-label={`Detalle del agente ${a.label}`}
      >
        <header className="space-y-3 border-b border-line px-4 pb-0 pt-4">
          <div className="flex items-start gap-3">
            <span className="mt-1 h-8 w-1.5 rounded-full" style={{ background: a.color }} />
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <h2 className="font-serif text-[20px] leading-tight text-ink-900">{a.label}</h2>
                {stats && (
                  <span className="inline-flex items-center gap-1.5 text-[12px] text-ink-500">
                    <StatusDot status={stats.status} />
                    {stats.status}
                  </span>
                )}
              </div>
              <p className="text-[12.5px] leading-5 text-ink-500">{a.role}</p>
            </div>
            <button onClick={onClose} className="btn-ghost" aria-label="Cerrar panel">
              ✕
            </button>
          </div>
          <Tabs<PanelTab>
            value={tab}
            onChange={setTab}
            tabs={[
              { id: "actividad", label: "Actividad", badge: events.length ? <span className="chip chip-neutral">{events.length}</span> : undefined },
              { id: "resultado", label: "Resultado" },
              { id: "configuracion", label: "Modelo y prompt" },
            ]}
          />
        </header>

        <div className="flex-1 overflow-y-auto">
          {tab === "actividad" && (
            <div>
              {view && stats ? (
                <>
                  <div className="grid grid-cols-2 gap-px border-b border-line bg-line sm:grid-cols-4">
                    {[
                      ["Modelo", modelLabel(profile.provider, profile.model)],
                      ["Paso", stats.status === "omitido" ? "—" : `${stats.step}/${maxSteps}`],
                      ["Tokens", `${fmtTokens(stats.tokensIn)} / ${fmtTokens(stats.tokensOut)}`],
                      ["Coste", fmtUsd(stats.costUsd)],
                    ].map(([k, v]) => (
                      <div key={k} className="bg-surface px-3 py-2">
                        <div className="text-[10.5px] uppercase tracking-[0.08em] text-ink-400">{k}</div>
                        <div className="truncate text-[13px] font-medium text-ink-900">{v}</div>
                      </div>
                    ))}
                  </div>
                  {stats.status === "trabajando" && stats.lastTitle && (
                    <div className="flex items-center gap-2 border-b border-line bg-info-soft px-4 py-2 text-[12.5px] text-info">
                      <StatusDot status="trabajando" />
                      Ahora: {stats.lastTitle}
                    </div>
                  )}
                  {events.length ? (
                    <ol className="divide-y divide-line">
                      {[...events].reverse().map((e) => (
                        <EventRow key={e.seq} event={e} perspective={agentId} />
                      ))}
                    </ol>
                  ) : (
                    <p className="px-4 py-8 text-center text-[13px] text-ink-500">
                      {stats.status === "omitido" ? "Este agente está desactivado en esta ejecución." : "Todavía no ha empezado: espera a los agentes de los que depende."}
                    </p>
                  )}
                </>
              ) : (
                <p className="px-4 py-8 text-center text-[13px] text-ink-500">Todavía no hay ejecuciones. La actividad aparecerá aquí en vivo.</p>
              )}
            </div>
          )}

          {tab === "resultado" && (
            <div className="space-y-3 p-4">
              <ResultSummary agentId={agentId} view={view} />
              {DELIVERABLE_TAB[agentId] && view?.completed.includes(agentId) && (
                <button className="btn-ghost" onClick={() => onOpenDeliverable(DELIVERABLE_TAB[agentId]!)}>
                  ver entregable completo →
                </button>
              )}
            </div>
          )}

          {tab === "configuracion" && (
            <div className="p-4">
              <ProfileEditor
                agentId={agentId}
                requirementId={req.id}
                compact
                runningSnapshotVersion={view?.state === "en_curso" ? view.run.profiles[agentId].promptVersion : undefined}
              />
            </div>
          )}
        </div>
      </aside>
    </div>
  );
}

function ResultSummary({ agentId, view }: { agentId: AgentId; view: RunView | null }) {
  if (!view) return <p className="text-[13px] text-ink-500">Sin ejecuciones.</p>;
  if (!view.run.enabledAgents.includes(agentId)) return <p className="text-[13px] text-ink-500">Agente desactivado en esta ejecución.</p>;
  if (!view.completed.includes(agentId) && agentId !== "orchestrator")
    return <p className="text-[13px] text-ink-500">El resultado estará disponible cuando el agente termine.</p>;
  const d = view.deliverables;
  const line = (k: string, v: React.ReactNode) => (
    <div className="flex justify-between gap-3 border-b border-line py-1.5 text-[13px] last:border-0">
      <span className="text-ink-500">{k}</span>
      <span className="text-right font-medium text-ink-900">{v}</span>
    </div>
  );
  switch (agentId) {
    case "orchestrator":
      return (
        <div>
          {line("Agentes activos", view.run.enabledAgents.length)}
          {line("Omitidos", 8 - view.run.enabledAgents.length)}
          {line("Estado", view.state.replace("_", " "))}
        </div>
      );
    case "code":
      return (
        <div>
          <p className="mb-2 text-[13px] leading-5 text-ink-700">{d.code.summary}</p>
          {line("Stack", d.code.stack)}
          {line("Archivos en el mapa", d.code.changeMap.length)}
          {line("Hallazgos", d.code.findings.length)}
        </div>
      );
    case "tests": {
      const failed = d.tests.tests.filter((t) => t.status === "fallo").length;
      return (
        <div>
          {line("Framework", d.tests.framework)}
          {line("Pruebas generadas", d.tests.tests.length)}
          {line("Pasan / fallan", `${d.tests.tests.length - failed} / ${failed}`)}
          {line("Cobertura del cambio", `${d.tests.coverage} %`)}
        </div>
      );
    }
    case "kiuwan":
      return (
        <div>
          {line("Archivo", d.kiuwan.fileName)}
          {line("Filas", d.kiuwan.rows)}
          {line("Críticos", d.kiuwan.defects.filter((x) => x.severity === "critica" && !x.falsePositive).length)}
          {line("Falsos positivos", d.kiuwan.defects.filter((x) => x.falsePositive).length)}
        </div>
      );
    case "sql":
      return (
        <div>
          {line("Motor", d.sql.engine)}
          {line("Scripts", d.sql.scripts.length)}
          {line("Hallazgos", d.sql.findings.length)}
        </div>
      );
    case "uiux":
      return (
        <div>
          {line("Herramienta", "Playwright")}
          {line("Escenarios", d.uiux.scenarios.length)}
          {line("Fallan", d.uiux.scenarios.filter((s) => s.status === "fallo").length)}
          {line("Hallazgos", d.uiux.findings.length)}
        </div>
      );
    case "vtr":
      return (
        <div>
          {line("Documento", d.vtr.outputName)}
          {line("Secciones completas", `${d.vtr.sections.filter((s) => s.status === "completa").length}/${d.vtr.sections.length}`)}
        </div>
      );
    case "verdict":
      return (
        <div className="space-y-2">
          <VerdictBadge verdict={d.verdict.verdict} large />
          <p className="text-[13px] leading-5 text-ink-700">{d.verdict.rationale}</p>
          {line("Hallazgos consolidados", consolidatedFindings(d, view.completed).length)}
        </div>
      );
  }
}
