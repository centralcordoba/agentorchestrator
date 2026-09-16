"use client";

import { AGENTS, AGENT_ORDER, modelLabel } from "@/lib/rq/agents";
import { agentStats, type AgentStats } from "@/lib/rq/simulator";
import type { AgentId, Run, TraceEvent } from "@/lib/rq/types";
import { fmtUsd } from "./ui";

const W = 1000;
const H = 532;
const NW = 156;
const NH = 74;

const POS: Record<AgentId, { x: number; y: number }> = {
  orchestrator: { x: 95, y: 266 },
  code: { x: 295, y: 266 },
  tests: { x: 515, y: 62 },
  kiuwan: { x: 515, y: 164 },
  sql: { x: 515, y: 266 },
  uiux: { x: 515, y: 368 },
  privacy: { x: 515, y: 470 },
  vtr: { x: 725, y: 266 },
  verdict: { x: 912, y: 266 },
  chat: { x: -1000, y: -1000 }, // no se dibuja: el asistente no participa en el flujo
};

const STRUCTURE: [AgentId, AgentId][] = [
  ["orchestrator", "code"],
  ["code", "tests"],
  ["code", "kiuwan"],
  ["code", "sql"],
  ["code", "uiux"],
  ["code", "privacy"],
  ["tests", "vtr"],
  ["kiuwan", "vtr"],
  ["sql", "vtr"],
  ["uiux", "vtr"],
  ["privacy", "vtr"],
  ["vtr", "verdict"],
];

const STATUS_COLOR: Record<AgentStats["status"], string> = {
  pendiente: "#8C887F",
  trabajando: "#2F6F8F",
  completado: "#2E7D5B",
  omitido: "#B3AFA6",
};
const STATUS_TEXT: Record<AgentStats["status"], string> = {
  pendiente: "en espera",
  trabajando: "trabajando",
  completado: "completado",
  omitido: "omitido",
};

function clip(text: string, max = 25): string {
  return text.length > max ? `${text.slice(0, max - 1)}…` : text;
}

function anchor(from: { x: number; y: number }, to: { x: number; y: number }) {
  const dx = to.x - from.x;
  const dy = to.y - from.y;
  const s = Math.min(NW / 2 / Math.max(Math.abs(dx), 1e-6), NH / 2 / Math.max(Math.abs(dy), 1e-6));
  return { x: from.x + dx * s, y: from.y + dy * s };
}

function curve(from: AgentId, to: AgentId, bend = 0) {
  const a = anchor(POS[from], POS[to]);
  const b = anchor(POS[to], POS[from]);
  const dx = b.x - a.x;
  const dy = b.y - a.y;
  const len = Math.hypot(dx, dy) || 1;
  const c = { x: (a.x + b.x) / 2 + (-dy / len) * bend, y: (a.y + b.y) / 2 + (dx / len) * bend };
  return { a, b, c };
}

function path(from: AgentId, to: AgentId, bend = 0): string {
  const { a, b, c } = curve(from, to, bend);
  return `M ${a.x} ${a.y} Q ${c.x} ${c.y} ${b.x} ${b.y}`;
}

/** Posición de un mensaje en vuelo (t de 0 a 1). Los "de vuelta" se curvan al otro lado para no pisarse. */
function messagePoint(from: AgentId, to: AgentId, t: number) {
  const forward = AGENT_ORDER.indexOf(from) < AGENT_ORDER.indexOf(to);
  const long = Math.abs(POS[from].x - POS[to].x) > 300;
  const { a, b, c } = curve(from, to, (forward ? -1 : 1) * (long ? 40 : 18));
  const u = 1 - t;
  return { x: u * u * a.x + 2 * u * t * c.x + t * t * b.x, y: u * u * a.y + 2 * u * t * c.y + t * t * b.y };
}

const MSG_COLOR: Record<string, string> = {
  task_request: "#8C887F",
  task_result: "#2F6F8F",
  info_request: "#9A6700",
  info_response: "#9A6700",
  decision: "#C2562E",
};

interface Props {
  run: Run;
  events: TraceEvent[];
  now: number;
  selected: AgentId | null;
  onSelect: (a: AgentId) => void;
}

