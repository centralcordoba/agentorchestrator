import type { AgentId, AgentProfile, ProviderId } from "./types";

export interface AgentDef {
  id: AgentId;
  label: string;
  short: string;
  role: string;
  color: string;
  soft: string;
  optional: boolean; // el usuario puede desactivarlo
  dependsOn: AgentId[];
  tools: string[];
  outputContract: string;
}

export const AGENT_ORDER: AgentId[] = ["orchestrator", "code", "tests", "kiuwan", "sql", "uiux", "vtr", "verdict"];

export const AGENTS: Record<AgentId, AgentDef> = {
  orchestrator: {
    id: "orchestrator",
    label: "Orquestador",
    short: "ORQ",
    role: "Interpreta el requerimiento, sugiere qué agentes usar y coordina la ejecución.",
    color: "#1F1E1D",
    soft: "#EDEBE5",
    optional: false,
    dependsOn: [],
    tools: ["list_attachments", "detect_file_types", "plan_stages"],
    outputContract: `{
  "items": [{ "agent": AgentId, "suggested": boolean, "reason": string }]
}`,
  },
  code: {
    id: "code",
    label: "Código",
    short: "COD",
    role: "Revisa el diff del repositorio contra el requerimiento y produce el mapa del cambio que usan los demás.",
    color: "#2F6F8F",
    soft: "#E6F0F5",
    optional: true,
    dependsOn: [],
    tools: ["git_diff", "list_files", "read_file", "search_code"],
    outputContract: `{
  "summary": string,
  "change_map": [{ "file", "change", "symbols", "criteria" }],
  "findings": [{ "severity", "title", "file", "line", "detail" }]
}`,
  },
  tests: {
    id: "tests",
    label: "Tests",
    short: "TST",
    role: "Genera pruebas pequeñas a partir del mapa del cambio y los criterios, y las ejecuta en local.",
    color: "#2E7D5B",
    soft: "#E7F2EC",
    optional: true,
    dependsOn: ["code"],
    tools: ["read_change_map", "read_file", "write_test", "run_tests"],
    outputContract: `{
  "tests": [{ "name", "file", "criterion", "status", "failure_reason" }],
  "coverage": number,
  "findings": [...]
}`,
  },
  kiuwan: {
    id: "kiuwan",
    label: "Kiuwan",
    short: "KIU",
    role: "Analiza el CSV de Kiuwan adjunto, prioriza defectos y detecta falsos positivos con ayuda de Código.",
    color: "#A8445C",
    soft: "#F7E8EC",
    optional: true,
    dependsOn: ["code"],
    tools: ["parse_kiuwan_csv", "group_defects", "ask_code_agent"],
    outputContract: `{
  "defects": [{ "rule_id", "severity", "file", "line", "false_positive", "note" }],
  "findings": [...]
}`,
  },
  sql: {
    id: "sql",
    label: "SQL",
    short: "SQL",
    role: "Revisa scripts y consultas: rendimiento, seguridad y reversibilidad.",
    color: "#9A6700",
    soft: "#FBF1DC",
    optional: true,
    dependsOn: ["code"],
    tools: ["parse_sql", "lint_sql", "explain_plan_hint"],
    outputContract: `{
  "scripts": [{ "file", "statements" }],
  "findings": [...]
}`,
  },
  uiux: {
    id: "uiux",
    label: "UI/UX",
    short: "UIX",
    role: "Diseña y ejecuta escenarios Playwright sobre las pantallas afectadas y evalúa usabilidad y accesibilidad.",
    color: "#5B4B8A",
    soft: "#EDEAF5",
    optional: true,
    dependsOn: ["code"],
    tools: ["playwright_run", "axe_scan", "screenshot"],
    outputContract: `{
  "scenarios": [{ "name", "status", "steps", "a11y_issues" }],
  "findings": [...]
}`,
  },
  vtr: {
    id: "vtr",
    label: "VTR",
    short: "VTR",
    role: "Genera el documento VTR (.docx) a partir de la plantilla modelo y de lo producido por los demás agentes.",
    color: "#C2562E",
    soft: "#F7EAE3",
    optional: true,
    dependsOn: ["code", "tests"],
    tools: ["read_vtr_template", "fill_section", "render_docx"],
    outputContract: `{
  "sections": [{ "title", "status", "content", "sources": AgentId[] }]
}`,
  },
  verdict: {
    id: "verdict",
    label: "Dictamen",
    short: "DIC",
    role: "Consolida hallazgos, elimina duplicados, aplica umbrales y emite el dictamen final.",
    color: "#3D3A35",
    soft: "#F4F2EC",
    optional: false,
    dependsOn: [],
    tools: ["dedupe_findings", "count_by_severity", "apply_thresholds"],
    outputContract: `{
  "verdict": "APROBADO" | "APROBADO_CON_OBSERVACIONES" | "RECHAZADO",
  "confidence": number,
  "rationale": string
}`,
  },
};

