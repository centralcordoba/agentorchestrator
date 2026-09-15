"use client";

import { useState } from "react";
import { AGENTS } from "@/lib/rq/agents";
import type { AgentId, TraceEvent, TraceEventType } from "@/lib/rq/types";
import { fmtTokens, fmtUsd } from "./ui";

const TYPE_LABEL: Record<TraceEventType, string> = {
  run_started: "inicio",
  agent_started: "arranca",
  llm_call: "LLM",
  tool_called: "herramienta",
  message_sent: "mensaje",
  guardrail_applied: "guardarraíl",
  agent_completed: "termina",
  agent_skipped: "omitido",
  run_completed: "fin",
};

const TYPE_CLASS: Record<TraceEventType, string> = {
  run_started: "chip-neutral",
  agent_started: "border-info/30 bg-info-soft text-info",
  llm_call: "border-violet/30 bg-violet-soft text-violet",
  tool_called: "chip-neutral",
  message_sent: "border-warn/30 bg-warn-soft text-warn",
  guardrail_applied: "border-accent/30 bg-accent-soft text-accent",
  agent_completed: "border-ok/30 bg-ok-soft text-ok",
  agent_skipped: "chip-neutral text-ink-400",
  run_completed: "border-ok/30 bg-ok-soft text-ok",
};

function clock(ms: number) {
  const s = Math.floor(ms / 1000);
  return `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
}

export default function EventRow({ event: e, perspective }: { event: TraceEvent; perspective?: AgentId }) {
  const [open, setOpen] = useState(false);
  const hasData = Boolean(e.data || e.detail);
  const direction =
    e.type === "message_sent" && e.to
      ? perspective === e.to
        ? `← de ${AGENTS[e.agent].label}`
        : `→ ${AGENTS[e.to].label}`
      : null;

  return (
    <li className="px-4 py-2">
      <button className="flex w-full items-start gap-2 text-left" onClick={() => hasData && setOpen((v) => !v)} aria-expanded={hasData ? open : undefined}>
        <span className="w-10 shrink-0 pt-0.5 font-mono text-[10.5px] text-ink-400">{clock(e.offsetMs)}</span>
        <span className={`chip shrink-0 ${TYPE_CLASS[e.type]}`}>{TYPE_LABEL[e.type]}</span>
        <span className="min-w-0 flex-1">
          <span className="block text-[12.5px] leading-5 text-ink-900">
            {!perspective && <span className="font-semibold" style={{ color: AGENTS[e.agent].color }}>{AGENTS[e.agent].label} </span>}
            {direction && <span className="text-ink-500">{direction} · </span>}
            <span className={e.type === "tool_called" || e.type === "message_sent" ? "font-mono text-[12px]" : ""}>{e.title}</span>
            {e.step ? <span className="text-ink-400"> · paso {e.step}</span> : null}
          </span>
          {e.detail && !open && <span className="block truncate text-[12px] text-ink-500">{e.detail}</span>}
          {e.type === "llm_call" && (
            <span className="block font-mono text-[10.5px] text-ink-400">
              {fmtTokens(e.tokensIn ?? 0)} in · {fmtTokens(e.tokensOut ?? 0)} out · {fmtUsd(e.costUsd ?? 0)}
            </span>
          )}
        </span>
        {hasData && <span className="pt-0.5 text-[10px] text-ink-400">{open ? "▾" : "▸"}</span>}
      </button>
      {open && (
        <div className="ml-12 mt-1 space-y-1">
          {e.detail && <p className="text-[12px] leading-5 text-ink-700">{e.detail}</p>}
          {e.data && (
            <pre className="overflow-x-auto rounded-md bg-sunken px-2 py-1.5 font-mono text-[11px] leading-4 text-ink-700">{JSON.stringify(e.data, null, 2)}</pre>
          )}
        </div>
      )}
    </li>
  );
}
