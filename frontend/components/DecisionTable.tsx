"use client";

import { computeNodeStats } from "@/lib/trace";
import { AGENT_LABELS, DECISION_STYLES, type AgentName, type RunEvent, type SymbolResult } from "@/lib/types";

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
      <div className="h-1.5 w-16 overflow-hidden rounded bg-ink-700">
        <div className="h-full bg-sky-400" style={{ width: `${pct}%` }} />
      </div>
      <span className="font-mono text-[11px] text-slate-400">{pct}%</span>
    </div>
  );
}

function currentStage(events: RunEvent[], symbol: string): string {
  const stats = computeNodeStats(events, symbol);
  const working = (Object.keys(stats) as AgentName[]).filter((a) => stats[a].status === "working" && a !== "orchestrator");
  if (working.length) return `en curso: ${working.map((a) => AGENT_LABELS[a]).join(", ")}`;
  return events.some((e) => e.symbol === symbol) ? "en cola…" : "pendiente";
}

export default function DecisionTable({ symbols, results, events, selectedSymbol, onSelectSymbol, onInspect }: Props) {
  const findDecisionEvent = (symbol: string) =>
    [...events].reverse().find((e) => e.symbol === symbol && e.type === "message_sent" && e.message?.type === "decision");

  return (
    <div className="panel">
      <div className="panel-title">
        <span>Decisiones (señales experimentales)</span>
        <button
          onClick={() => onSelectSymbol("all")}
          className={`rounded px-1.5 py-0.5 text-[10px] normal-case tracking-normal ${selectedSymbol === "all" ? "bg-ink-700 text-white" : "text-slate-400 hover:text-white"}`}
        >
          ver todos
        </button>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs">
          <thead className="text-[10px] uppercase tracking-wider text-slate-500">
            <tr className="border-b border-ink-700">
              <th className="px-3 py-2">Símbolo</th>
              <th className="px-3 py-2">Decisión</th>
              <th className="px-3 py-2">Confianza</th>
              <th className="px-3 py-2">Técnico</th>
              <th className="px-3 py-2">Riesgo</th>
              <th className="px-3 py-2">Escéptico</th>
              <th className="px-3 py-2">Datos</th>
              <th className="px-3 py-2">Justificación</th>
            </tr>
          </thead>
          <tbody>
            {symbols.length === 0 && (
              <tr>
                <td colSpan={8} className="px-3 py-4 text-slate-500">
                  Sin ejecución activa.
                </td>
              </tr>
            )}
            {symbols.map((symbol) => {
              const r = results[symbol];
              const tech = r?.opinions.find((o) => o.agent === "technical");
              const risk = r?.opinions.find((o) => o.agent === "risk");
              const skeptic = r?.opinions.find((o) => o.agent === "skeptic");
              const selected = selectedSymbol === symbol;
              return (
                <tr
                  key={symbol}
                  onClick={() => onSelectSymbol(selected ? "all" : symbol)}
                  className={`cursor-pointer border-b border-ink-800 align-top hover:bg-ink-800/60 ${selected ? "bg-ink-800/80" : ""}`}
                >
                  <td className="px-3 py-2 font-mono font-semibold text-slate-100">{symbol}</td>
                  <td className="px-3 py-2">
                    {r ? (
                      <span className={`chip ${DECISION_STYLES[r.decision]}`}>{r.decision}</span>
                    ) : (
                      <span className="text-slate-500">{currentStage(events, symbol)}</span>
                    )}
                  </td>
                  <td className="px-3 py-2">{r ? <Confidence value={r.confidence} /> : "—"}</td>
                  <td className="px-3 py-2 font-mono">{tech?.stance ?? "—"}</td>
                  <td className="px-3 py-2 font-mono">{risk?.risk_level ?? "—"}</td>
                  <td className="px-3 py-2">
                    {skeptic ? (
                      skeptic.agrees ? (
                        <span className="text-emerald-300">de acuerdo</span>
                      ) : (
                        <span className="text-pink-300">discrepa{r && r.disagreements ? ` (${r.disagreements})` : ""}</span>
                      )
                    ) : (
                      "—"
                    )}
                  </td>
                  <td className="px-3 py-2 font-mono text-slate-400">
                    {r?.bars_used ? `${r.bars_used} sesiones · ${r.data_source} · cierre ${r.last_close}` : r?.error ? <span className="text-rose-300">sin datos</span> : "—"}
                  </td>
                  <td className="max-w-[360px] px-3 py-2 text-slate-300">
                    {r ? (
                      <>
                        <p className="line-clamp-3" title={r.rationale}>
                          {r.rationale}
                        </p>
                        {r.error && <p className="mt-1 text-[11px] text-rose-300">{r.error}</p>}
                        {(() => {
                          const ev = findDecisionEvent(symbol);
                          return ev ? (
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                onInspect(ev);
                              }}
                              className="mt-1 text-[11px] text-sky-300 hover:underline"
                            >
                              ver mensaje de decisión →
                            </button>
                          ) : null;
                        })()}
                      </>
                    ) : (
                      "—"
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