// Precios USD por millón de tokens (entrada, salida) tomados del catálogo de OpenRouter.
export const MODEL_CATALOG: Record<ProviderId, { id: string; label: string; inPerM: number; outPerM: number }[]> = {
  openrouter: [
    { id: "google/gemini-3.5-flash-lite", label: "Gemini 3.5 Flash Lite", inPerM: 0.3, outPerM: 2.5 },
    { id: "google/gemini-3.5-flash", label: "Gemini 3.5 Flash", inPerM: 1.5, outPerM: 9 },
    { id: "anthropic/claude-sonnet-5", label: "Claude Sonnet 5", inPerM: 2, outPerM: 10 },
    { id: "anthropic/claude-opus-5", label: "Claude Opus 5", inPerM: 5, outPerM: 25 },
    { id: "openai/gpt-5.3-codex", label: "GPT-5.3 Codex", inPerM: 1.75, outPerM: 14 },
    { id: "deepseek/deepseek-v4-flash", label: "DeepSeek V4 Flash", inPerM: 0.084, outPerM: 0.168 },
  ],
  anthropic: [
    { id: "claude-opus-5", label: "Claude Opus 5", inPerM: 5, outPerM: 25 },
    { id: "claude-sonnet-5", label: "Claude Sonnet 5", inPerM: 2, outPerM: 10 },
    { id: "claude-haiku-4-5-20251001", label: "Claude Haiku 4.5", inPerM: 1, outPerM: 5 },
  ],
  mock: [{ id: "mock", label: "Mock (sin coste)", inPerM: 0, outPerM: 0 }],
};

export const PROVIDER_LABELS: Record<ProviderId, string> = {
  openrouter: "OpenRouter",
  anthropic: "Claude API",
  mock: "Mock",
};

export function modelInfo(provider: ProviderId, model: string) {
  return MODEL_CATALOG[provider].find((m) => m.id === model) ?? { id: model, label: model, inPerM: 0, outPerM: 0 };
}

export function modelLabel(provider: ProviderId, model: string): string {
  return modelInfo(provider, model).label;
}

const SYSTEM_PROMPTS: Record<AgentId, string> = {
  orchestrator:
    "Eres el orquestador de un proceso de revisión de requerimientos de software. Lee el requerimiento y el inventario de adjuntos y decide qué agentes especialistas deben intervenir. Justifica cada decisión en una frase. No inventes adjuntos que no existan.",
  code:
    "Eres un revisor de código senior. Revisa únicamente el diff de la rama indicada. Comprueba que el cambio cumple los criterios de aceptación, busca errores de lógica, manejo de errores y convenciones del equipo. Cita siempre archivo y línea.",
  tests:
    "Eres un ingeniero de pruebas. A partir del mapa del cambio y de los criterios de aceptación, escribe pruebas pequeñas y enfocadas (caso feliz, bordes y errores). Nunca modifiques el código del desarrollador: si una prueba falla, decide si es un bug o si la prueba está mal escrita.",
  kiuwan:
    "Eres un analista de calidad y seguridad. Analiza el CSV de Kiuwan adjunto. Prioriza por severidad e impacto, agrupa defectos repetidos y consulta al agente de Código antes de marcar un defecto como falso positivo.",
  sql:
    "Eres un DBA. Revisa los scripts y consultas SQL del cambio. Señala riesgos de rendimiento (índices, planes), seguridad (inyección, permisos) y reversibilidad (scripts de rollback).",
  uiux:
    "Eres un especialista en UI/UX y pruebas end-to-end. Diseña escenarios Playwright para las pantallas afectadas, ejecútalos y evalúa usabilidad, consistencia visual y accesibilidad (WCAG AA).",
  vtr:
    "Eres responsable de documentación. Rellena la plantilla VTR respetando exactamente su estructura. Cada afirmación debe provenir de lo que produjeron los demás agentes; si una sección no tiene fuente, márcala como parcial.",
  verdict:
    "Eres el consolidador. Une los hallazgos de todos los agentes, elimina duplicados, aplica los umbrales de calidad y emite un dictamen con una justificación breve y verificable.",
};

