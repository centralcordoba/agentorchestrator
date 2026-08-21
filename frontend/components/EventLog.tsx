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
  message_sent: "text-sky-300",
  agent_error: "text-rose-300",
  validation_warning: "text-amber-300",
  disagreement: "text-pink-300",
  decision_made: "text-orange-300",
  llm_call_started: "text-violet-300",
  llm_call_completed: "text-violet-300",
  run_started: "text-slate-200",
  run_completed: "text-slate-200",
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
          const involved =
            e.agent === agent || e.message?.sender === agent || e.message?.recipient === agent;
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
    <div className="panel flex h-full min-h-0 flex-col">
      <div className="panel-title">
        <span>Traza de eventos</span>
        <div className="flex items-center gap-2 normal-case tracking-normal">
          {Object.keys(EVENT_GROUPS).map((g) => (
            <button
              key={g}
              onClick={() => setGroups((s) => ({ ...s, [g]: !s[g] }))}
              className={`rounded px-1.5 py-0.5 text-[10px] ${groups[g] ? "bg-ink-700 text-slate-200" : "text-slate-500"}`}
            >
              {g}
            </button>
          ))}
          <label className="ml-2 flex items-center gap-1 text-[10px] text-slate-400">
            <input type="checkbox" checked={autoScroll} onChange={(e) => setAutoScroll(e.target.checked)} />
            auto-scroll
          </label>
          <span className="font-mono text-[10px] text-slate-500">{visible.length}</span>
        </div>
      </div>
      <div ref={listRef} className="min-h-0 flex-1 overflow-y-auto font-mono text-[11.5px] leading-5">
        {visible.length === 0 && <p className="p-4 text-slate-500">Sin eventos. Inicia una ejecución para ver la traza.</p>}
        {visible.map((e) => {
          const agentName = e.agent ?? e.message?.sender ?? null;
          const color = agentName ? AGENT_COLORS[agentName] : "#64748b";
          const selected = e.seq === selectedSeq;
          return (
            <button
              key={e.seq}
              onClick={() => onSelect(e)}
              className={`flex w-full items-start gap-2 border-b border-ink-800 px-3 py-1 text-left hover:bg-ink-800/70 ${selected ? "bg-ink-700/70" : ""}`}
            >
              <span className="w-10 shrink-0 text-slate-600">#{e.seq}</span>
              <span className="w-[88px] shrink-0 text-slate-500">{formatTime(e.timestamp)}</span>
              <span className="w-14 shrink-0 truncate text-slate-300">{e.symbol ?? "—"}</span>
              <span className="w-[112px] shrink-0 truncate" style={{ color }} title={agentName ?? ""}>
                {agentName ? AGENT_LABELS[agentName] : "sistema"}
              </span>
              <span className={`min-w-0 flex-1 truncate ${TYPE_STYLE[e.type] ?? "text-slate-300"}`} title={describeEvent(e)}>
                <span className="text-slate-500">{e.type}</span> · {describeEvent(e)}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
