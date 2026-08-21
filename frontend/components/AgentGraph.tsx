"use client";

import { useEffect, useMemo, useState } from "react";
import AgentNode, { NODE_H, NODE_W } from "./AgentNode";
import { AGENTS, computeNodeStats } from "@/lib/trace";
import { MESSAGE_TYPE_LABELS, type AgentName, type MessageType, type RunEvent } from "@/lib/types";

const POS: Record<AgentName, { x: number; y: number }> = {
  orchestrator: { x: 100, y: 175 },
  market_data: { x: 300, y: 175 },
  technical: { x: 500, y: 75 },
  risk: { x: 500, y: 275 },
  skeptic: { x: 700, y: 175 },
  decision: { x: 900, y: 175 },
};

const VIEW_W = 1000;
const VIEW_H = 330;
const ANIM_MS = 1400;
const HOT_MS = 2200;

interface Edge {
  from: AgentName;
  to: AgentName;
  path: string;
  key: string;
}

/** Punto en el borde del nodo en dirección a otro punto. */
function anchor(from: { x: number; y: number }, to: { x: number; y: number }) {
  const dx = to.x - from.x;
  const dy = to.y - from.y;
  const hw = NODE_W / 2;
  const hh = NODE_H / 2;
  const scale = Math.min(hw / Math.max(Math.abs(dx), 1e-6), hh / Math.max(Math.abs(dy), 1e-6));
  return { x: from.x + dx * scale, y: from.y + dy * scale };
}

/** Curva entre dos nodos; las direcciones opuestas se desplazan para no solaparse. */
function edgePath(from: AgentName, to: AgentName): string {
  const a = anchor(POS[from], POS[to]);
  const b = anchor(POS[to], POS[from]);
  const dx = b.x - a.x;
  const dy = b.y - a.y;
  const len = Math.hypot(dx, dy) || 1;
  // desplazamiento perpendicular constante según el sentido (from<to vs to<from)
  const sign = AGENTS.indexOf(from) < AGENTS.indexOf(to) ? -1 : 1;
  const nx = (-dy / len) * 14 * sign;
  const ny = (dx / len) * 14 * sign;
  const mx = (a.x + b.x) / 2 + nx;
  const my = (a.y + b.y) / 2 + ny;
  return `M ${a.x + nx * 0.4} ${a.y + ny * 0.4} Q ${mx} ${my} ${b.x + nx * 0.4} ${b.y + ny * 0.4}`;
}

const TYPE_COLOR: Record<MessageType, string> = {
  task_request: "#94a3b8",
  task_result: "#38bdf8",
  info_request: "#fbbf24",
  info_response: "#fbbf24",
  opinion: "#34d399",
  challenge: "#f472b6",
  decision: "#f97316",
  error: "#f43f5e",
};

interface Props {
  events: RunEvent[];
  symbol: string | "all";
  running: boolean;
  selectedAgent: AgentName | null;
  onSelectAgent: (a: AgentName | null) => void;
  onSelectEvent: (e: RunEvent) => void;
}

