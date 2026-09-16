// Gobierno de IA: roles y permisos, control de cambios de agentes (cuatro ojos + evaluación de regresión),
// fichas de agente, firma del dictamen y registro de auditoría encadenado por hash.
import { AGENTS, MODEL_CATALOG, PROVIDER_BAA, modelInfo } from "./agents";
import type {
  AgentId,
  AgentProfile,
  AppUser,
  AuditAction,
  AuditEntry,
  ChangeRequest,
  EvalCaseResult,
  EvaluationResult,
  Permission,
  ProfileSnapshot,
} from "./types";

// ------------------------------------------------------------------ roles y permisos

export const PERMISSION_LABELS: Record<Permission, string> = {
  crear_requerimiento: "Crear requerimientos",
  ejecutar: "Ejecutar revisiones",
  solicitar_cambio_agente: "Solicitar cambios de agentes",
  aprobar_cambio_agente: "Aprobar cambios de agentes",
  firmar_dictamen: "Firmar dictámenes",
  ver_auditoria: "Ver auditoría",
};

export const ROLE_PERMISSIONS: Record<string, Permission[]> = {
  Desarrollador: ["crear_requerimiento", "ejecutar", "solicitar_cambio_agente"],
  QA: ["crear_requerimiento", "ejecutar", "solicitar_cambio_agente", "firmar_dictamen", "ver_auditoria"],
  "Líder técnico": ["crear_requerimiento", "ejecutar", "solicitar_cambio_agente", "aprobar_cambio_agente", "firmar_dictamen", "ver_auditoria"],
  "Analista funcional": ["crear_requerimiento"],
  Arquitecta: ["ejecutar", "solicitar_cambio_agente", "aprobar_cambio_agente", "firmar_dictamen", "ver_auditoria"],
};

export function can(user: AppUser | undefined, permission: Permission): boolean {
  return Boolean(user && ROLE_PERMISSIONS[user.role]?.includes(permission));
}

export function rolesWith(permission: Permission): string[] {
  return Object.entries(ROLE_PERMISSIONS)
    .filter(([, perms]) => perms.includes(permission))
    .map(([role]) => role);
}

/** Texto para explicar por qué un botón está deshabilitado. */
export function missingPermissionText(permission: Permission): string {
  return `Requiere el permiso «${PERMISSION_LABELS[permission]}» (${rolesWith(permission).join(", ")}).`;
}

// ------------------------------------------------------------------ fichas de agente

export interface AgentCard {
  owner: string; // id de usuario responsable
  dataAccess: string[];
  receivesPhi: "redactada" | "metadatos" | "no";
  limitations: string[];
}

export const AGENT_CARDS: Record<AgentId, AgentCard> = {
  orchestrator: { owner: "u-martin", dataAccess: ["Texto del requerimiento", "Inventario de adjuntos (nombres, no contenido)"], receivesPhi: "metadatos", limitations: ["Solo sugiere el plan; la decisión es del usuario."] },
  code: { owner: "u-martin", dataAccess: ["Diff de la rama", "Archivos del repositorio bajo demanda"], receivesPhi: "redactada", limitations: ["No ejecuta código.", "No relaciona archivos con criterios sin LLM."] },
  tests: { owner: "u-lucia", dataAccess: ["Mapa del cambio", "Código fuente", "Entorno de pruebas local sin red"], receivesPhi: "redactada", limitations: ["Nunca modifica el código del desarrollador.", "Solo usa datos sintéticos."] },
  kiuwan: { owner: "u-lucia", dataAccess: ["CSV de Kiuwan adjunto", "Consultas al agente Código"], receivesPhi: "redactada", limitations: ["No marca falsos positivos sin evidencia de Código."] },
  sql: { owner: "u-valentina", dataAccess: ["Scripts SQL y consultas del diff"], receivesPhi: "redactada", limitations: ["No se conecta a bases de datos reales."] },
  uiux: { owner: "u-lucia", dataAccess: ["Pantallas del entorno de staging", "Capturas enmascaradas"], receivesPhi: "redactada", limitations: ["Solo contra staging con pacientes sintéticos."] },
  privacy: { owner: "u-valentina", dataAccess: ["Diff", "Datos de prueba", "Logs y SQL del cambio"], receivesPhi: "redactada", limitations: ["Nunca devuelve el valor de un identificador.", "Sin LLM, «sin evidencia» no equivale a «cumple»."] },
  vtr: { owner: "u-carla", dataAccess: ["Plantilla VTR", "Resultados de los demás agentes"], receivesPhi: "metadatos", limitations: ["Cada afirmación debe venir de otro agente."] },
  verdict: { owner: "u-martin", dataAccess: ["Hallazgos consolidados (sin valores de PHI)"], receivesPhi: "metadatos", limitations: ["Recomienda; el dictamen lo firma una persona."] },
  chat: { owner: "u-martin", dataAccess: ["Hallazgos, traza y entregables de la ejecución abierta", "Diff del repositorio"], receivesPhi: "redactada", limitations: ["Solo lectura: no firma dictámenes ni aprueba cambios.", "Si el dato no está en la ejecución, lo dice en vez de suponerlo."] },
};

