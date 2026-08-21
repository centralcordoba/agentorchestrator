"use client";

import { AGENT_COLORS, AGENT_LABELS, type AgentCost, type AgentName, type CostSummary } from "@/lib/types";

interface Props {
  costs: CostSummary;
  running: boolean;
  providerName?: string;
}

const SOURCE_LABEL: Record<string, string> = {
  provider: "coste informado por el proveedor",
  estimated: "coste estimado con precios públicos",
  mock: "proveedor simulado: sin coste",
  unknown: "precio desconocido",
};

function fmtTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(2)}M`;
  if (n >= 10_000) return `${(n / 1000).toFixed(1)}k`;
  return n.toLocaleString("es-ES");
}

function fmtUsd(v: number | null, known: number, calls: number): string {
  if (v === null) return "—";
  const txt = v < 0.01 && v > 0 ? `$${v.toFixed(4)}` : `$${v.toFixed(v >= 1 ? 2 : 3)}`;
  return known < calls ? `${txt}*` : txt;
}

function dominantSource(c: AgentCost): string {
  const entries = Object.entries(c.sources);
  if (!entries.length) return "unknown";
  return entries.sort((a, b) => b[1] - a[1])[0][0];
}

export default function CostPanel({ costs, running, providerName }: Props) {
  const agents = (Object.keys(costs.per_agent) as AgentName[]).sort((a, b) => (costs.per_agent[b].cost_usd ?? 0) - (costs.per_agent[a].cost_usd ?? 0) || costs.per_agent[b].input_tokens - costs.per_agent[a].input_tokens);
  const total = costs.total;
  const source = dominantSource(total);
  const models = Object.keys(total.models).filter((m) => m !== "?");
  const maxTokens = Math.max(1, ...agents.map((a) => costs.per_agent[a].input_tokens + costs.per_agent[a].output_tokens));

  return (
    <div className="panel p-4">
      <div className="mb-2 flex items-baseline justify-between">
        <span className="text-[11px] font-semibold uppercase tracking-[0.08em] text-ink-500">Consumo LLM</span>
        {running && total.calls > 0 && <span className="font-mono text-[10.5px] text-ink-400">actualizando…</span>}
      </div>

      {total.calls === 0 ? (
        <p className="text-[12px] leading-5 text-ink-400">Sin llamadas al modelo todavía.</p>
      ) : (
        <>
          <div className="mb-3 grid grid-cols-3 gap-2">
            <div className="rounded-lg bg-sunken px-2.5 py-2">
              <div className="text-[10px] uppercase tracking-wider text-ink-400">llamadas</div>
              <div className="font-mono text-[15px] font-semibold text-ink-900">{total.calls}</div>
            </div>
            <div className="rounded-lg bg-sunken px-2.5 py-2">
              <div className="text-[10px] uppercase tracking-wider text-ink-400">tokens</div>
              <div className="font-mono text-[15px] font-semibold text-ink-900">{fmtTokens(total.input_tokens + total.output_tokens)}</div>
              <div className="font-mono text-[10px] text-ink-400">
                ↑{fmtTokens(total.input_tokens)} ↓{fmtTokens(total.output_tokens)}
              </div>
            </div>
            <div className="rounded-lg bg-accent-soft px-2.5 py-2">
              <div className="text-[10px] uppercase tracking-wider text-accent/80">coste</div>
              <div className="font-mono text-[15px] font-semibold text-accent">{fmtUsd(total.cost_usd, total.cost_known_calls, total.calls)}</div>
            </div>
          </div>

          <table className="w-full text-[11.5px]">
            <thead>
              <tr className="text-[10px] uppercase tracking-wider text-ink-400">
                <th className="pb-1 text-left font-semibold">agente</th>
                <th className="pb-1 text-right font-semibold">llam.</th>
                <th className="pb-1 text-right font-semibold">tokens</th>
                <th className="pb-1 text-right font-semibold">USD</th>
              </tr>
            </thead>
            <tbody>
              {agents.map((a) => {
                const c = costs.per_agent[a];
                const tokens = c.input_tokens + c.output_tokens;
                const color = AGENT_COLORS[a] ?? "#8C887F";
                return (
                  <tr key={a} className="border-t border-line/70">
                    <td className="py-1.5 pr-2">
                      <div className="flex items-center gap-1.5">
                        <span className="inline-block h-2 w-2 shrink-0 rounded-full" style={{ background: color }} />
                        <span className="truncate text-ink-700">{AGENT_LABELS[a] ?? a}</span>
                      </div>
                      <div className="mt-0.5 h-1 w-full overflow-hidden rounded-full bg-line">
                        <div className="h-full rounded-full" style={{ width: `${Math.round((tokens / maxTokens) * 100)}%`, background: color }} />
                      </div>
                    </td>
                    <td className="py-1.5 text-right font-mono text-ink-500">{c.calls}</td>
                    <td className="py-1.5 text-right font-mono text-ink-700" title={`entrada ${c.input_tokens.toLocaleString("es-ES")} · salida ${c.output_tokens.toLocaleString("es-ES")}`}>
                      {fmtTokens(tokens)}
                    </td>
                    <td className="py-1.5 text-right font-mono font-medium text-ink-900">{fmtUsd(c.cost_usd, c.cost_known_calls, c.calls)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>

          <p className="mt-2.5 border-t border-line pt-2 text-[10.5px] leading-4 text-ink-400">
            {SOURCE_LABEL[source] ?? source}
            {models.length > 0 && <> · {models.join(", ")}</>}
            {providerName && !models.length && <> · {providerName}</>}
            {total.cost_known_calls < total.calls && total.cost_usd !== null && (
              <> · * {total.calls - total.cost_known_calls} llamada(s) sin precio conocido, no incluidas</>
            )}
          </p>
        </>
      )}
    </div>
  );
}