export default function AgentGraph({ events, symbol, running, selectedAgent, onSelectAgent, onSelectEvent }: Props) {
  const [, setTick] = useState(0);

  // Re-render periódico mientras hay actividad para que las animaciones caduquen.
  useEffect(() => {
    if (!running) return;
    const t = setInterval(() => setTick((n) => n + 1), 250);
    return () => clearInterval(t);
  }, [running]);

  const stats = useMemo(() => computeNodeStats(events, symbol), [events, symbol]);

  const messages = useMemo(
    () =>
      events.filter(
        (e) => e.type === "message_sent" && e.message && (symbol === "all" || e.symbol === symbol),
      ),
    [events, symbol],
  );

  // Aristas: todas las combinaciones que hayan transportado al menos un mensaje, más la topología base.
  const edges = useMemo(() => {
    const base: [AgentName, AgentName][] = [
      ["orchestrator", "market_data"],
      ["market_data", "orchestrator"],
      ["orchestrator", "technical"],
      ["technical", "orchestrator"],
      ["orchestrator", "risk"],
      ["risk", "orchestrator"],
      ["risk", "market_data"],
      ["market_data", "risk"],
      ["orchestrator", "skeptic"],
      ["skeptic", "orchestrator"],
      ["skeptic", "technical"],
      ["technical", "skeptic"],
      ["orchestrator", "decision"],
      ["decision", "orchestrator"],
    ];
    const seen = new Set(base.map(([f, t]) => `${f}>${t}`));
    messages.forEach((e) => {
      const k = `${e.message!.sender}>${e.message!.recipient}`;
      if (!seen.has(k)) {
        seen.add(k);
        base.push([e.message!.sender, e.message!.recipient]);
      }
    });
    return base.map<Edge>(([from, to]) => ({ from, to, key: `${from}>${to}`, path: edgePath(from, to) }));
  }, [messages]);

  const now = Date.now();
  const lastByEdge = new Map<string, RunEvent>();
  let total = 0;
  messages.forEach((e) => {
    total += 1;
    lastByEdge.set(`${e.message!.sender}>${e.message!.recipient}`, e);
  });
  const animated = messages.filter((e) => e.receivedAt && now - e.receivedAt < ANIM_MS).slice(-24);

  return (
    <div className="panel">
      <div className="panel-title">
        <span>Grafo de agentes · {symbol === "all" ? "todos los símbolos" : symbol}</span>
        <span className="font-mono normal-case tracking-normal text-slate-500">{total} mensajes</span>
      </div>
      <svg viewBox={`0 0 ${VIEW_W} ${VIEW_H}`} className="h-auto w-full" role="img" aria-label="Grafo de comunicación entre agentes">
        <defs>
          <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
            <path d="M 0 0 L 10 5 L 0 10 z" fill="#64748b" />
          </marker>
          <marker id="arrow-hot" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
            <path d="M 0 0 L 10 5 L 0 10 z" fill="#e2e8f0" />
          </marker>
        </defs>

        {/* etiquetas de fase */}
        <g fontSize={10} fill="#475569" fontFamily="ui-monospace, monospace">
          <text x={POS.orchestrator.x} y={18} textAnchor="middle">1. inicia</text>
          <text x={POS.market_data.x} y={18} textAnchor="middle">2. datos</text>
          <text x={POS.technical.x} y={18} textAnchor="middle">3. análisis en paralelo</text>
          <text x={POS.skeptic.x} y={18} textAnchor="middle">4. revisión crítica</text>
          <text x={POS.decision.x} y={18} textAnchor="middle">5. decisión</text>
        </g>

        {edges.map((edge) => {
          const last = lastByEdge.get(edge.key);
          const hot = last?.receivedAt ? now - last.receivedAt < HOT_MS : false;
          const used = Boolean(last);
          const dashed = edge.from === "risk" && edge.to === "market_data" ? "6 4" : edge.from === "skeptic" && edge.to === "technical" ? "6 4" : undefined;
          return (
            <g key={edge.key} onClick={() => last && onSelectEvent(last)} className={last ? "cursor-pointer" : ""}>
              <path
                d={edge.path}
                fill="none"
                stroke={hot ? "#e2e8f0" : used ? "#64748b" : "#2f3b54"}
                strokeWidth={hot ? 2.4 : 1.4}
                strokeDasharray={dashed}
                markerEnd={hot ? "url(#arrow-hot)" : "url(#arrow)"}
                opacity={used ? 1 : 0.7}
              />
              {/* zona de clic más amplia */}
              <path d={edge.path} fill="none" stroke="transparent" strokeWidth={12} />
            </g>
          );
        })}

        {/* mensajes en vuelo */}
        {animated.map((e) => {
          const m = e.message!;
          const edge = edges.find((x) => x.from === m.sender && x.to === m.recipient);
          if (!edge) return null;
          return (
            <g key={m.id}>
              <circle r={6} fill={TYPE_COLOR[m.type]} stroke="#0b0f17" strokeWidth={1.5}>
                <animateMotion dur={`${ANIM_MS / 1000}s`} path={edge.path} fill="freeze" />
              </circle>
            </g>
          );
        })}

        {AGENTS.map((name) => (
          <AgentNode
            key={name}
            name={name}
            x={POS[name].x}
            y={POS[name].y}
            stats={stats[name]}
            selected={selectedAgent === name}
            onClick={() => onSelectAgent(selectedAgent === name ? null : name)}
          />
        ))}

      </svg>
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 border-t border-ink-700 px-4 py-2 font-mono text-[10.5px] text-slate-400">
        {(Object.keys(TYPE_COLOR) as MessageType[]).map((t) => (
          <span key={t} className="inline-flex items-center gap-1.5">
            <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: TYPE_COLOR[t] }} />
            {MESSAGE_TYPE_LABELS[t]}
          </span>
        ))}
        <span className="ml-auto inline-flex items-center gap-1.5">
          <svg width="26" height="6" aria-hidden>
            <line x1="0" y1="3" x2="26" y2="3" stroke="#94a3b8" strokeDasharray="6 4" />
          </svg>
          comunicación directa entre agentes
        </span>
      </div>
    </div>
  );
}
