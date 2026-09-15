// Sugerencia de plan del orquestador (simulada en el frontend) y avisos antes de ejecutar.
import { AGENTS, AGENT_ORDER } from "./agents";
import { FRONTEND_FILE } from "./github";
import type { AgentId, AttachmentKind, Plan, PlanItem, Requirement } from "./types";

const UI_WORDS = ["pantalla", "formulario", "portal", "web", "interfaz", "botón", "vista", "frontend", "ui"];
const SQL_WORDS = ["base de datos", "tabla", "consulta", "sql", "migración", "reporte", "índice", "procedimiento"];

function has(req: Requirement, kind: AttachmentKind) {
  return req.attachments.some((a) => a.kind === kind);
}

function mentions(req: Requirement, words: string[]): string | null {
  const text = `${req.title} ${req.description} ${req.acceptanceCriteria.join(" ")}`.toLowerCase();
  // \b de JS no entiende tildes: se usa un límite de palabra propio.
  return words.find((w) => new RegExp(`(^|[^a-záéíóúüñ])${w}($|[^a-záéíóúüñ])`).test(text)) ?? null;
}

export const PLANNABLE: AgentId[] = AGENT_ORDER.filter((a) => AGENTS[a].optional);

export function suggestPlan(req: Requirement): Plan {
  const repo = has(req, "repo");
  const real = req.attachments.find((a) => a.kind === "repo")?.repo;
  const realSql = real?.files.filter((f) => /\.sql$/i.test(f.path) && f.status !== "removed") ?? [];
  const realUi = real?.files.filter((f) => FRONTEND_FILE.test(f.path) && f.status !== "removed") ?? [];
  const items: PlanItem[] = PLANNABLE.map((agentId) => {
    switch (agentId) {
      case "code":
        return repo
          ? { agentId, suggested: true, enabled: true, reason: real ? `Repositorio conectado: ${real.files.length} archivos cambiados en ${real.rangeLabel}.` : "Hay un repositorio con rama adjunta: se revisa el diff." }
          : { agentId, suggested: false, enabled: false, reason: "No hay repositorio adjunto." };
      case "tests":
        return repo
          ? { agentId, suggested: true, enabled: true, reason: "Hay código nuevo: se generarán y ejecutarán pruebas locales." }
          : { agentId, suggested: false, enabled: false, reason: "Sin repositorio no hay código que probar." };
      case "kiuwan":
        return has(req, "kiuwan_csv")
          ? { agentId, suggested: true, enabled: true, reason: "Se adjuntó un CSV de Kiuwan." }
          : { agentId, suggested: false, enabled: false, reason: "No se adjuntó el CSV de Kiuwan." };
      case "sql": {
        if (realSql.length) return { agentId, suggested: true, enabled: true, reason: `El diff incluye ${realSql.length} script(s) SQL: ${realSql.slice(0, 2).map((f) => f.path).join(", ")}.` };
        if (has(req, "sql")) return { agentId, suggested: true, enabled: true, reason: "Se adjuntaron scripts SQL." };
        const w = mentions(req, SQL_WORDS);
        return w
          ? { agentId, suggested: true, enabled: true, reason: `El requerimiento menciona «${w}»: probablemente hay consultas.` }
          : { agentId, suggested: false, enabled: false, reason: "No hay scripts SQL ni menciones a base de datos." };
      }
      case "uiux": {
        if (realUi.length) return { agentId, suggested: true, enabled: true, reason: `El diff modifica ${realUi.length} archivo(s) de interfaz: ${realUi.slice(0, 2).map((f) => f.path).join(", ")}.` };
        const w = mentions(req, UI_WORDS);
        if (real && !w) return { agentId, suggested: false, enabled: false, reason: "El diff no toca archivos de interfaz y el requerimiento no menciona pantallas." };
        return w
          ? { agentId, suggested: true, enabled: true, reason: `El requerimiento menciona «${w}»: se probarán las pantallas con Playwright.` }
          : { agentId, suggested: false, enabled: false, reason: "El requerimiento no menciona pantallas." };
      }
      case "vtr":
        return has(req, "vtr_template")
          ? { agentId, suggested: true, enabled: true, reason: "Hay plantilla VTR: se generará el documento." }
          : { agentId, suggested: true, enabled: true, reason: "El VTR es obligatorio. Falta adjuntar la plantilla modelo." };
      default:
        return { agentId, suggested: false, enabled: false, reason: "" };
    }
  });
  return { items, suggestedAt: new Date().toISOString() };
}

export interface PlanWarning {
  agentId: AgentId;
  level: "bloqueo" | "aviso";
  text: string;
}

export function planWarnings(req: Requirement, plan: Plan): PlanWarning[] {
  const on = new Set(plan.items.filter((i) => i.enabled).map((i) => i.agentId));
  const out: PlanWarning[] = [];
  const need: Partial<Record<AgentId, AttachmentKind>> = { code: "repo", tests: "repo", kiuwan: "kiuwan_csv", vtr: "vtr_template" };
  for (const id of on) {
    const kind = need[id];
    if (kind && !has(req, kind)) {
      out.push({ agentId: id, level: "bloqueo", text: `${AGENTS[id].label} necesita un adjunto de tipo «${ATTACHMENT_LABELS[kind]}».` });
    }
    for (const dep of AGENTS[id].dependsOn) {
      if (!on.has(dep)) {
        out.push({ agentId: id, level: "aviso", text: `${AGENTS[id].label} funciona mejor con ${AGENTS[dep].label} activo; trabajará con menos contexto.` });
      }
    }
  }
  return out;
}

export const ATTACHMENT_LABELS: Record<AttachmentKind, string> = {
  repo: "Repositorio git",
  vtr_template: "Plantilla VTR",
  kiuwan_csv: "CSV Kiuwan",
  sql: "Script SQL",
};
