"use client";

// Grafo del flujo. Las columnas se calculan con las mismas reglas que el motor
// (`orq/domain/orchestration.py`), no con posiciones escritas a mano: así el dibujo se adapta
// solo cuando el plan activa o desactiva agentes.
import { useMemo, useState } from "react";
import { AGENTS, AGENT_ORDER, MODEL_CATALOG } from "@/lib/rq/agents";
import type { AgentId } from "@/lib/rq/types";
import type { TraceEvent } from "@/lib/api/types";
import { agentStatuses, type LiveAgentStatus, type RunStream } from "@/lib/api/useRunStream";
import { fmtUsd } from "./ui";

/** Va antes que todos. */
const FIRST: AgentId = "orchestrator";
/** Va después de todos: consolida lo que produjeron los demás. */
const LAST: AgentId = "verdict";

const NW = 156;
const NH = 74;
const COL = 208; // separación entre oleadas
const ROW = 102; // separación entre agentes de la misma oleada
const PAD_X = 28;
const PAD_TOP = 30;
const PAD_BOTTOM = 18;

const STATUS_COLOR: Record<LiveAgentStatus, string> = {
  pendiente: "#8C887F",
  trabajando: "#2F6F8F",
  completado: "#2E7D5B",
  omitido: "#B3AFA6",
  fallido: "#B3362B",
};

const STATUS_TEXT: Record<LiveAgentStatus, string> = {
  pendiente: "en espera",
  trabajando: "trabajando",
  completado: "completado",
  omitido: "omitido",
  fallido: "sin resultado",
};

/** Qué hace cada etapa, para el rótulo de la columna. */
const WAVE_CAPTION: Partial<Record<AgentId, string>> = {
  orchestrator: "planifica",
  code: "mapa del cambio",
  vtr: "documenta",
  verdict: "dictamen",
};

type Point = { x: number; y: number };

function clip(text: string, max = 25): string {
  return text.length > max ? `${text.slice(0, max - 1)}…` : text;
}

/** Dependencias efectivas dentro de los agentes activos. Espejo de `dependencies_of` del dominio. */
function dependenciesOf(agent: AgentId, active: Set<AgentId>): AgentId[] {
  const declared = new Set<AgentId>(AGENTS[agent]?.dependsOn ?? []);
  if (agent !== FIRST) declared.add(FIRST);
  if (agent === LAST) for (const other of active) if (other !== LAST) declared.add(other);
  return [...declared].filter((d) => active.has(d));
}

/** Oleadas: todo lo que hay en una puede correr en paralelo. Espejo de `execution_waves`. */
function executionWaves(enabled: AgentId[]): AgentId[][] {
  const active = new Set(enabled);
  const pending = new Set(enabled);
  const done = new Set<AgentId>();
  const waves: AgentId[][] = [];

  while (pending.size) {
    const ready = [...pending].filter((a) => dependenciesOf(a, active).every((d) => done.has(d)));
    // Si hubiera un ciclo, se dibuja el resto junto en vez de colgar el navegador.
    const wave = ready.length ? ordered(ready) : ordered([...pending]);
    waves.push(wave);
    for (const agent of wave) {
      done.add(agent);
      pending.delete(agent);
    }
  }
  return waves;
}

/** Orden del catálogo, para que el dibujo sea siempre igual de legible. */
function ordered(agents: AgentId[]): AgentId[] {
  const known = AGENT_ORDER.filter((a) => agents.includes(a));
  return [...known, ...agents.filter((a) => !AGENT_ORDER.includes(a))];
}

/** Flechas: una por dependencia activa, y las puntas del grafo confluyen en el Dictamen. */
function edgesOf(enabled: AgentId[]): [AgentId, AgentId][] {
  const active = new Set(enabled);
  const edges: [AgentId, AgentId][] = [];
  const withSuccessor = new Set<AgentId>();

  for (const agent of ordered(enabled)) {
    if (agent === FIRST || agent === LAST) continue;
    const declared = (AGENTS[agent]?.dependsOn ?? []).filter((d) => active.has(d));
    const from = declared.length ? declared : active.has(FIRST) ? [FIRST] : [];
    for (const source of from) {
      edges.push([source, agent]);
      withSuccessor.add(source);
    }
  }

  if (active.has(LAST)) {
    for (const agent of ordered(enabled)) {
      if (agent !== LAST && !withSuccessor.has(agent)) edges.push([agent, LAST]);
    }
  }
  return edges;
}

