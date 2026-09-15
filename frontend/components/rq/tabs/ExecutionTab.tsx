"use client";

import { AGENTS, AGENT_ORDER, modelLabel } from "@/lib/rq/agents";
import type { RunView } from "@/lib/rq/derive";
import { USERS } from "@/lib/rq/mockData";
import { SPEED_LABELS, agentStats, runDurationMs } from "@/lib/rq/simulator";
import { useRq } from "@/lib/rq/store";
import type { AgentId, Requirement } from "@/lib/rq/types";
import EventRow from "../EventRow";
import FlowGraph from "../FlowGraph";
import { EmptyState, StatusDot, VerdictBadge, fmtDate, fmtDuration, fmtTokens, fmtUsd } from "../ui";

interface Props {
  req: Requirement;
  view: RunView | null;
  now: number;
  selectedAgent: AgentId | null;
  onSelectAgent: (a: AgentId) => void;
  onSelectRun: (runId: string) => void;
  onGoToPlan: () => void;
}

export default function ExecutionTab({ req, view, now, selectedAgent, onSelectAgent, onSelectRun, onGoToPlan }: Props) {
  const { cancelRun } = useRq();

  if (!view) {
    return (
      <EmptyState title="Todavía no hay ejecuciones">
        <p>Revisa el plan de agentes y pulsa «Ejecutar revisión». Aquí verás el flujo en vivo.</p>
        <button className="btn-primary mt-3" onClick={onGoToPlan}>
          Ir al plan
        </button>
      </EmptyState>
    );
  }

  const { run, events, state } = view;
  const total = runDurationMs(req, run);
  const elapsed = Math.min(total, (run.cancelledAt ?? now) - run.startedAt);
  const pct = total ? Math.round((elapsed / total) * 100) : 100;
  const stats = AGENT_ORDER.map((id) => ({ id, s: agentStats(events, id, run.enabledAgents.includes(id)) }));
  const cost = stats.reduce((acc, x) => acc + x.s.costUsd, 0);
  const tokens = stats.reduce((acc, x) => acc + x.s.tokensIn + x.s.tokensOut, 0);
  const maxCost = Math.max(...stats.map((x) => x.s.costUsd), 1e-9);
  const starter = USERS.find((u) => u.id === run.startedBy);

  return (
    <div className="space-y-4">
      <div className="panel flex flex-wrap items-center gap-x-5 gap-y-3 px-4 py-3">
        <label className="flex items-center gap-2 text-[12px] text-ink-500">
          Ejecución
          <select value={run.id} onChange={(e) => onSelectRun(e.target.value)} className="rounded-md border border-line bg-surface px-2 py-1 font-mono text-[12px] text-ink-900 outline-none focus:border-accent">
            {[...req.runs].reverse().map((r, i) => (
              <option key={r.id} value={r.id}>
                #{req.runs.length - i} · {fmtDate(r.startedAt)}
              </option>
            ))}
          </select>
        </label>
        <span className="text-[12px] text-ink-500">
          por <span className="text-ink-900">{starter?.name ?? run.startedBy}</span> · ritmo {SPEED_LABELS[run.speed].toLowerCase()}
        </span>
        <div className="flex min-w-[200px] flex-1 items-center gap-2">
          <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-sunken" role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100}>
            <div className={`h-full rounded-full transition-all ${state === "cancelado" ? "bg-ink-300" : state === "completado" ? "bg-ok" : "bg-info"}`} style={{ width: `${pct}%` }} />
          </div>
          <span className="font-mono text-[11px] text-ink-500">{fmtDuration(elapsed)}</span>
        </div>
        <span className="font-mono text-[12px] text-ink-700">
          {fmtTokens(tokens)} tokens · {fmtUsd(cost)}
        </span>
        {state === "en_curso" && (
          <span className="chip border-info/30 bg-info-soft text-info">
            <StatusDot status="trabajando" /> en curso
          </span>
        )}
        {state === "cancelado" && <span className="chip chip-neutral">cancelada</span>}
        {view.verdict && <VerdictBadge verdict={view.verdict} />}
        {state === "en_curso" && (
          <button className="btn-ghost" onClick={() => cancelRun(req.id, run.id)}>
            cancelar
          </button>
        )}
      </div>

      <div className="panel overflow-hidden">
        <FlowGraph run={run} events={events} now={now} selected={selectedAgent} onSelect={onSelectAgent} />
      </div>

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1.5fr)_minmax(0,1fr)]">
        <section className="panel flex max-h-[520px] flex-col">
          <div className="panel-title">
            <span>Traza de la ejecución</span>
            <span className="font-mono normal-case tracking-normal text-ink-400">{events.length} eventos</span>
          </div>
          <ol className="flex-1 divide-y divide-line overflow-y-auto">
            {[...events].reverse().map((e) => (
              <EventRow key={e.seq} event={e} />
            ))}
          </ol>
        </section>

        <section className="panel">
          <div className="panel-title">
            <span>Consumo por agente</span>
            <span className="font-mono normal-case tracking-normal text-ink-400">{fmtUsd(cost)}</span>
          </div>
          <ul className="divide-y divide-line">
            {stats.map(({ id, s }) => (
              <li key={id}>
                <button onClick={() => onSelectAgent(id)} className="w-full px-4 py-2 text-left transition hover:bg-sunken/60" title={`${AGENTS[id].label}: ${s.llmCalls} llamadas, ${fmtTokens(s.tokensIn)} entrada, ${fmtTokens(s.tokensOut)} salida, ${fmtUsd(s.costUsd)}`}>
                  <div className="flex items-center gap-2 text-[12.5px]">
                    <StatusDot status={s.status} />
                    <span className="font-medium text-ink-900">{AGENTS[id].label}</span>
                    <span className="truncate font-mono text-[10.5px] text-ink-400">{modelLabel(run.profiles[id].provider, run.profiles[id].model)}</span>
                    <span className="ml-auto font-mono text-[11.5px] text-ink-700">{s.status === "omitido" ? "—" : fmtUsd(s.costUsd)}</span>
                  </div>
                  <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-sunken">
                    <div className="h-full rounded-full bg-accent transition-all" style={{ width: `${(s.costUsd / maxCost) * 100}%` }} />
                  </div>
                </button>
              </li>
            ))}
          </ul>
        </section>
      </div>
    </div>
  );
}