const TASK_PROMPTS: Record<AgentId, string> = {
  orchestrator: "Requerimiento: {{requerimiento}}\nCriterios: {{criterios}}\nAdjuntos: {{adjuntos}}",
  code: "Requerimiento: {{requerimiento}}\nRepositorio: {{repo}} · rama {{rama}}\nCriterios: {{criterios}}",
  tests: "Mapa del cambio: {{mapa_cambio}}\nCriterios: {{criterios}}\nFramework: {{framework}}",
  kiuwan: "CSV: {{kiuwan_csv}}\nMapa del cambio: {{mapa_cambio}}",
  sql: "Scripts: {{scripts_sql}}\nMotor: {{motor}}\nMapa del cambio: {{mapa_cambio}}",
  uiux: "Pantallas afectadas: {{pantallas}}\nURL base: {{url_base}}\nCriterios: {{criterios}}",
  vtr: "Plantilla: {{plantilla_vtr}}\nResultados: {{resultados_agentes}}",
  verdict: "Hallazgos: {{hallazgos}}\nUmbrales: {{umbrales}}",
};

const DEFAULT_MODEL: Record<AgentId, { provider: ProviderId; model: string; temperature: number; maxSteps: number }> = {
  orchestrator: { provider: "openrouter", model: "google/gemini-3.5-flash-lite", temperature: 0.1, maxSteps: 4 },
  code: { provider: "openrouter", model: "anthropic/claude-sonnet-5", temperature: 0.2, maxSteps: 10 },
  tests: { provider: "openrouter", model: "openai/gpt-5.3-codex", temperature: 0.2, maxSteps: 12 },
  kiuwan: { provider: "openrouter", model: "google/gemini-3.5-flash-lite", temperature: 0.1, maxSteps: 6 },
  sql: { provider: "openrouter", model: "google/gemini-3.5-flash", temperature: 0.1, maxSteps: 6 },
  uiux: { provider: "openrouter", model: "google/gemini-3.5-flash", temperature: 0.2, maxSteps: 10 },
  vtr: { provider: "openrouter", model: "google/gemini-3.5-flash-lite", temperature: 0.3, maxSteps: 8 },
  verdict: { provider: "openrouter", model: "anthropic/claude-sonnet-5", temperature: 0.0, maxSteps: 4 },
};

export function defaultProfiles(): Record<AgentId, AgentProfile> {
  const out = {} as Record<AgentId, AgentProfile>;
  for (const id of AGENT_ORDER) {
    const m = DEFAULT_MODEL[id];
    out[id] = {
      agentId: id,
      ...m,
      systemPrompt: SYSTEM_PROMPTS[id],
      taskPrompt: TASK_PROMPTS[id],
      promptVersion: 1,
      versions: [
        {
          version: 1,
          savedAt: "2026-09-01T09:00:00.000Z",
          author: "sistema",
          note: "Versión inicial",
          systemPrompt: SYSTEM_PROMPTS[id],
          taskPrompt: TASK_PROMPTS[id],
        },
      ],
    };
  }
  return out;
}