/** Punto por donde la flecha toca el borde del nodo, no su centro. */
function anchor(from: Point, to: Point): Point {
  const dx = to.x - from.x;
  const dy = to.y - from.y;
  const s = Math.min(NW / 2 / Math.max(Math.abs(dx), 1e-6), NH / 2 / Math.max(Math.abs(dy), 1e-6));
  return { x: from.x + dx * s, y: from.y + dy * s };
}

function path(from: Point, to: Point): string {
  const a = anchor(from, to);
  const b = anchor(to, from);
  const dx = b.x - a.x;
  const dy = b.y - a.y;
  const len = Math.hypot(dx, dy) || 1;
  // Curva suave hacia fuera: con cinco agentes en paralelo, las rectas se solapan.
  const bend = Math.abs(dy) > 8 ? -14 : 0;
  const c = { x: (a.x + b.x) / 2 + (-dy / len) * bend, y: (a.y + b.y) / 2 + (dx / len) * bend };
  return `M ${a.x} ${a.y} Q ${c.x} ${c.y} ${b.x} ${b.y}`;
}

interface AgentStats {
  llmCalls: number;
  tools: number;
  costUsd: number;
  lastTitle: string;
  events: TraceEvent[];
}

function statsByAgent(events: TraceEvent[]): Record<string, AgentStats> {
  const stats: Record<string, AgentStats> = {};
  for (const event of events) {
    const agent = event.agent;
    if (!agent) continue;
    const entry = (stats[agent] ??= { llmCalls: 0, tools: 0, costUsd: 0, lastTitle: "", events: [] });
    entry.events.push(event);
    if (event.type === "llm_call") entry.llmCalls += 1;
    if (event.type === "tool_called") entry.tools += 1;
    entry.costUsd += event.usage?.costUsd ?? 0;
    if (event.title) entry.lastTitle = event.title;
  }
  return stats;
}

const VACIO: AgentStats = { llmCalls: 0, tools: 0, costUsd: 0, lastTitle: "", events: [] };

function modelName(provider: string | undefined, model: string | undefined): string {
  if (!provider || !model) return "";
  const catalog = (MODEL_CATALOG as Record<string, { id: string; label: string }[]>)[provider];
  return catalog?.find((m) => m.id === model)?.label ?? model;
}

