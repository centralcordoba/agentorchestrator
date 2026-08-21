"use client";

import { computeNodeStats } from "@/lib/trace";
import { AGENT_LABELS, DECISION_DOT, DECISION_STYLES, type AgentName, type RunEvent, type SymbolResult } from "@/lib/types";

interface Props {
  symbols: string[];
  results: Record<string, SymbolResult>;
  events: RunEvent[];
  selectedSymbol: string | "all";
  onSelectSymbol: (s: string | "all") => void;
  onInspect: (e: RunEvent) => void;
}

function Confidence({ value }: { value: number }) {
  const pct = Math.round(Math.max(0, Math.min(1, value)) * 100);
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-16 overflow-hidden rounded-full bg-line">
        <div className="h-full rounded-full bg-ink-700" style={{ width: `${pct}%` }} />
      </div>
      <span className="font-mono text-[11px] text-ink-500">{pct}%</span>
    </div>
  );
}

function currentStage(events: RunEvent[], symbol: string): string {
  const stats = computeNodeStats(events, symbol);
  const working = (Object.keys(stats) as AgentName[]).filter((a) => stats[a].status === "working" && a !== "orchestrator");
  if (working.length) return `en curso · ${working.map((a) => AGENT_LABELS[a]).join(", ")}`;
  return events.some((e) => e.symbol === symbol) ? "en cola…" : "pendiente";
}

/** Muestra lo que habrían dicho las reglas cuando el agente (en modo LLM) opinó distinto. */
function RuleRef({ value, current, mode }: { value: unknown; current: unknown; mode?: string }) {
  if (mode !== "llm" || value === undefined || value === null) return null;
  if (value === current) return <span className="ml-1 text-[10px] text-ink-300" title="Coincide con las reglas">= reglas</span>;
  return (
    <span className="ml-1 rounded bg-warn-soft px-1 text-[10px] text-warn" title="Las reglas habrían dicho otra cosa">
      reglas: {String(value)}
    </span>
  );
}

const RISK_STYLE: Record<string, string> = {
  BAJO: "text-ok",
  MEDIO: "text-warn",
  ALTO: "text-danger",
};

export default function DecisionTable({ symbols, results, events, selectedSymbol, onSelectSymbol, onInspect }: Props) {
  const findDecisionEvent = (symbol: string) =>
    [...events].reverse().find((e) => e.symbol === symbol && e.type === "message_sent" && e.message?.type === "decision");

  return (
    <div className="panel overflow-hidden">
      <div className="panel-title">
        <span>Decisiones · señales experimentales</span>
        <button
          onClick={() => onSelectSymbol("all")}
          className={`rounded-md px-1.5 py-0.5 text-[10.5px] normal-case tracking-normal transition ${
            selectedSymbol === "all" ? "bg-ink-900 text-white" : "text-ink-400 hover:bg-sunken hover:text-ink-700"
          }`}
        >
          ver todos
        </button>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-left text-[12.5px]">
          <thead className="bg-sunken/60 text-[10.5px] uppercase tracking-[0.08em] text-ink-500">
            <tr className="border-b border-line">
              <th className="px-4 py-2 font-semibold">Símbolo</th>
              <th className="px-3 py-2 font-semibold">Decisión</th>
              <th className="px-3 py-2 font-semibold">Confianza</th>
              <th className="px-3 py-2 font-semibold">Técnico</th>
              <th className="px-3 py-2 font-semibold">Riesgo</th>
              <th className="px-3 py-2 font-semibold">Escéptico</th>
              <th className="px-3 py-2 font-semibold">Datos</th>
              <th className="px-3 py-2 font-semibold">Justificación</th>
            </tr>
          </thead>
          <tbody>
            {symbols.length === 0 && (
              <tr>
                <td colSpan={8} className="px-4 py-6 text-center text-ink-400">
                  Sin ejecución activa.
                </td>
              </tr>
            )}
            {symbols.map((symbol) => {
              const r = results[symbol];
              const tech = r?.opinions.find((o) => o.agent === "technical");
              const risk = r?.opinions.find((o) => o.agent === "risk");
              const skeptic = r?.opinions.find((o) => o.agent === "skeptic");
              const decisionOp = r?.opinions.find((o) => o.agent === "decision");
              const selected = selectedSymbol === symbol;
              return (
                <tr
                  key={symbol}
                  onClick={() => onSelectSymbol(selected ? "all" : symbol)}
                  className={`cursor-pointer border-b border-line/70 align-top transition hover:bg-sunken/70 ${
                    selected ? "bg-accent-soft/50 shadow-[inset_3px_0_0_#C2562E]" : ""
                  }`}
                >
                  <td className="px-4 py-2.5 font-mono font-semibold text-ink-900">{symbol}</td>
                  <td className="px-3 py-2.5">
                    {r ? (
                      <>
                        <span className={`chip font-sans font-semibold ${DECISION_STYLES[r.decision]}`}>
                          <span className="inline-block h-1.5 w-1.5 rounded-full" style={{ background: DECISION_DOT[r.decision] }} />
                          {r.decision}
                        </span>
                        <RuleRef value={decisionOp?.rule_reference?.decision} current={r.decision} mode={decisionOp?.mode} />
                      </>
                    ) : (
                      <span className="text-ink-400">{currentStage(events, symbol)}</span>
                    )}
                  </td>
                  <td className="px-3 py-2.5">{r ? <Confidence value={r.confidence} /> : <span className="text-ink-300">—</span>}</td>
                  <td className="px-3 py-2.5 font-mono text-ink-700">
                    {tech?.stance ?? <span className="text-ink-300">—</span>}
                    <RuleRef value={tech?.rule_reference?.stance} current={tech?.stance} mode={tech?.mode} />
                  </td>
                  <td className={`px-3 py-2.5 font-mono ${risk ? RISK_STYLE[risk.risk_level ?? ""] ?? "" : "text-ink-300"}`}>
                    {risk?.risk_level ?? "—"}
                    <RuleRef value={risk?.rule_reference?.risk_level} current={risk?.risk_level} mode={risk?.mode} />
                  </td>
                  <td className="px-3 py-2.5">
                    {skeptic ? (
                      skeptic.agrees ? (
                        <span className="text-ok">de acuerdo</span>
                      ) : (
                        <span className="text-rose">discrepa{r && r.disagreements ? ` (${r.disagreements})` : ""}</span>
                      )
                    ) : (
                      <span className="text-ink-300">—</span>
                    )}
                  </td>
                  <td className="px-3 py-2.5 font-mono text-[11.5px] text-ink-500">
                    {r?.bars_used ? (
                      `${r.bars_used} sesiones · ${r.data_source} · cierre ${r.last_close}`
                    ) : r?.error ? (
                      <span className="text-danger">sin datos</span>
                    ) : (
                      <span className="text-ink-300">—</span>
                    )}
                  </td>
                  <td className="max-w-[380px] px-3 py-2.5 text-ink-700">
                    {r ? (
                      <>
                        <p className="line-clamp-3 leading-5" title={r.rationale}>
                          {r.rationale}
                        </p>
                        {r.error && <p className="mt-1 text-[11.5px] text-danger">{r.error}</p>}
                        {(() => {
                          const ev = findDecisionEvent(symbol);
                          return ev ? (
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                onInspect(ev);
                              }}
                              className="mt-1 text-[11.5px] font-medium text-accent hover:underline"
                            >
                              ver mensaje de decisión →
                            </button>
                          ) : null;
                        })()}
                      </>
                    ) : (
                      <span className="text-ink-300">—</span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
