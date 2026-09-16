// Tipos del dominio "revisión de requerimientos". Todo cuelga de un Requerimiento.

// "chat" es el asistente de consulta: no participa en el flujo de la revisión, pero se gobierna igual que los demás.
export type AgentId = "orchestrator" | "code" | "tests" | "kiuwan" | "sql" | "uiux" | "privacy" | "vtr" | "verdict" | "chat";

/** ¿El requerimiento puede tocar información de salud protegida (PHI)? "desconocido" se trata como "si". */
export type PhiClassification = "si" | "no" | "desconocido";

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
  phiDetections: PhiDetection[];
  phiSignals: string[]; // rutas o términos del diff que sugieren PHI (fhir, patient, hl7…)
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
  phi: PhiClassification;
  phiSetBy?: string;
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
  signoff?: Signoff; // firma humana del dictamen
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
  | "phi_redacted"
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
  safeguard?: SafeguardId; // salvaguarda técnica HIPAA afectada (solo agente de privacidad)
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


/** Salvaguardas técnicas de la regla de seguridad de HIPAA (45 CFR 164.312). */
export type SafeguardId = "acceso" | "auditoria" | "integridad" | "autenticacion" | "transmision";

/** Tipos de identificador de la lista Safe Harbor (45 CFR 164.514(b)(2)) que detecta el agente. */
export type PhiIdentifier =
  | "nombre"
  | "fecha"
  | "telefono"
  | "email"
  | "ssn"
  | "historia_clinica"
  | "afiliado"
  | "direccion"
  | "documento"
  | "dato_paciente"; // variable con datos de paciente sin valor literal (logs, URL, navegador)

export interface PhiDetection {
  identifier: PhiIdentifier;
  file: string;
  line?: number;
  where: "datos_prueba" | "log" | "sql" | "codigo" | "url" | "almacenamiento_local";
  masked: string; // nunca el valor real
  url?: string;
}

export interface SafeguardCheck {
  id: SafeguardId;
  status: "cumple" | "riesgo" | "sin_evidencia" | "no_aplica";
  evidence: string;
}

export interface PrivacyReport {
  detections: PhiDetection[];
  safeguards: SafeguardCheck[];
  minimumNecessary: string;
  findings: Finding[];
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
  privacy: PrivacyReport;
  verdict: VerdictReport;
}


export interface AppUser {
  id: string;
  name: string;
  role: string;
  initials: string;
  mfa: boolean;
}


export type Permission =
  | "crear_requerimiento"
  | "ejecutar"
  | "solicitar_cambio_agente"
  | "aprobar_cambio_agente"
  | "firmar_dictamen"
  | "ver_auditoria";

/** Configuración de un agente que se somete a control de cambios. */
export interface ProfileSnapshot {
  provider: ProviderId;
  model: string;
  temperature: number;
  maxSteps: number;
  systemPrompt: string;
  taskPrompt: string;
  promptVersion: number;
}

export interface EvalCaseResult {
  caseId: string;
  baseline: "paso" | "fallo";
  candidate: "paso" | "fallo";
  note: string;
}

export interface EvaluationResult {
  runAt: string;
  runBy: string;
  results: EvalCaseResult[];
  regressions: number;
  improvements: number;
  costDeltaPct: number;
  latencyDeltaPct: number;
  complianceBlockers: string[];
}

export type ChangeStatus = "pendiente" | "aprobada" | "rechazada" | "retirada";

export interface ChangeRequest {
  id: string;
  agentId: AgentId;
  createdBy: string;
  createdAt: string;
  justification: string;
  before: ProfileSnapshot;
  after: ProfileSnapshot;
  status: ChangeStatus;
  evaluation?: EvaluationResult;
  review?: { by: string; at: string; comment: string };
}

export interface Signoff {
  by: string;
  at: string;
  decision: "confirmado" | "modificado";
  aiVerdict: Verdict;
  finalVerdict: Verdict;
  comment: string;
}

export type AuditAction =
  | "requerimiento_creado"
  | "clasificacion_phi"
  | "ejecucion_iniciada"
  | "ajuste_local"
  | "cambio_solicitado"
  | "cambio_evaluado"
  | "cambio_aprobado"
  | "cambio_rechazado"
  | "cambio_retirado"
  | "dictamen_firmado"
  | "chat_consulta";

export interface AuditEntry {
  seq: number;
  at: string;
  actor: string;
  action: AuditAction;
  target: string;
  detail: string;
  prevHash: string;
  hash: string;
}


/** Enlace a la evidencia que respalda una respuesta del asistente. */
export interface ChatCitation {
  label: string;
  tab?: string; // pestaña del requerimiento a la que saltar
  url?: string; // enlace externo (GitHub)
}

export interface ChatAction {
  label: string;
  tab?: string;
  href?: string;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  at: string;
  author?: string; // usuario que preguntó
  agentScope?: AgentId; // si la pregunta se hizo desde el panel de un agente
  text: string;
  citations?: ChatCitation[];
  actions?: ChatAction[];
  tokensIn?: number;
  tokensOut?: number;
  costUsd?: number;
  /** Identificadores de PHI que la pasarela redactó del contexto enviado. */
  redactedTypes?: string[];
  fallback?: boolean; // el asistente no supo responder con los datos de la ejecución
}
