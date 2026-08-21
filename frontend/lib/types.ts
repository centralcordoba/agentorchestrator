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
  | "decision_made";

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

export interface AgentOpinion {
  agent: AgentName;
  stance: Stance | null;
  risk_level: RiskLevel | null;
  agrees: boolean | null;
  confidence: number;
  facts: Record<string, unknown>;
  explanation: LLMExplanation;
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
  disclaimer: string;
}

export interface RunCreated {
  run_id: string;
  symbols: string[];
  rejected: Record<string, string>;
}

export interface AppConfig {
  llm_provider: string;
  market_data_provider: string;
  max_symbols_per_run: number;
  max_parallel_symbols: number;
  demo_delay_ms: number;
  disclaimer: string;
}

export const AGENT_LABELS: Record<AgentName, string> = {
  orchestrator: "Orquestador",
  market_data: "Datos de mercado",
  technical: "Analista técnico",
  risk: "Analista de riesgo",
  skeptic: "Escéptico",
  decision: "Decisión",
};

export const AGENT_COLORS: Record<AgentName, string> = {
  orchestrator: "#a78bfa",
  market_data: "#38bdf8",
  technical: "#34d399",
  risk: "#fbbf24",
  skeptic: "#f472b6",
  decision: "#f97316",
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
  COMPRA: "bg-emerald-500/15 text-emerald-300 border-emerald-500/40",
  VENTA: "bg-rose-500/15 text-rose-300 border-rose-500/40",
  ESPERAR: "bg-amber-500/15 text-amber-300 border-amber-500/40",
  NO_ANALIZABLE: "bg-slate-500/15 text-slate-300 border-slate-500/40",
};