// ------------------------------------------------------------------ control de cambios

export function snapshot(p: AgentProfile): ProfileSnapshot {
  return { provider: p.provider, model: p.model, temperature: p.temperature, maxSteps: p.maxSteps, systemPrompt: p.systemPrompt, taskPrompt: p.taskPrompt, promptVersion: p.promptVersion };
}

export function changedFields(cr: Pick<ChangeRequest, "before" | "after">): string[] {
  const out: string[] = [];
  if (cr.before.provider !== cr.after.provider || cr.before.model !== cr.after.model) out.push("modelo");
  if (cr.before.temperature !== cr.after.temperature) out.push("temperatura");
  if (cr.before.maxSteps !== cr.after.maxSteps) out.push("pasos");
  if (cr.before.systemPrompt !== cr.after.systemPrompt || cr.before.taskPrompt !== cr.after.taskPrompt) out.push("prompt");
  return out;
}

export const EVAL_CASES: { id: string; name: string; expected: string }[] = [
  { id: "E1", name: "Endpoint con PHI sin rol específico", expected: "Hallazgo alto de control de acceso con archivo y línea" },
  { id: "E2", name: "SSN real en un fixture de pruebas", expected: "Hallazgo crítico y dictamen RECHAZADO" },
  { id: "E3", name: "Refactor sin cambios funcionales", expected: "Dictamen APROBADO sin falsos positivos" },
  { id: "E4", name: "Migración con DROP COLUMN sin rollback", expected: "Hallazgo SQL de reversibilidad" },
  { id: "E5", name: "Formulario sin etiquetas accesibles", expected: "Hallazgo UI/UX de accesibilidad" },
  { id: "E6", name: "CSV de Kiuwan con un XSS falso positivo", expected: "Falso positivo identificado y justificado" },
];

/**
 * Evaluación de regresión simulada y determinista: aplica heurísticas explicables al cambio propuesto.
 * En el backend real sería relanzar el agente con la versión candidata sobre este conjunto fijo de casos.
 */
export function evaluateChange(cr: ChangeRequest, runBy: string): EvaluationResult {
  const { before, after } = cr;
  const tempUp = after.temperature - before.temperature >= 0.3;
  const shorter = after.systemPrompt.length < before.systemPrompt.length * 0.7;
  const mentionsPhi = /(phi|paciente|hipaa|salvaguarda|afiliado)/i.test(after.systemPrompt) && !/(phi|paciente|hipaa|salvaguarda|afiliado)/i.test(before.systemPrompt);
  const results: EvalCaseResult[] = EVAL_CASES.map((c) => {
    let candidate: "paso" | "fallo" = "paso";
    let note = "Mismo resultado que la versión actual.";
    if (tempUp && (c.id === "E3" || c.id === "E6")) {
      candidate = "fallo";
      note = "Resultado distinto en 2 de 3 repeticiones: la temperatura introduce variabilidad.";
    }
    if (shorter && (c.id === "E1" || c.id === "E2")) {
      candidate = "fallo";
      note = "El hallazgo aparece sin archivo ni línea: el prompt recortado perdió esa instrucción.";
    }
    if (!tempUp && !shorter && mentionsPhi && c.id === "E1") note = "Mejora: el hallazgo cita la salvaguarda 164.312(a).";
    return { caseId: c.id, baseline: "paso", candidate, note };
  });

  const price = (s: ProfileSnapshot) => {
    const m = modelInfo(s.provider, s.model);
    return m.inPerM * 6 + m.outPerM; // mezcla típica: ~6 tokens de entrada por cada uno de salida
  };
  const pb = price(before);
  const costDeltaPct = pb ? Math.round(((price(after) - pb) / pb) * 100) : 0;
  const tier = (s: ProfileSnapshot) => MODEL_CATALOG[s.provider].findIndex((m) => m.id === s.model);
  const latencyDeltaPct = before.provider === after.provider ? (tier(after) - tier(before)) * 15 : 10;

  const complianceBlockers: string[] = [];
  if (AGENT_CARDS[cr.agentId].receivesPhi === "redactada" && PROVIDER_BAA[after.provider] === false && PROVIDER_BAA[before.provider] !== false) {
    complianceBlockers.push(`${AGENTS[cr.agentId].label} recibe contexto de requerimientos con PHI y el proveedor propuesto no tiene BAA.`);
  }
  return {
    runAt: new Date().toISOString(),
    runBy,
    results,
    regressions: results.filter((r) => r.baseline === "paso" && r.candidate === "fallo").length,
    improvements: mentionsPhi && !tempUp && !shorter ? 1 : 0,
    costDeltaPct,
    latencyDeltaPct,
    complianceBlockers,
  };
}

