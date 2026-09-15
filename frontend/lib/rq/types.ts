// Tipos del dominio "revisión de requerimientos". Todo cuelga de un Requerimiento.

export type AgentId = "orchestrator" | "code" | "tests" | "kiuwan" | "sql" | "uiux" | "vtr" | "verdict";

export type ProviderId = "openrouter" | "anthropic" | "mock";

export interface PromptVersion {
  version: number;
  savedAt: string;
  author: string;
  note: string;
  systemPrompt: string;
  taskPrompt: string;
}

export interface AgentProfile {
  agentId: AgentId;
  provider: ProviderId;
  model: string;
  temperature: number;
  maxSteps: number;
  systemPrompt: string;
  taskPrompt: string;
  promptVersion: number;
  versions: PromptVersion[];
}

export type AttachmentKind = "repo" | "vtr_template" | "kiuwan_csv" | "sql";

export interface Attachment {
  id: string;
  kind: AttachmentKind;
  name: string; // repo: URL · archivos: nombre
  detail?: string; // repo: rama · archivos: tamaño / filas
  addedBy: string;
  addedAt: string;
  repo?: RepoInfo; // solo si el repositorio se conectó de verdad (GitHub público)
}

export interface RepoFile {
  path: string;
  status: "added" | "modified" | "removed" | "renamed";
  additions: number;
  deletions: number;
  hasPatch: boolean;
}

export interface RepoInfo {
  provider: "github";
  owner: string;
  name: string;
  fullName: string;
  htmlUrl: string;
  description: string;
  defaultBranch: string;
  branch: string;
  base: string;
  rangeLabel: string;
  compareUrl: string;
  headSha: string;
  aheadBy: number;
  commits: { sha: string; message: string; author: string; date: string; url: string }[];
  files: RepoFile[];
  filesTruncated: boolean;
  languages: Record<string, number>;
  findings: Finding[];
  fetchedAt: string;
}

export interface PlanItem {
  agentId: AgentId;
  suggested: boolean;
  enabled: boolean;
  reason: string;
}

export interface Plan {
  items: PlanItem[];
  suggestedAt: string;
  overriddenBy?: string;
}

export type ScenarioId = "pagos" | "portal";

export interface Requirement {
  id: string;
  title: string;
  description: string;
  acceptanceCriteria: string[];
  owner: string;
  createdAt: string;
  scenario: ScenarioId;
  attachments: Attachment[];
  plan: Plan | null;
  runs: Run[];
  profileOverrides: Partial<Record<AgentId, AgentProfile>>;
}

export type RunSpeed = "rapido" | "normal" | "lento";

export interface Run {
  id: string;
  requirementId: string;
  startedBy: string;
  startedAt: number;
  speed: RunSpeed;
  enabledAgents: AgentId[];
  profiles: Record<AgentId, { provider: ProviderId; model: string; promptVersion: number }>;
  cancelledAt?: number;
}

export type TraceEventType =
  | "run_started"
  | "agent_started"
  | "llm_call"
  | "tool_called"
  | "message_sent"
  | "guardrail_applied"
  | "agent_completed"
  | "agent_skipped"
  | "run_completed";

export interface TraceEvent {
  seq: number;
  offsetMs: number; // desde el inicio de la ejecución (ya escalado por velocidad)
  type: TraceEventType;
  agent: AgentId;
  to?: AgentId;
  title: string;
  detail?: string;
  data?: Record<string, unknown>;
  step?: number;
  tokensIn?: number;
  tokensOut?: number;
  costUsd?: number;
}

export type AgentRunStatus = "pendiente" | "trabajando" | "completado" | "omitido";

// ------------------------------------------------------------------ entregables

export type Severity = "critica" | "alta" | "media" | "baja" | "info";

export interface Finding {
  id: string;
  severity: Severity;
  title: string;
  detail: string;
  source: AgentId;
  file?: string;
  line?: number;
  url?: string;
  suggestion?: string;
}

export interface ChangeMapEntry {
  file: string;
  change: "nuevo" | "modificado" | "eliminado";
  added: number;
  removed: number;
  symbols: string[];
  criteria: number[]; // índices de criterios de aceptación cubiertos
}

export interface CodeReport {
  summary: string;
  stack: string;
  changeMap: ChangeMapEntry[];
  findings: Finding[];
}

export interface GeneratedTest {
  name: string;
  file: string;
  kind: "unitario" | "integracion";
  criterion: number;
  status: "paso" | "fallo";
  durationMs: number;
  code: string;
  failureReason?: string;
}

export interface TestsReport {
  framework: string;
  command: string;
  tests: GeneratedTest[];
  coverage: number;
  findings: Finding[];
}

export interface KiuwanDefect {
  ruleId: string;
  rule: string;
  severity: Severity;
  category: string;
  file: string;
  line: number;
  falsePositive: boolean;
  note: string;
}

export interface KiuwanReport {
  fileName: string;
  rows: number;
  defects: KiuwanDefect[];
  findings: Finding[];
}

export interface SqlReport {
  engine: string;
  scripts: { file: string; statements: number; kind: string }[];
  findings: Finding[];
}

export interface UiScenario {
  name: string;
  browser: string;
  status: "paso" | "fallo";
  durationMs: number;
  steps: string[];
  a11yIssues: number;
  failureReason?: string;
}

export interface UiuxReport {
  baseUrl: string;
  scenarios: UiScenario[];
  findings: Finding[];
}

export interface VtrSection {
  title: string;
  status: "completa" | "parcial" | "vacia";
  content: string;
  sources: AgentId[];
}

export interface VtrReport {
  templateName: string;
  outputName: string;
  sections: VtrSection[];
}

export type Verdict = "APROBADO" | "APROBADO_CON_OBSERVACIONES" | "RECHAZADO";

export interface VerdictReport {
  verdict: Verdict;
  confidence: number;
  rationale: string;
  guardrails: string[];
}

export interface Deliverables {
  realRepo: RepoInfo | null; // si existe, Código y SQL se basan en el diff real
  code: CodeReport;
  tests: TestsReport;
  kiuwan: KiuwanReport;
  sql: SqlReport;
  uiux: UiuxReport;
  vtr: VtrReport;
  verdict: VerdictReport;
}

// ------------------------------------------------------------------ usuarios / monitor

export interface AppUser {
  id: string;
  name: string;
  role: string;
  initials: string;
}
