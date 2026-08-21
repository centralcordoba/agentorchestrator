// Utilidades para derivar estado visual a partir de la lista de eventos (traza).
import {
  AGENT_LABELS,
  MESSAGE_TYPE_LABELS,
  type AgentCost,
  type AgentName,
  type CostSummary,
  type RunEvent,
  type SymbolResult,
} from "./types";

export type NodeStatus = "idle" | "working" | "done" | "error";

export const AGENTS: AgentName[] = ["orchestrator", "market_data", "technical", "risk", "skeptic", "decision"];

export interface NodeStats {
  status: NodeStatus;
  sent: number;
  received: number;
  llmCalls: number;
  errors: number;
  activeSymbols: string[];
}

export function symbolsFromEvents(events: RunEvent[]): string[] {
  const start = events.find((e) => e.type === "run_started");
  const fromStart = (start?.data.symbols as string[] | undefined) ?? [];
  if (fromStart.length) return fromStart;
  const set = new Set<string>();
  events.forEach((e) => e.symbol && set.add(e.symbol));
  return Array.from(set);
}

/** Parámetros de la ejecución anunciados en `run_started`. */
export function runSettingsFromEvents(events: RunEvent[]): { messageDelayMs: number | null; agentMode: "rules" | "llm" | null } {
  const start = events.find((e) => e.type === "run_started");
  const raw = start?.data.message_delay_ms;
  const mode = start?.data.agent_mode;
  return {
    messageDelayMs: typeof raw === "number" ? raw : null,
    agentMode: mode === "llm" || mode === "rules" ? mode : null,
  };
}

export function resultsFromEvents(events: RunEvent[]): Record<string, SymbolResult> {
  const out: Record<string, SymbolResult> = {};
  for (const e of events) {
    if (e.type === "symbol_completed" && e.data.result) {
      const r = e.data.result as SymbolResult;
      out[r.symbol] = r;
    }
  }
  return out;
}

function emptyCost(): AgentCost {
  return { calls: 0, input_tokens: 0, output_tokens: 0, cost_usd: null, cost_known_calls: 0, sources: {}, models: {} };
}

function addUsage(acc: AgentCost, usage: Record<string, unknown>): void {
  acc.calls += 1;
  if (typeof usage.input_tokens === "number") acc.input_tokens += usage.input_tokens;
  if (typeof usage.output_tokens === "number") acc.output_tokens += usage.output_tokens;
  if (typeof usage.cost_usd === "number") {
    acc.cost_usd = (acc.cost_usd ?? 0) + usage.cost_usd;
    acc.cost_known_calls += 1;
  }
  const source = typeof usage.cost_source === "string" ? usage.cost_source : "unknown";
  acc.sources[source] = (acc.sources[source] ?? 0) + 1;
  const model = typeof usage.model === "string" ? usage.model : "?";
  acc.models[model] = (acc.models[model] ?? 0) + 1;
}

/** Consumo LLM (tokens y USD) por agente, calculado en vivo a partir de la traza. */
export function costsFromEvents(events: RunEvent[]): CostSummary {
  const summary: CostSummary = { currency: "USD", per_agent: {}, total: emptyCost() };
  for (const e of events) {
    if (e.type !== "llm_call_completed" || !e.data.ok) continue;
    const usage = e.data.usage;
    if (!usage || typeof usage !== "object") continue;
    const agent = e.agent ?? "unknown";
    summary.per_agent[agent] = summary.per_agent[agent] ?? emptyCost();
    addUsage(summary.per_agent[agent], usage as Record<string, unknown>);
    addUsage(summary.total, usage as Record<string, unknown>);
  }
  return summary;
}

export function isRunFinished(events: RunEvent[]): boolean {
  return events.some((e) => e.type === "run_completed");
}

/** Estado de cada agente, filtrado opcionalmente por símbolo. */
export function computeNodeStats(events: RunEvent[], symbol: string | "all"): Record<AgentName, NodeStats> {
  const stats = Object.fromEntries(
    AGENTS.map((a) => [a, { status: "idle", sent: 0, received: 0, llmCalls: 0, errors: 0, activeSymbols: [] } as NodeStats]),
  ) as Record<AgentName, NodeStats>;

  // Estado por (agente, símbolo): el último evento de ciclo de vida gana.
  const perSymbol = new Map<string, NodeStatus>();
  const key = (a: AgentName, s: string | null) => `${a}::${s ?? "-"}`;

  for (const e of events) {
    if (symbol !== "all" && e.symbol && e.symbol !== symbol) continue;
    if (e.type === "message_sent" && e.message) {
      stats[e.message.sender].sent += 1;
      stats[e.message.recipient].received += 1;
    }
    if (!e.agent) continue;
    const s = stats[e.agent];
    switch (e.type) {
      case "agent_started":
        perSymbol.set(key(e.agent, e.symbol), "working");
        break;
      case "agent_completed":
        perSymbol.set(key(e.agent, e.symbol), "done");
        break;
      case "agent_error":
        perSymbol.set(key(e.agent, e.symbol), "error");
        s.errors += 1;
        break;
      case "llm_call_started":
        s.llmCalls += 1;
        break;
      case "run_started":
        perSymbol.set(key("orchestrator", null), "working");
        break;
      case "run_completed":
        perSymbol.set(key("orchestrator", null), "done");
        break;
      default:
        break;
    }
  }

  for (const [k, status] of perSymbol.entries()) {
    const [agent, sym] = k.split("::") as [AgentName, string];
    const s = stats[agent];
    if (status === "working" && sym !== "-") s.activeSymbols.push(sym);
    // Prioridad: working > error > done > idle
    const rank: Record<NodeStatus, number> = { idle: 0, done: 1, error: 2, working: 3 };
    if (rank[status] > rank[s.status]) s.status = status;
  }
  return stats;
}