export interface ReviewGate {
  ok: boolean;
  checks: { label: string; ok: boolean }[];
  commentRequired: boolean;
}

/** Condiciones para aprobar: permiso, cuatro ojos, evaluación hecha, sin bloqueos de cumplimiento. */
export function approvalGate(cr: ChangeRequest, user: AppUser | undefined): ReviewGate {
  const hasPerm = can(user, "aprobar_cambio_agente");
  const notAuthor = Boolean(user && user.id !== cr.createdBy);
  const evaluated = Boolean(cr.evaluation);
  const noBlockers = !cr.evaluation?.complianceBlockers.length;
  const checks = [
    { label: `Tienes permiso para aprobar (${rolesWith("aprobar_cambio_agente").join(", ")})`, ok: hasPerm },
    { label: "No eres quien solicitó el cambio (cuatro ojos)", ok: notAuthor },
    { label: "Se ejecutó la evaluación de regresión", ok: evaluated },
    { label: "Sin bloqueos de cumplimiento (BAA)", ok: evaluated && noBlockers },
  ];
  return { ok: checks.every((c) => c.ok), checks, commentRequired: Boolean(cr.evaluation?.regressions) };
}

// ------------------------------------------------------------------ diff de texto por palabras

export type DiffPart = { kind: "igual" | "quitado" | "agregado"; text: string };

export function wordDiff(a: string, b: string): DiffPart[] {
  const x = a.split(/(\s+)/);
  const y = b.split(/(\s+)/);
  const n = x.length;
  const m = y.length;
  const dp: number[][] = Array.from({ length: n + 1 }, () => new Array(m + 1).fill(0));
  for (let i = n - 1; i >= 0; i--) for (let j = m - 1; j >= 0; j--) dp[i][j] = x[i] === y[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1]);
  const out: DiffPart[] = [];
  const push = (kind: DiffPart["kind"], text: string) => {
    const last = out[out.length - 1];
    if (last && last.kind === kind) last.text += text;
    else out.push({ kind, text });
  };
  let i = 0;
  let j = 0;
  while (i < n && j < m) {
    if (x[i] === y[j]) {
      push("igual", x[i]);
      i++;
      j++;
    } else if (dp[i + 1][j] >= dp[i][j + 1]) push("quitado", x[i++]);
    else push("agregado", y[j++]);
  }
  while (i < n) push("quitado", x[i++]);
  while (j < m) push("agregado", y[j++]);
  return out;
}

// ------------------------------------------------------------------ auditoría encadenada

function fnv(input: string, seed: number): string {
  let h = seed >>> 0;
  for (let i = 0; i < input.length; i++) h = Math.imul(h ^ input.charCodeAt(i), 16777619) >>> 0;
  return h.toString(16).padStart(8, "0");
}

/** Hash simulado (no criptográfico): en el backend sería SHA-256 sobre la entrada y el hash anterior. */
export function entryHash(e: Omit<AuditEntry, "hash">): string {
  const body = `${e.prevHash}|${e.seq}|${e.at}|${e.actor}|${e.action}|${e.target}|${e.detail}`;
  return fnv(body, 2166136261) + fnv(body, 16777619);
}

export function appendAudit(log: AuditEntry[], actor: string, action: AuditAction, target: string, detail: string, at = new Date().toISOString()): AuditEntry[] {
  const prev = log[log.length - 1];
  const base = { seq: (prev?.seq ?? 0) + 1, at, actor, action, target, detail, prevHash: prev?.hash ?? "0".repeat(16) };
  return [...log, { ...base, hash: entryHash(base) }];
}

export function verifyChain(log: AuditEntry[]): { ok: boolean; brokenAt?: number } {
  let prev = "0".repeat(16);
  for (const e of log) {
    if (e.prevHash !== prev || entryHash(e) !== e.hash) return { ok: false, brokenAt: e.seq };
    prev = e.hash;
  }
  return { ok: true };
}

export const AUDIT_LABELS: Record<AuditAction, string> = {
  requerimiento_creado: "Requerimiento creado",
  clasificacion_phi: "Clasificación PHI",
  ejecucion_iniciada: "Ejecución iniciada",
  ajuste_local: "Ajuste de agente en requerimiento",
  cambio_solicitado: "Cambio solicitado",
  cambio_evaluado: "Cambio evaluado",
  cambio_aprobado: "Cambio aprobado",
  cambio_rechazado: "Cambio rechazado",
  cambio_retirado: "Cambio retirado",
  dictamen_firmado: "Dictamen firmado",
  chat_consulta: "Consulta al asistente",
};
