// Tipos espejo de backend/app/models.py

export type AgentName = "orchestrator" | "market_data" | "technical" | "risk" | "skeptic" | "decision";

export type MessageType =
  | "task_request"
  | "task_result"
  | "info_request"
  | "info_response"
  | "opinion"
  | "challenge"
  | "decision"
  | "error";

export type EventType =
  | "run_started"
  | "run_completed"
  | "symbol_started"
  | "symbol_completed"
  | "agent_started"
  | "agent_completed"
  | "agent_error"
  | "message_sent"
  | "llm_call_started"
  | "llm_call_completed"
  | "validation_warning"
  | "disagreement"
  | "decision_made"
  | "tool_called"
  | "guardrail_applied";

export type AgentMode = "rules" | "llm";

export type Decision = "COMPRA" | "VENTA" | "ESPERAR" | "NO_ANALIZABLE";
export type Stance = "ALCISTA" | "BAJISTA" | "NEUTRAL";
export type RiskLevel = "BAJO" | "MEDIO" | "ALTO";

export interface AgentMessage {
  id: string;
  run_id: string;
  symbol: string | null;
  sender: AgentName;
  recipient: AgentName;
  type: MessageType;
  payload: Record<string, unknown>;
  in_reply_to: string | null;
  timestamp: string;
}

export interface RunEvent {
  seq: number;
  run_id: string;
  type: EventType;
  timestamp: string;
  symbol: string | null;
  agent: AgentName | null;
  message: AgentMessage | null;
  data: Record<string, unknown>;
  /** Marca de tiempo local de recepción (para animaciones). */
  receivedAt?: number;
}

export interface LLMExplanation {
  summary: string;
  facts_used: string[];
  caveats: string[];
  generated_by: string;
  validation_warnings: string[];
}

export interface Evidence {
  fact: string;
  observation: string;
}

export interface AgentOpinion {
  agent: AgentName;
  stance: Stance | null;
  risk_level: RiskLevel | null;
  agrees: boolean | null;
  confidence: number;
  facts: Record<string, unknown>;
  explanation: LLMExplanation;
  mode?: "rules" | "llm" | "rules_fallback";
  evidence?: Evidence[];
  rule_reference?: Record<string, unknown>;
}

export interface SymbolResult {
  symbol: string;
  decision: Decision;
  confidence: number;
  rationale: string;
  opinions: AgentOpinion[];
  data_source: string | null;
  bars_used: number;
  last_close: number | null;
  last_bar_date: string | null;
  error: string | null;
  disagreements: number;
}

export type RunStatus = "pending" | "running" | "completed" | "failed";

export interface RunSummary {
  run_id: string;
  status: RunStatus;
  symbols: string[];
  created_at: string;
  finished_at: string | null;
  results: Record<string, SymbolResult>;
  providers: Record<string, string>;
  message_delay_ms?: number;
  agent_mode?: AgentMode;
  disclaimer: string;
}

export interface RunCreated {
  run_id: string;
  symbols: string[];
  rejected: Record<string, string>;
  message_delay_ms: number;
  agent_mode: AgentMode;
}

export interface AppConfig {
  llm_provider: string;
  market_data_provider: string;
  max_symbols_per_run: number;
  max_parallel_symbols: number;
  demo_delay_ms: number;
  message_delay_ms: number;
  max_message_delay_ms: number;
  agent_mode: AgentMode;
  llm_supports_tools: boolean;
  disclaimer: string;
}

export const AGENT_MODE_LABELS: Record<AgentMode, { label: string; hint: string }> = {
  rules: { label: "Reglas", hint: "Las reglas deciden; el LLM solo redacta las explicaciones" },
  llm: { label: "LLM", hint: "El modelo razona con herramientas; las reglas vigilan (guardarraíles)" },
};

/** Ritmos predefinidos: retardo (ms) aplicado a cada mensaje entre agentes. */
export const PACE_OPTIONS: { label: string; ms: number; hint: string }[] = [
  { label: "Rápido", ms: 0, hint: "Sin retardo entre mensajes" },
  { label: "Normal", ms: 800, hint: "0,8 s por mensaje" },
  { label: "Lento", ms: 1500, hint: "1,5 s por mensaje: cómodo para explicar en clase" },
  { label: "Muy lento", ms: 3000, hint: "3 s por mensaje: paso a paso" },
];

export const AGENT_LABELS: Record<AgentName, string> = {
  orchestrator: "Orquestador",
  market_data: "Datos de mercado",
  technical: "Analista técnico",
  risk: "Analista de riesgo",
  skeptic: "Escéptico",
  decision: "Decisión",
};

// Colores de agente: oscuros y desaturados, legibles sobre fondo claro.
export const AGENT_COLORS: Record<AgentName, string> = {
  orchestrator: "#5B4B8A",
  market_data: "#2F6F8F",
  technical: "#2E7D5B",
  risk: "#9A6700",
  skeptic: "#A8445C",
  decision: "#C2562E",
};

export const AGENT_SOFT_COLORS: Record<AgentName, string> = {
  orchestrator: "#EDEAF5",
  market_data: "#E6F0F5",
  technical: "#E7F2EC",
  risk: "#FBF1DC",
  skeptic: "#F7E8EC",
  decision: "#F7EAE3",
};

export const MESSAGE_TYPE_LABELS: Record<MessageType, string> = {
  task_request: "petición de tarea",
  task_result: "resultado",
  info_request: "petición de información",
  info_response: "respuesta de información",
  opinion: "opinión",
  challenge: "réplica",
  decision: "decisión",
  error: "error",
};

export const DECISION_STYLES: Record<Decision, string> = {
  COMPRA: "bg-ok-soft text-ok border-ok/30",
  VENTA: "bg-danger-soft text-danger border-danger/30",
  ESPERAR: "bg-warn-soft text-warn border-warn/30",
  NO_ANALIZABLE: "bg-sunken text-ink-500 border-line-strong",
};

export const DECISION_DOT: Record<Decision, string> = {
  COMPRA: "#2E7D5B",
  VENTA: "#B3362B",
  ESPERAR: "#9A6700",
  NO_ANALIZABLE: "#8C887F",
};
