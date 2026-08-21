"use client";

import { AGENT_COLORS, AGENT_LABELS, AGENT_SOFT_COLORS, type AgentName } from "@/lib/types";
import type { NodeStats } from "@/lib/trace";

export const NODE_W = 160;
export const NODE_H = 76;

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
  idle: "#B3AFA6",
  working: "#2F6F8F",
  done: "#2E7D5B",
  error: "#B3362B",
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
        rx={12}
        fill="#FFFFFF"
        stroke={selected ? "#1F1E1D" : working ? color : "#D5D1C5"}
        strokeWidth={selected ? 2 : working ? 1.75 : 1.25}
        opacity={stats.status === "idle" ? 0.85 : 1}
      />
      {/* franja de color del agente */}
      <path d={`M 0 12 Q 0 0 12 0 L 12 ${NODE_H} Q 0 ${NODE_H} 0 ${NODE_H - 12} Z`} fill={AGENT_SOFT_COLORS[name]} />
      <rect x={0} y={12} width={3} height={NODE_H - 24} rx={1.5} fill={color} />

      {/* fila 1: nombre · fila 2: id · fila 3: estado · fila 4: contadores */}
      <text x={22} y={19} fill="#1F1E1D" fontSize={12.5} fontWeight={600}>
        {AGENT_LABELS[name]}
      </text>
      <text x={22} y={33} fill="#8C887F" fontSize={10} fontFamily="ui-monospace, monospace">
        {name}
      </text>
      <g transform="translate(22 49)">
        <circle r={3.5} cx={3.5} cy={-3} fill={STATUS_COLOR[stats.status]}>
          {working && <animate attributeName="opacity" values="1;0.3;1" dur="1s" repeatCount="indefinite" />}
        </circle>
        <text x={12} fill={STATUS_COLOR[stats.status]} fontSize={10} fontWeight={500}>
          {STATUS_LABEL[stats.status]}
          {active ? ` · ${active}` : ""}
        </text>
      </g>
      <g transform={`translate(22 ${NODE_H - 10})`} fontSize={9.5} fontFamily="ui-monospace, monospace">
        <text fill="#8C887F">
          ↑{stats.sent} ↓{stats.received}
        </text>
        {stats.llmCalls > 0 && (
          <text x={52} fill="#5B4B8A">
            LLM×{stats.llmCalls}
          </text>
        )}
        {stats.errors > 0 && (
          <text x={stats.llmCalls > 0 ? 98 : 52} fill="#B3362B">
            err×{stats.errors}
          </text>
        )}
      </g>
    </g>
  );
}