export default function FlowGraph({ run, events, now, selected, onSelect }: Props) {
  const elapsed = (run.cancelledAt ?? now) - run.startedAt;
  const animMs = run.speed === "rapido" ? 700 : run.speed === "normal" ? 1100 : 1600;
  const messages = events.filter((e) => e.type === "message_sent" && e.to);
  const inFlight = messages.filter((e) => elapsed - e.offsetMs < animMs);
  const direct = Array.from(
    new Set(messages.filter((e) => e.title.startsWith("info_")).map((e) => [e.agent, e.to!].sort().join(">"))),
  ).map((k) => k.split(">") as [AgentId, AgentId]);

  return (
    <div className="overflow-x-auto">
      <svg viewBox={`0 0 ${W} ${H}`} className="h-auto w-full min-w-[760px]" role="img" aria-label="Flujo de agentes de la ejecución">
        <defs>
          <marker id="rq-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
            <path d="M 0 0 L 10 5 L 0 10 z" fill="#B3AFA6" />
          </marker>
        </defs>

        <g fontSize={10} fill="#8C887F" fontFamily="ui-monospace, monospace" textAnchor="middle">
          <text x={POS.orchestrator.x} y={14}>1 · planifica</text>
          <text x={POS.code.x} y={14}>2 · mapa del cambio</text>
          <text x={POS.tests.x} y={14}>3 · en paralelo</text>
          <text x={POS.vtr.x} y={14}>4 · documenta</text>
          <text x={POS.verdict.x} y={14}>5 · dictamen</text>
        </g>

        {STRUCTURE.map(([f, t]) => {
          const off = !run.enabledAgents.includes(f) || !run.enabledAgents.includes(t);
          return <path key={`${f}-${t}`} d={path(f, t)} fill="none" stroke={off ? "#EFEDE6" : "#D5D1C5"} strokeWidth={1.3} markerEnd="url(#rq-arrow)" strokeDasharray={off ? "3 4" : undefined} />;
        })}

        {direct.map(([a, b]) => (
          <path key={`d-${a}-${b}`} d={path(a, b, 34)} fill="none" stroke="#9A6700" strokeOpacity={0.55} strokeWidth={1.3} strokeDasharray="6 4" />
        ))}

        {inFlight.map((e) => {
          const pt = messagePoint(e.agent, e.to!, Math.min(1, Math.max(0, (elapsed - e.offsetMs) / animMs)));
          return <circle key={`m-${e.seq}`} cx={pt.x} cy={pt.y} r={6} fill={MSG_COLOR[e.title] ?? "#1F1E1D"} stroke="#FFFFFF" strokeWidth={1.5} />;
        })}

        {AGENT_ORDER.map((id) => {
          const enabled = run.enabledAgents.includes(id);
          const s = agentStats(events, id, enabled);
          const a = AGENTS[id];
          const p = POS[id];
          const isSel = selected === id;
          const working = s.status === "trabajando";
          const off = s.status === "omitido";
          return (
            <g
              key={id}
              transform={`translate(${p.x - NW / 2} ${p.y - NH / 2})`}
              onClick={() => onSelect(id)}
              className={`cursor-pointer ${working ? "node-working" : ""}`}
              role="button"
              tabIndex={0}
              onKeyDown={(ev) => (ev.key === "Enter" || ev.key === " ") && onSelect(id)}
              aria-label={`${a.label}: ${STATUS_TEXT[s.status]}. Abrir detalle.`}
              opacity={off ? 0.5 : 1}
            >
              <rect width={NW} height={NH} rx={12} fill="#FFFFFF" stroke={isSel ? "#1F1E1D" : working ? a.color : "#D5D1C5"} strokeWidth={isSel ? 2 : working ? 1.8 : 1.2} strokeDasharray={off ? "4 3" : undefined} />
              <rect x={0} y={12} width={3.5} height={NH - 24} rx={1.5} fill={a.color} />
              <text x={14} y={20} fontSize={12.5} fontWeight={600} fill="#1F1E1D">
                {a.nodeLabel ?? a.label}
              </text>
              <text x={NW - 10} y={20} fontSize={9.5} textAnchor="end" fill="#8C887F" fontFamily="ui-monospace, monospace">
                {s.llmCalls > 0 ? fmtUsd(s.costUsd) : ""}
              </text>
              <g transform="translate(14 36)">
                <circle cx={3.5} cy={-3.5} r={3.5} fill={STATUS_COLOR[s.status]}>
                  {working && <animate attributeName="opacity" values="1;0.3;1" dur="1s" repeatCount="indefinite" />}
                </circle>
                <text x={12} fontSize={10.5} fill={STATUS_COLOR[s.status]} fontWeight={500}>
                  {STATUS_TEXT[s.status]}
                  {working && s.step ? ` · paso ${s.step}` : ""}
                </text>
              </g>
              <text x={14} y={52} fontSize={9.5} fill="#6B6760">
                {clip(
                  working
                    ? id === "orchestrator"
                      ? "coordinando agentes"
                      : s.lastTitle ?? ""
                    : modelLabel(run.profiles[id].provider, run.profiles[id].model),
                )}
              </text>
              <text x={14} y={66} fontSize={9.5} fill="#8C887F" fontFamily="ui-monospace, monospace">
                {off ? "desactivado" : `LLM×${s.llmCalls} · tools×${s.tools}`}
              </text>
            </g>
          );
        })}
      </svg>
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 border-t border-line bg-sunken/60 px-4 py-2 font-mono text-[10.5px] text-ink-500">
        {Object.entries({ task_request: "tarea", task_result: "resultado", info_request: "consulta entre agentes", decision: "dictamen" }).map(([k, label]) => (
          <span key={k} className="inline-flex items-center gap-1.5">
            <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: MSG_COLOR[k] }} />
            {label}
          </span>
        ))}
        <span className="inline-flex items-center gap-1.5">
          <svg width="26" height="6" aria-hidden>
            <line x1="0" y1="3" x2="26" y2="3" stroke="#9A6700" strokeDasharray="6 4" />
          </svg>
          comunicación directa
        </span>
        <span className="ml-auto">Haz clic en un agente para ver qué está haciendo</span>
      </div>
    </div>
  );
}
