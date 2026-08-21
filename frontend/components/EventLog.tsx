"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { EVENT_GROUPS, describeEvent, formatTime } from "@/lib/trace";
import { AGENT_COLORS, AGENT_LABELS, type AgentName, type RunEvent } from "@/lib/types";

interface Props {
  events: RunEvent[];
  symbol: string | "all";
  agent: AgentName | null;
  selectedSeq: number | null;
  onSelect: (e: RunEvent) => void;
}

const TYPE_STYLE: Partial<Record<RunEvent["type"], string>> = {
  message_sent: "text-info",
  agent_error: "text-danger",
  validation_warning: "text-warn",
  disagreement: "text-rose",
  decision_made: "text-accent",
  llm_call_started: "text-violet",
  llm_call_completed: "text-violet",
  tool_called: "text-violet font-medium",
  guardrail_applied: "text-warn font-medium",
  run_started: "text-ink-900 font-medium",
  run_completed: "text-ink-900 font-medium",
};

export default function EventLog({ events, symbol, agent, selectedSeq, onSelect }: Props) {
  const [groups, setGroups] = useState<Record<string, boolean>>({ mensajes: true, agentes: true, llm: true, sistema: true });
  const [autoScroll, setAutoScroll] = useState(true);
  const listRef = useRef<HTMLDivElement>(null);

  const allowedTypes = useMemo(() => {
    const set = new Set<RunEvent["type"]>();
    Object.entries(groups).forEach(([g, on]) => on && EVENT_GROUPS[g].forEach((t) => set.add(t)));
    return set;
  }, [groups]);

  const visible = useMemo(
    () =>
      events.filter((e) => {
        if (!allowedTypes.has(e.type)) return false;
        if (symbol !== "all" && e.symbol && e.symbol !== symbol) return false;
        if (agent) {
          const involved = e.agent === agent || e.message?.sender === agent || e.message?.recipient === agent;
          if (!involved) return false;
        }
        return true;
      }),
    [events, allowedTypes, symbol, agent],
  );

  useEffect(() => {
    if (autoScroll && listRef.current) listRef.current.scrollTop = listRef.current.scrollHeight;
  }, [visible.length, autoScroll]);

  return (
    <div className="panel flex h-full min-h-0 flex-col overflow-hidden">
      <div className="panel-title">
        <span>Traza de eventos</span>
        <div className="flex items-center gap-1 normal-case tracking-normal">
          {Object.keys(EVENT_GROUPS).map((g) => (
            <button
              key={g}
              onClick={() => setGroups((s) => ({ ...s, [g]: !s[g] }))}
              className={`rounded-md px-1.5 py-0.5 text-[10.5px] transition ${
                groups[g] ? "bg-ink-900 text-white" : "text-ink-400 hover:bg-sunken hover:text-ink-700"
              }`}
            >
              {g}
            </button>
          ))}
          <label className="ml-2 flex cursor-pointer items-center gap-1 text-[10.5px] text-ink-500">
            <input type="checkbox" className="accent-[#C2562E]" checked={autoScroll} onChange={(e) => setAutoScroll(e.target.checked)} />
            auto-scroll
          </label>
          <span className="ml-1 font-mono text-[10.5px] text-ink-400">{visible.length}</span>
        </div>
      </div>
      <div ref={listRef} className="min-h-0 flex-1 overflow-y-auto font-mono text-[11.5px] leading-5">
        {visible.length === 0 && (
          <div className="flex h-full flex-col items-center justify-center gap-1 p-6 text-center">
            <p className="text-[13px] text-ink-700">Sin eventos todavía</p>
            <p className="font-sans text-[12px] text-ink-400">Inicia una ejecución para ver la traza en tiempo real.</p>
          </div>
        )}
        {visible.map((e) => {
          const agentName = e.agent ?? e.message?.sender ?? null;
          const color = agentName ? AGENT_COLORS[agentName] : "#8C887F";
          const selected = e.seq === selectedSeq;
          return (
            <button
              key={e.seq}
              onClick={() => onSelect(e)}
              className={`flex w-full items-start gap-2 border-b border-line/70 px-3 py-1 text-left transition hover:bg-sunken ${
                selected ? "bg-accent-soft/70 shadow-[inset_3px_0_0_#C2562E]" : ""
              }`}
            >
              <span className="w-10 shrink-0 text-ink-300">#{e.seq}</span>
              <span className="w-[88px] shrink-0 text-ink-400">{formatTime(e.timestamp)}</span>
              <span className="w-14 shrink-0 truncate font-semibold text-ink-700">{e.symbol ?? "—"}</span>
              <span className="w-[112px] shrink-0 truncate font-medium" style={{ color }} title={agentName ?? ""}>
                {agentName ? AGENT_LABELS[agentName] : "sistema"}
              </span>
              <span className={`min-w-0 flex-1 truncate ${TYPE_STYLE[e.type] ?? "text-ink-700"}`} title={describeEvent(e)}>
                <span className="text-ink-400">{e.type}</span> · {describeEvent(e)}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