export function FlowGraph({ stream }: { stream: RunStream }) {
  const [selected, setSelected] = useState<AgentId | null>(null);
  const enabled = useMemo(
    () => (stream.run?.enabledAgents ?? []).filter((a): a is AgentId => a in AGENTS),
    [stream.run?.enabledAgents],
  );
  const statuses = useMemo(() => agentStatuses(stream.events, enabled), [stream.events, enabled]);
  const stats = useMemo(() => statsByAgent(stream.events), [stream.events]);

  const layout = useMemo(() => {
    const waves = executionWaves(enabled);
    const rows = Math.max(1, ...waves.map((w) => w.length));
    const positions = {} as Record<AgentId, Point>;
    waves.forEach((wave, column) => {
      wave.forEach((agent, row) => {
        positions[agent] = {
          x: PAD_X + NW / 2 + column * COL,
          y: PAD_TOP + NH / 2 + ((rows - wave.length) / 2 + row) * ROW,
        };
      });
    });
    return {
      waves,
      positions,
      width: PAD_X * 2 + NW + Math.max(0, waves.length - 1) * COL,
      height: PAD_TOP + rows * ROW + PAD_BOTTOM,
    };
  }, [enabled]);

  const edges = useMemo(() => edgesOf(enabled), [enabled]);

  if (!enabled.length) return null;

  const { positions, width, height } = layout;

  return (
    <div className="panel overflow-hidden">
      <div className="overflow-x-auto">
        <svg
          viewBox={`0 0 ${width} ${height}`}
          className="h-auto w-full min-w-[760px]"
          role="img"
          aria-label="Flujo de agentes de la ejecución"
        >
          <defs>
            <marker
              id="rq-arrow"
              viewBox="0 0 10 10"
              refX="9"
              refY="5"
              markerWidth="6"
              markerHeight="6"
              orient="auto-start-reverse"
            >
              <path d="M 0 0 L 10 5 L 0 10 z" fill="#B3AFA6" />
            </marker>
          </defs>

          <g fontSize={10} fill="#8C887F" fontFamily="ui-monospace, monospace" textAnchor="middle">
            {layout.waves.map((wave, i) => {
              const caption =
                wave.length > 1 ? "en paralelo" : WAVE_CAPTION[wave[0]] ?? AGENTS[wave[0]]?.label ?? "";
              return (
                <text key={`c-${i}`} x={PAD_X + NW / 2 + i * COL} y={16}>
                  {`${i + 1} · ${caption}`}
                </text>
              );
            })}
          </g>

          {edges.map(([from, to]) => {
            const a = positions[from];
            const b = positions[to];
            if (!a || !b) return null;
            const d = path(a, b);
            const entregado = statuses[from] === "completado";
            const enVuelo = entregado && statuses[to] === "trabajando";
            return (
              <g key={`${from}-${to}`}>
                <path
                  d={d}
                  fill="none"
                  stroke={entregado ? "#B3AFA6" : "#E7E4DB"}
                  strokeWidth={entregado ? 1.6 : 1.3}
                  markerEnd="url(#rq-arrow)"
                />
                {enVuelo && (
                  <circle r={5} fill="#2F6F8F" stroke="#FFFFFF" strokeWidth={1.5}>
                    <animateMotion dur="1.4s" repeatCount="indefinite" path={d} />
                  </circle>
                )}
              </g>
            );
          })}

          {enabled.map((id) => {
            const p = positions[id];
            if (!p) return null;
            const definition = AGENTS[id];
            const status = statuses[id] ?? "pendiente";
            const s = stats[id] ?? VACIO;
            const isSel = selected === id;
            const working = status === "trabajando";
            const apagado = status === "omitido" || status === "fallido";
            const profile = stream.run?.profiles?.[id];
            return (
              <g
                key={id}
                transform={`translate(${p.x - NW / 2} ${p.y - NH / 2})`}
                onClick={() => setSelected(isSel ? null : id)}
                className={`cursor-pointer ${working ? "node-working" : ""}`}
                role="button"
                tabIndex={0}
                onKeyDown={(ev) =>
                  (ev.key === "Enter" || ev.key === " ") && setSelected(isSel ? null : id)
                }
                aria-label={`${definition.label}: ${STATUS_TEXT[status]}. Ver detalle.`}
                opacity={apagado ? 0.6 : 1}
              >
                <rect
                  width={NW}
                  height={NH}
                  rx={12}
                  fill="#FFFFFF"
                  stroke={isSel ? "#1F1E1D" : working ? definition.color : "#D5D1C5"}
                  strokeWidth={isSel ? 2 : working ? 1.8 : 1.2}
                  strokeDasharray={status === "omitido" ? "4 3" : undefined}
                />
                <rect x={0} y={12} width={3.5} height={NH - 24} rx={1.5} fill={definition.color} />
                <text x={14} y={20} fontSize={12.5} fontWeight={600} fill="#1F1E1D">
                  {definition.nodeLabel ?? definition.label}
                </text>
                <text
                  x={NW - 10}
                  y={20}
                  fontSize={9.5}
                  textAnchor="end"
                  fill="#8C887F"
                  fontFamily="ui-monospace, monospace"
                >
                  {s.llmCalls > 0 ? fmtUsd(s.costUsd) : ""}
                </text>
                <g transform="translate(14 36)">
                  <circle cx={3.5} cy={-3.5} r={3.5} fill={STATUS_COLOR[status]}>
                    {working && (
                      <animate
                        attributeName="opacity"
                        values="1;0.3;1"
                        dur="1s"
                        repeatCount="indefinite"
                      />
                    )}
                  </circle>
                  <text x={12} fontSize={10.5} fill={STATUS_COLOR[status]} fontWeight={500}>
                    {STATUS_TEXT[status]}
                  </text>
                </g>
                <text x={14} y={52} fontSize={9.5} fill="#6B6760">
                  {clip(working && s.lastTitle ? s.lastTitle : modelName(profile?.provider, profile?.model))}
                </text>
                <text x={14} y={66} fontSize={9.5} fill="#8C887F" fontFamily="ui-monospace, monospace">
                  {`LLM×${s.llmCalls} · tools×${s.tools}`}
                </text>
              </g>
            );
          })}
        </svg>
      </div>

      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 border-t border-line bg-sunken/60 px-4 py-2 font-mono text-[10.5px] text-ink-500">
        {(["pendiente", "trabajando", "completado", "fallido"] as LiveAgentStatus[]).map((estado) => (
          <span key={estado} className="inline-flex items-center gap-1.5">
            <span
              className="inline-block h-2.5 w-2.5 rounded-full"
              style={{ background: STATUS_COLOR[estado] }}
            />
            {STATUS_TEXT[estado]}
          </span>
        ))}
        <span className="inline-flex items-center gap-1.5">
          <span className="inline-block h-2.5 w-2.5 rounded-full bg-info" />
          entrega en curso
        </span>
        <span className="ml-auto">Haz clic en un agente para ver qué está haciendo</span>
      </div>

      {selected && (
        <AgentDetail
          agent={selected}
          status={statuses[selected] ?? "pendiente"}
          stats={stats[selected] ?? VACIO}
          stream={stream}
          onClose={() => setSelected(null)}
        />
      )}
    </div>
  );
}

