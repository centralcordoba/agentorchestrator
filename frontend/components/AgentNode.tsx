"use client";

import { AGENT_COLORS, AGENT_LABELS, type AgentName } from "@/lib/types";
import type { NodeStats } from "@/lib/trace";

export const NODE_W = 156;
export const NODE_H = 74;

interface Props {
  name: AgentName;
  x: number;
  y: number;
  stats: NodeStats;
  selected: boolean;
  onClick: () => void;
}

const STATUS_LABEL: Record<NodeStats["status"], string> = {
  idle: "inactivo",
  working: "trabajando",
  done: "completado",
  error: "error",
};

const STATUS_COLOR: Record<NodeStats["status"], string> = {
  idle: "#475569",
  working: "#38bdf8",
  done: "#34d399",
  error: "#f43f5e",
};

export default function AgentNode({ name, x, y, stats, selected, onClick }: Props) {
  const color = AGENT_COLORS[name];
  const left = x - NODE_W / 2;
  const top = y - NODE_H / 2;
  const working = stats.status === "working";
  const active = working && stats.activeSymbols.length > 0 ? stats.activeSymbols.slice(0, 3).join(",") : "";

  return (
    <g
      transform={`translate(${left} ${top})`}
      onClick={onClick}
      className={`cursor-pointer ${working ? "node-working" : ""}`}
      role="button"
      aria-label={`${AGENT_LABELS[name]}: ${STATUS_LABEL[stats.status]}`}
    >
      <rect
        width={NODE_W}
        height={NODE_H}
        rx={10}
        fill="#111827"
        stroke={selected ? "#ffffff" : color}
        strokeWidth={selected ? 2 : 1.5}
        opacity={stats.status === "idle" ? 0.75 : 1}
      />
      <rect width={4} height={NODE_H} rx={2} fill={color} />

      {/* fila 1: nombre · fila 2: id · fila 3: estado · fila 4: contadores */}
      <text x={14} y={18} fill="#e5e7eb" fontSize={12} fontWeight={600}>
        {AGENT_LABELS[name]}
      </text>
      <text x={14} y={32} fill="#94a3b8" fontSize={10} fontFamily="ui-monospace, monospace">
        {name}
      </text>
      <g transform="translate(14 48)">
        <circle r={3.5} cx={3.5} cy={-3} fill={STATUS_COLOR[stats.status]}>
          {working && <animate attributeName="opacity" values="1;0.3;1" dur="1s" repeatCount="indefinite" />}
        </circle>
        <text x={12} fill={STATUS_COLOR[stats.status]} fontSize={9.5}>
          {STATUS_LABEL[stats.status]}
          {active ? ` · ${active}` : ""}
        </text>
      </g>
      <g transform={`translate(14 ${NODE_H - 9})`} fontSize={9} fontFamily="ui-monospace, monospace">
        <text fill="#94a3b8">
          ↑{stats.sent} ↓{stats.received}
        </text>
        {stats.llmCalls > 0 && (
          <text x={52} fill="#c4b5fd">
            LLM×{stats.llmCalls}
          </text>
        )}
        {stats.errors > 0 && (
          <text x={stats.llmCalls > 0 ? 96 : 52} fill="#fb7185">
            err×{stats.errors}
          </text>
        )}
      </g>
    </g>
  );
}