export function formatTime(iso: string): string {
  const d = new Date(iso);
  const hh = String(d.getHours()).padStart(2, "0");
  const mm = String(d.getMinutes()).padStart(2, "0");
  const ss = String(d.getSeconds()).padStart(2, "0");
  const ms = String(d.getMilliseconds()).padStart(3, "0");
  return `${hh}:${mm}:${ss}.${ms}`;
}

function str(v: unknown, max = 90): string {
  if (v === null || v === undefined) return "";
  const s = typeof v === "string" ? v : JSON.stringify(v);
  return s.length > max ? `${s.slice(0, max)}…` : s;
}

/** Línea resumen de un evento para el log. */
export function describeEvent(e: RunEvent): string {
  const d = e.data;
  switch (e.type) {
    case "run_started":
      return `Ejecución iniciada · ${(d.symbols as string[]).join(", ")} · modo ${d.agent_mode ?? "rules"} · paralelismo ${d.max_parallel} · retardo por mensaje ${d.message_delay_ms ?? 0} ms · LLM ${d.llm_provider} · datos ${d.market_data_provider}`;
    case "run_completed":
      return `Ejecución completada · ${Object.entries((d.results as Record<string, string>) || {})
        .map(([s, r]) => `${s}=${r}`)
        .join(" ")}`;
    case "symbol_started":
      return "Inicio del análisis del símbolo";
    case "symbol_completed": {
      const r = d.result as SymbolResult | undefined;
      return r ? `Símbolo completado → ${r.decision}` : "Símbolo completado";
    }
    case "agent_started":
      return `Recibe ${MESSAGE_TYPE_LABELS[(d.message_type as keyof typeof MESSAGE_TYPE_LABELS) ?? "task_request"] ?? d.message_type} de ${AGENT_LABELS[d.from as AgentName] ?? d.from}`;
    case "agent_completed":
      return `Completado: ${str(d.summary)}`;
    case "agent_error":
      return `Error: ${str(d.error)}`;
    case "message_sent": {
      const m = e.message!;
      const p = m.payload as Record<string, unknown>;
      const hint =
        m.type === "error"
          ? str(p.reason)
          : m.type === "decision"
            ? `${p.decision} (conf. ${p.confidence})`
            : m.type === "opinion"
              ? str(p.stance ?? p.risk_level ?? "")
              : m.type === "challenge"
                ? `${(p.counterarguments as unknown[] | undefined)?.length ?? 0} objeciones`
                : m.type === "info_request"
                  ? str(p.reason)
                  : m.type === "task_request"
                    ? str(p.data_ref ?? p.symbol ?? "")
                    : str(p.bars ? `${p.bars} sesiones` : "");
      return `${AGENT_LABELS[m.sender]} → ${AGENT_LABELS[m.recipient]} · ${MESSAGE_TYPE_LABELS[m.type]}${hint ? ` · ${hint}` : ""}`;
    }
    case "llm_call_started":
      return d.mode === "llm"
        ? `Turno ${d.step} del agente (${d.task}) · herramientas: ${((d.tools as string[]) || []).join(", ") || "ninguna"} · ${d.provider}`
        : `Llamada LLM (${d.task}) · proveedor ${d.provider}`;
    case "llm_call_completed": {
      if (!d.ok) return `LLM falló (${d.task}${d.step ? ` · turno ${d.step}` : ""}): ${str(d.error)} → fallback ${d.fallback}`;
      const calls = (d.tool_calls as string[] | undefined) ?? [];
      if (d.step) return calls.length ? `El modelo pide herramientas: ${calls.join(", ")}` : `El modelo entrega su respuesta final (${d.task})`;
      return `LLM respondió (${d.task}) · generado por ${d.generated_by}${Number(d.warnings) ? ` · ${d.warnings} avisos` : ""}`;
    }
    case "tool_called": {
      const res = d.result as Record<string, unknown> | undefined;
      const err = res && typeof res.error === "string" ? ` → error: ${str(res.error, 60)}` : "";
      return `Herramienta ${d.tool}(${str(d.arguments, 60)})${err}`;
    }
    case "guardrail_applied":
      return `Guardarraíl ${str(d.rule, 70)} · ${str(d.before, 40)} → ${str(d.after, 40)}`;
    case "validation_warning":
      return `Validación: ${(d.warnings as string[]).join(" | ")}${d.discarded ? " · explicación descartada" : ""}`;
    case "disagreement":
      return `Discrepancia con ${AGENT_LABELS[d.against as AgentName]} · ${(d.counterarguments as unknown[]).length} objeciones · respuesta: ${d.technical_response ?? "—"}`;
    case "decision_made":
      return `Decisión: ${d.decision} (conf. ${d.confidence})`;
    default:
      return e.type;
  }
}

export const EVENT_GROUPS: Record<string, RunEvent["type"][]> = {
  mensajes: ["message_sent"],
  agentes: ["agent_started", "agent_completed", "agent_error"],
  llm: ["llm_call_started", "llm_call_completed", "validation_warning", "tool_called"],
  sistema: ["run_started", "run_completed", "symbol_started", "symbol_completed", "disagreement", "decision_made", "guardrail_applied"],
};