function AgentDetail({
  agent,
  status,
  stats,
  stream,
  onClose,
}: {
  agent: AgentId;
  status: LiveAgentStatus;
  stats: AgentStats;
  stream: RunStream;
  onClose: () => void;
}) {
  const definition = AGENTS[agent];
  const profile = stream.run?.profiles?.[agent];
  const execution = stream.run?.executions?.[agent];
  const ultimos = stats.events.slice(-4).reverse();

  return (
    <div className="border-t border-line px-4 py-3">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-[14px] font-medium text-ink-900">
            {definition.label}{" "}
            <span className="text-[12px] font-normal" style={{ color: STATUS_COLOR[status] }}>
              · {STATUS_TEXT[status]}
            </span>
          </h3>
          <p className="mt-0.5 max-w-[70ch] text-[12.5px] leading-5 text-ink-500">{definition.role}</p>
        </div>
        <button className="btn-ghost shrink-0" onClick={onClose}>
          Cerrar
        </button>
      </div>

      <dl className="mt-3 grid gap-x-6 gap-y-1 text-[12px] sm:grid-cols-2 lg:grid-cols-4">
        <div>
          <dt className="text-ink-400">Modelo</dt>
          <dd className="font-mono text-ink-900">
            {modelName(profile?.provider, profile?.model) || "—"}
          </dd>
        </div>
        <div>
          <dt className="text-ink-400">Prompt</dt>
          <dd className="font-mono text-ink-900">
            {profile ? `v${profile.promptVersion}` : "—"}
          </dd>
        </div>
        <div>
          <dt className="text-ink-400">Llamadas</dt>
          <dd className="font-mono text-ink-900">
            LLM×{stats.llmCalls} · tools×{stats.tools} · {fmtUsd(stats.costUsd)}
          </dd>
        </div>
        <div>
          <dt className="text-ink-400">Herramientas</dt>
          <dd className="font-mono text-ink-700">{definition.tools.join(", ") || "—"}</dd>
        </div>
      </dl>

      {(execution?.error || execution?.reason) && (
        <p className="mt-2 text-[12px] text-ink-700">{execution.error || execution.reason}</p>
      )}

      {ultimos.length > 0 && (
        <ul className="mt-3 space-y-1 border-t border-line pt-2 text-[12px]">
          {ultimos.map((event) => (
            <li key={event.seq} className="flex gap-2">
              <span className="shrink-0 font-mono text-[11px] text-ink-400">{event.type}</span>
              <span className="min-w-0 text-ink-700">
                {event.title}
                {event.detail ? ` · ${event.detail}` : ""}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default FlowGraph;
