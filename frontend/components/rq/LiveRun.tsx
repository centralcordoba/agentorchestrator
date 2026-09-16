"use client";

import { useMemo } from "react";
import { AGENTS } from "@/lib/rq/agents";
import type { AgentId } from "@/lib/rq/types";
import type { TraceEvent } from "@/lib/api/types";
import { agentStatuses, type LiveAgentStatus, type RunStream } from "@/lib/api/useRunStream";
import { fmtTokens, fmtUsd } from "./ui";

const STATUS_CLASS: Record<LiveAgentStatus, string> = {
  pendiente: "border-line bg-sunken text-ink-400",
  trabajando: "border-violet/30 bg-violet-soft text-violet",
  completado: "border-ok/30 bg-ok-soft text-ok",
  omitido: "border-line bg-sunken text-ink-400",
  fallido: "border-danger/30 bg-danger-soft text-danger",
};

const STATUS_ICON: Record<LiveAgentStatus, string> = {
  pendiente: "·",
  trabajando: "◐",
  completado: "✓",
  omitido: "—",
  fallido: "✕",
};

const STATUS_LABEL: Record<LiveAgentStatus, string> = {
  pendiente: "pendiente",
  trabajando: "trabajando",
  completado: "completado",
  omitido: "omitido",
  fallido: "sin resultado",
};

const EVENT_LABEL: Record<string, string> = {
  run_started: "inicio",
  agent_started: "arranca",
  llm_call: "LLM",
  tool_called: "herramienta",
  message_sent: "mensaje",
  guardrail_applied: "guardarraíl",
  agent_completed: "termina",
  agent_skipped: "omitido",
  agent_failed: "sin resultado",
  agent_degraded: "menos contexto",
  phi_redacted: "PHI redactada",
  run_completed: "fin",
  run_cancelled: "cancelada",
};

const EVENT_CLASS: Record<string, string> = {
  run_started: "chip-neutral",
  agent_started: "border-info/30 bg-info-soft text-info",
  llm_call: "border-violet/30 bg-violet-soft text-violet",
  tool_called: "chip-neutral",
  message_sent: "border-warn/30 bg-warn-soft text-warn",
  guardrail_applied: "border-accent/30 bg-accent-soft text-accent",
  agent_completed: "border-ok/30 bg-ok-soft text-ok",
  agent_skipped: "chip-neutral text-ink-400",
  agent_failed: "border-danger/30 bg-danger-soft text-danger",
  agent_degraded: "border-warn/30 bg-warn-soft text-warn",
  phi_redacted: "border-teal/30 bg-teal-soft text-teal",
  run_completed: "border-ok/30 bg-ok-soft text-ok",
  run_cancelled: "border-line bg-sunken text-ink-500",
};

/** Aviso del estado del canal. Solo aparece cuando hay algo que decir. */
export function ConnectionBadge({ stream }: { stream: RunStream }) {
  if (stream.status === "en_vivo") {
    return (
      <span className="chip border-ok/30 bg-ok-soft text-ok" aria-live="polite">
        ● En vivo
      </span>
    );
  }
  if (stream.status === "terminada") {
    return <span className="chip chip-neutral">Ejecución {stream.finalStatus}</span>;
  }
  if (stream.status === "reconectando") {
    return (
      <span className="chip border-warn/30 bg-warn-soft text-warn" role="status">
        Reconectando…
      </span>
    );
  }
  if (stream.status === "error") {
    return (
      <span className="chip border-danger/30 bg-danger-soft text-danger" role="alert">
        Sin conexión
      </span>
    );
  }
  return <span className="chip chip-neutral">Conectando…</span>;
}

function elapsed(events: TraceEvent[], event: TraceEvent): string {
  const first = events[0];
  if (!first) return "00:00";
  const ms = new Date(event.at).getTime() - new Date(first.at).getTime();
  const seconds = Math.max(0, Math.floor(ms / 1000));
  return `${String(Math.floor(seconds / 60)).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;
}

export function AgentBoard({ stream }: { stream: RunStream }) {
  const enabled = stream.run?.enabledAgents ?? [];
  const statuses = useMemo(() => agentStatuses(stream.events, enabled), [stream.events, enabled]);

  if (!enabled.length) return null;

  return (
    <ul className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
      {enabled.map((agent) => {
        const status = statuses[agent] ?? "pendiente";
        const definition = AGENTS[agent as AgentId];
        return (
          <li key={agent} className={`panel flex items-center gap-3 px-3 py-2 ${STATUS_CLASS[status]}`}>
            <span aria-hidden className="text-[16px] leading-none">
              {STATUS_ICON[status]}
            </span>
            <span className="min-w-0 flex-1">
              <span className="block truncate text-[13px] font-medium text-ink-900">
                {definition?.label ?? agent}
              </span>
              <span className="block text-[11.5px]">{STATUS_LABEL[status]}</span>
            </span>
          </li>
        );
      })}
    </ul>
  );
}

export function LiveTrace({ stream }: { stream: RunStream }) {
  if (!stream.events.length) {
    return (
      <p className="panel px-4 py-6 text-center text-[13px] text-ink-500">
        {stream.status === "conectando"
          ? "Conectando con la ejecución…"
          : "Todavía no hay eventos en esta ejecución."}
      </p>
    );
  }

  return (
    <ol className="panel divide-y divide-line">
      {stream.events.map((event) => (
        <li key={event.seq} className="flex items-start gap-3 px-4 py-2 text-[13px]">
          <span className="w-10 shrink-0 font-mono text-[11.5px] text-ink-400">
            {elapsed(stream.events, event)}
          </span>
          <span className={`chip shrink-0 ${EVENT_CLASS[event.type] ?? "chip-neutral"}`}>
            {EVENT_LABEL[event.type] ?? event.type}
          </span>
          <span className="min-w-0 flex-1">
            <span className="block text-ink-900">
              {event.agent ? `${AGENTS[event.agent as AgentId]?.label ?? event.agent}: ` : ""}
              {event.title}
            </span>
            {event.detail && (
              <span className="block text-[12px] leading-5 text-ink-500">{event.detail}</span>
            )}
          </span>
          {event.usage && (event.usage.tokensIn || event.usage.tokensOut) ? (
            <span className="shrink-0 text-right font-mono text-[11px] text-ink-400">
              <span className="block">
                {fmtTokens((event.usage.tokensIn ?? 0) + (event.usage.tokensOut ?? 0))} tok
              </span>
              <span className="block">{fmtUsd(event.usage.costUsd ?? 0)}</span>
            </span>
          ) : null}
        </li>
      ))}
    </ol>
  );
}
