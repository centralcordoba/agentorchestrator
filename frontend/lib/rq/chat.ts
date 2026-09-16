// Asistente de consulta sobre una revisión ya ejecutada.
// En el prototipo las respuestas se construyen con reglas sobre los datos reales de la ejecución
// (hallazgos, traza, entregables y diff): sin LLM, pero con las mismas exigencias que los agentes:
// citar la evidencia, no inventar y no repetir valores de PHI.
import { AGENTS, modelInfo } from "./agents";
import type { RunView } from "./derive";
import { AGENT_CARDS } from "./governance";
import { IDENTIFIER_LABELS, SAFEGUARD_LABEL, WHERE_LABELS, handlesPhi } from "./privacy";
import { VERDICT_LABELS, consolidatedFindings, sortFindings } from "./scenarios";
import { agentStats } from "./simulator";
import type { AgentId, AgentProfile, ChatAction, ChatCitation, ChatMessage, Finding, Requirement } from "./types";

export interface ChatContext {
  req: Requirement;
  view: RunView | null;
  agentId?: AgentId; // alcance: preguntas dentro del panel de un agente
}

export type ChatAnswer = Pick<ChatMessage, "text" | "citations" | "actions" | "fallback">;

// ------------------------------------------------------------------ preguntas sugeridas

const GENERAL_SUGGESTIONS: Record<string, string[]> = {
  dictamen: ["¿Por qué el dictamen es este?", "¿Qué corrijo primero?", "¿Quién puede firmarlo?"],
  privacidad: ["¿Qué datos de paciente aparecen y dónde?", "¿Qué salvaguardas están en riesgo?"],
  codigo: ["¿Qué cambia este requerimiento?", "¿Qué pruebas fallan y por qué?"],
  kiuwan: ["¿Qué defectos de Kiuwan son reales?"],
  sql: ["¿Qué riesgos hay en el SQL?"],
  uiux: ["¿Qué escenarios de interfaz fallan?"],
  vtr: ["¿Qué secciones del VTR quedaron incompletas?"],
  default: ["Resume esta revisión para el comité", "¿Por qué el dictamen es este?", "¿Qué corrijo primero?", "¿Cuánto costó la ejecución?"],
};

export function suggestionsFor(ctx: ChatContext, tab?: string): string[] {
  if (ctx.agentId) {
    const a = AGENTS[ctx.agentId];
    return [`¿Qué hizo ${a.label} en esta ejecución?`, "¿Por qué marcó esos hallazgos?", "¿Qué no revisó?", "¿Con qué modelo y prompt trabajó?"];
  }
  return GENERAL_SUGGESTIONS[tab ?? "default"] ?? GENERAL_SUGGESTIONS.default;
}

// ------------------------------------------------------------------ utilidades

const has = (q: string, ...words: string[]) => words.some((w) => q.includes(w));

function findingCitation(f: Finding, tabByAgent: Partial<Record<AgentId, string>>): ChatCitation {
  return {
    label: f.file ? `${f.title} · ${f.file}${f.line ? `:${f.line}` : ""}` : f.title,
    tab: tabByAgent[f.source],
    url: f.url,
  };
}

const TAB_BY_AGENT: Partial<Record<AgentId, string>> = {
  code: "codigo",
  tests: "codigo",
  kiuwan: "kiuwan",
  sql: "sql",
  uiux: "uiux",
  privacy: "privacidad",
  vtr: "vtr",
  verdict: "dictamen",
};

function listFindings(findings: Finding[], max = 3): string {
  return findings
    .slice(0, max)
    .map((f, i) => `${i + 1}. [${f.severity}] ${f.title}${f.file ? ` (${f.file}${f.line ? `:${f.line}` : ""})` : ""}${f.suggestion ? ` → ${f.suggestion}` : ""}`)
    .join("\n");
}

const NO_RUN: ChatAnswer = {
  text: "Todavía no hay una ejecución terminada de este requerimiento, así que no tengo datos que consultar. Lanza la revisión desde la pestaña Plan de agentes y vuelve a preguntar.",
  actions: [{ label: "Ir al plan", tab: "plan" }],
  fallback: true,
};

// ------------------------------------------------------------------ respuestas por alcance de agente

function answerAgent(q: string, ctx: ChatContext, agentId: AgentId): ChatAnswer {
  const { view } = ctx;
  const a = AGENTS[agentId];
  const card = AGENT_CARDS[agentId];
  if (!view) return NO_RUN;
  if (!view.run.enabledAgents.includes(agentId)) {
    return {
      text: `${a.label} estaba desactivado en esta ejecución, así que no produjo ningún resultado. Puedes activarlo en el plan y volver a ejecutar.`,
      actions: [{ label: "Ir al plan", tab: "plan" }],
    };
  }
  const stats = agentStats(view.events, agentId, true);
  const events = view.events.filter((e) => e.agent === agentId);
  const d = view.deliverables;
  const own = (agentId === "code" ? d.code.findings : agentId === "tests" ? d.tests.findings : agentId === "kiuwan" ? d.kiuwan.findings : agentId === "sql" ? d.sql.findings : agentId === "uiux" ? d.uiux.findings : agentId === "privacy" ? d.privacy.findings : []) as Finding[];

  // ¿con qué modelo y prompt?
  if (has(q, "modelo", "prompt", "configur", "versión", "version", "temperatura")) {
    const p = view.run.profiles[agentId];
    return {
      text: `En esta ejecución ${a.label} usó ${p.model} (${p.provider}) con el prompt v${p.promptVersion}. Esa configuración queda congelada en la ejecución: si alguien cambia el prompt después, esta revisión sigue mostrando la versión con la que se hizo.`,
      citations: [{ label: `Configuración de ${a.label}`, tab: "ejecucion" }],
      actions: [{ label: "Ver ficha y control de cambios", href: `/agentes?agent=${agentId}` }],
    };
  }

  // ¿qué no revisó?
  if (has(q, "no revis", "limitac", "falt", "no hizo", "no pudo")) {
    const missingDeps = a.dependsOn.filter((dep) => !view.run.enabledAgents.includes(dep));
    return {
      text: [
        `Límites declarados de ${a.label}: ${card.limitations.join(" ")}`,
        `Datos a los que accede: ${card.dataAccess.join(", ")}.`,
        missingDeps.length ? `Además, en esta ejecución trabajó sin ${missingDeps.map((x) => AGENTS[x].label).join(" ni ")}, así que tuvo menos contexto.` : "",
        view.deliverables.realRepo && agentId !== "code" && agentId !== "sql" && agentId !== "privacy"
          ? "En este requerimiento el repositorio es real, pero este agente todavía trabaja con datos de ejemplo."
          : "",
      ]
        .filter(Boolean)
        .join("\n\n"),
      citations: [{ label: `Ficha de ${a.label}`, tab: "ejecucion" }],
      actions: [{ label: "Ver ficha del agente", href: "/gobierno?tab=fichas" }],
    };
  }

  // ¿por qué marcó esos hallazgos?
  if (has(q, "por qué", "porque", "crític", "hallazgo", "marc", "grave")) {
    if (!own.length) return { text: `${a.label} no reportó hallazgos en esta ejecución.`, citations: [{ label: `Resultado de ${a.label}`, tab: TAB_BY_AGENT[agentId] }] };
    const top = sortFindings(own).slice(0, 3);
    return {
      text: `${a.label} reportó ${own.length} hallazgo(s). Los más graves:\n\n${listFindings(top)}\n\nCada uno apunta a un archivo y una línea del cambio; si quieres el detalle completo, abre su pestaña.`,
      citations: top.map((f) => findingCitation(f, TAB_BY_AGENT)),
      actions: TAB_BY_AGENT[agentId] ? [{ label: "Ver entregable completo", tab: TAB_BY_AGENT[agentId] }] : undefined,
    };
  }

  // ¿qué hizo? (respuesta por defecto del alcance de agente)
  const tools = events.filter((e) => e.type === "tool_called").map((e) => e.title);
  const guardrails = events.filter((e) => e.type === "guardrail_applied");
  return {
    text: [
      `${a.label} ${stats.status === "completado" ? "terminó" : `está ${stats.status}`} con ${stats.llmCalls} llamada(s) al modelo y ${stats.tools} uso(s) de herramienta.`,
      tools.length ? `Herramientas: ${Array.from(new Set(tools)).join(", ")}.` : "",
      guardrails.length ? `Guardarraíles aplicados: ${guardrails.map((g) => g.title).join(" · ")}.` : "",
      own.length ? `Resultado: ${own.length} hallazgo(s).` : "",
      `Coste de este agente en la ejecución: ${stats.costUsd.toFixed(4)} USD.`,
    ]
      .filter(Boolean)
      .join("\n"),
    citations: [{ label: "Traza de la ejecución", tab: "ejecucion" }],
    actions: TAB_BY_AGENT[agentId] ? [{ label: "Ver resultado", tab: TAB_BY_AGENT[agentId] }] : undefined,
  };
}

// ------------------------------------------------------------------ respuestas del requerimiento

export function answerQuestion(question: string, ctx: ChatContext): ChatAnswer {
  const q = question.toLowerCase();
  const { req, view } = ctx;
  if (ctx.agentId) return answerAgent(q, ctx, ctx.agentId);
  if (!view || !view.completed.length) return NO_RUN;
  const d = view.deliverables;
  const findings = consolidatedFindings(d, view.completed);

  // dictamen
  if (has(q, "dictamen", "por qué", "porque", "rechaz", "aprob", "veredicto")) {
    const v = d.verdict;
    const blockers = findings.filter((f) => f.severity === "critica" || f.severity === "alta").slice(0, 3);
    return {
      text: [
        `El dictamen de la IA es «${VERDICT_LABELS[v.verdict]}» con ${Math.round(v.confidence * 100)} % de confianza. ${v.rationale}`,
        v.guardrails.length ? `Reglas que se aplicaron:\n${v.guardrails.map((g) => `• ${g}`).join("\n")}` : "",
        blockers.length ? `Lo que más pesa:\n${listFindings(blockers)}` : "",
        view.run.signoff
          ? `Firmado por una persona: quedó como «${VERDICT_LABELS[view.run.signoff.finalVerdict]}».`
          : "Todavía no lo ha firmado nadie, así que no sirve como evidencia para el pase.",
      ]
        .filter(Boolean)
        .join("\n\n"),
      citations: blockers.map((f) => findingCitation(f, TAB_BY_AGENT)),
      actions: [{ label: "Ver dictamen", tab: "dictamen" }],
    };
  }

  // privacidad / PHI
  if (has(q, "phi", "privacidad", "paciente", "hipaa", "salvaguarda", "dato sensible")) {
    if (!view.completed.includes("privacy")) {
      return {
        text: `El agente de Privacidad no se ejecutó en esta revisión${handlesPhi(req) ? ", y el requerimiento sí está clasificado con PHI: por eso el dictamen quedó limitado (regla G5)" : ""}. Actívalo en el plan y vuelve a ejecutar para tener datos.`,
        actions: [{ label: "Ir al plan", tab: "plan" }],
        fallback: true,
      };
    }
    const pr = d.privacy;
    const where = Array.from(new Set(pr.detections.map((x) => WHERE_LABELS[x.where])));
    const types = Array.from(new Set(pr.detections.map((x) => IDENTIFIER_LABELS[x.identifier])));
    const risk = pr.safeguards.filter((s) => s.status === "riesgo");
    return {
      text: [
        `Privacidad detectó ${pr.detections.length} identificador(es) de PHI${where.length ? ` en ${where.join(", ")}` : ""}. Tipos: ${types.join(", ") || "—"}. No muestro los valores.`,
        risk.length ? `Salvaguardas en riesgo:\n${risk.map((s) => `• ${SAFEGUARD_LABEL[s.id]}: ${s.evidence}`).join("\n")}` : "Ninguna salvaguarda quedó marcada en riesgo.",
        pr.minimumNecessary,
      ].join("\n\n"),
      citations: pr.detections.slice(0, 3).map((x) => ({ label: `${IDENTIFIER_LABELS[x.identifier]} · ${x.file}${x.line ? `:${x.line}` : ""}`, tab: "privacidad", url: x.url })),
      actions: [{ label: "Ver privacidad", tab: "privacidad" }],
    };
  }

  // prioridades
  if (has(q, "corrijo", "corregir", "primero", "priorid", "empiezo", "arreglar")) {
    const top = findings.slice(0, 3);
    if (!top.length) return { text: "No hay hallazgos abiertos en esta ejecución.", actions: [{ label: "Ver dictamen", tab: "dictamen" }] };
    return {
      text: `Por gravedad, empezaría por esto:\n\n${listFindings(top)}\n\nDespués quedan ${Math.max(0, findings.length - top.length)} hallazgo(s) de menor severidad.`,
      citations: top.map((f) => findingCitation(f, TAB_BY_AGENT)),
      actions: [{ label: "Ver todos los hallazgos", tab: "dictamen" }],
    };
  }

  // pruebas
  if (has(q, "prueba", "test", "cobertura")) {
    if (!view.completed.includes("tests")) return { text: "El agente de Tests no se ejecutó en esta revisión.", actions: [{ label: "Ir al plan", tab: "plan" }], fallback: true };
    const failed = d.tests.tests.filter((t) => t.status === "fallo");
    return {
      text: [
        `Se generaron ${d.tests.tests.length} pruebas con ${d.tests.framework}; pasan ${d.tests.tests.length - failed.length} y fallan ${failed.length}. Cobertura del cambio: ${d.tests.coverage} %.`,
        failed.length ? `Fallos:\n${failed.map((t) => `• ${t.name}: ${t.failureReason ?? "sin detalle"}`).join("\n")}` : "",
      ]
        .filter(Boolean)
        .join("\n\n"),
      citations: failed.slice(0, 2).map((t) => ({ label: `${t.name} · ${t.file}`, tab: "codigo" })),
      actions: [{ label: "Ver pruebas", tab: "codigo" }],
    };
  }

  // qué cambia / diff
  if (has(q, "qué cambia", "que cambia", "diff", "archivos", "cambio", "repositorio")) {
    const cm = d.code.changeMap;
    const add = cm.reduce((s, c) => s + c.added, 0);
    const del = cm.reduce((s, c) => s + c.removed, 0);
    return {
      text: `${d.code.summary}\n\nEn números: ${cm.length} archivo(s), +${add} −${del} líneas. Stack: ${d.code.stack}.`,
      citations: cm.slice(0, 3).map((c) => ({ label: c.file, tab: "codigo" })),
      actions: [{ label: "Ver mapa del cambio", tab: "codigo" }],
    };
  }

  // kiuwan
  if (has(q, "kiuwan", "defecto", "estático", "estatico")) {
    if (!view.completed.includes("kiuwan")) return { text: "El agente de Kiuwan no se ejecutó en esta revisión.", actions: [{ label: "Ir al plan", tab: "plan" }], fallback: true };
    const fp = d.kiuwan.defects.filter((x) => x.falsePositive);
    const crit = d.kiuwan.defects.filter((x) => x.severity === "critica" && !x.falsePositive);
    return {
      text: `El CSV tenía ${d.kiuwan.rows} filas. Quedan ${d.kiuwan.defects.length} defectos relevantes: ${crit.length} crítico(s) confirmado(s) y ${fp.length} falso(s) positivo(s) descartado(s) con ayuda del agente de Código.`,
      citations: crit.slice(0, 2).map((x) => ({ label: `${x.rule} · ${x.file}:${x.line}`, tab: "kiuwan" })),
      actions: [{ label: "Ver Kiuwan", tab: "kiuwan" }],
    };
  }

  // sql
  if (has(q, "sql", "consulta", "base de datos", "migraci")) {
    if (!view.completed.includes("sql")) return { text: "El agente SQL no se ejecutó en esta revisión.", actions: [{ label: "Ir al plan", tab: "plan" }], fallback: true };
    return {
      text: d.sql.findings.length
        ? `SQL revisó ${d.sql.scripts.length} script(s) y reportó ${d.sql.findings.length} hallazgo(s):\n\n${listFindings(sortFindings(d.sql.findings))}`
        : `SQL revisó ${d.sql.scripts.length} script(s) y no encontró problemas.`,
      citations: sortFindings(d.sql.findings).slice(0, 2).map((f) => findingCitation(f, TAB_BY_AGENT)),
      actions: [{ label: "Ver SQL", tab: "sql" }],
    };
  }

  // ui/ux
  if (has(q, "ui", "ux", "interfaz", "pantalla", "accesib", "playwright")) {
    if (!view.completed.includes("uiux")) return { text: "El agente de UI/UX no se ejecutó en esta revisión.", actions: [{ label: "Ir al plan", tab: "plan" }], fallback: true };
    const failed = d.uiux.scenarios.filter((s) => s.status === "fallo");
    return {
      text: `Se ejecutaron ${d.uiux.scenarios.length} escenarios Playwright; fallan ${failed.length}.${failed.length ? ` ${failed.map((s) => `«${s.name}»: ${s.failureReason ?? ""}`).join(" ")}` : ""}`,
      citations: failed.slice(0, 2).map((s) => ({ label: s.name, tab: "uiux" })),
      actions: [{ label: "Ver UI/UX", tab: "uiux" }],
    };
  }

  // vtr
  if (has(q, "vtr", "documento", "docx", "secci")) {
    if (!view.completed.includes("vtr")) return { text: "El agente VTR no se ejecutó en esta revisión, así que no hay documento generado.", actions: [{ label: "Ir al plan", tab: "plan" }], fallback: true };
    const incomplete = d.vtr.sections.filter((s) => s.status !== "completa");
    return {
      text: `El VTR tiene ${d.vtr.sections.length} secciones; ${d.vtr.sections.length - incomplete.length} están completas.${incomplete.length ? ` Pendientes: ${incomplete.map((s) => s.title).join("; ")}.` : ""}`,
      citations: incomplete.slice(0, 3).map((s) => ({ label: s.title, tab: "vtr" })),
      actions: [{ label: "Ver VTR", tab: "vtr" }],
    };
  }

  // coste
  if (has(q, "cost", "token", "gast", "precio")) {
    const perAgent = view.run.enabledAgents
      .map((a) => ({ a, s: agentStats(view.events, a, true) }))
      .sort((x, y) => y.s.costUsd - x.s.costUsd);
    const total = perAgent.reduce((s, x) => s + x.s.costUsd, 0);
    const tokens = perAgent.reduce((s, x) => s + x.s.tokensIn + x.s.tokensOut, 0);
    return {
      text: `La ejecución costó ${total.toFixed(3)} USD y consumió ${tokens.toLocaleString("es-ES")} tokens. Los agentes que más gastan: ${perAgent
        .slice(0, 3)
        .map((x) => `${AGENTS[x.a].label} (${x.s.costUsd.toFixed(3)} USD)`)
        .join(", ")}.`,
      citations: [{ label: "Consumo por agente", tab: "ejecucion" }],
      actions: [{ label: "Ver ejecución", tab: "ejecucion" }],
    };
  }

  // firma
  if (has(q, "firm", "quién", "quien", "aprueba", "responsable")) {
    if (view.run.signoff) {
      return {
        text: `Ya está firmado: ${VERDICT_LABELS[view.run.signoff.finalVerdict]}${view.run.signoff.decision === "modificado" ? ` (la IA recomendaba ${VERDICT_LABELS[view.run.signoff.aiVerdict].toLowerCase()})` : ""}. Comentario: «${view.run.signoff.comment || "sin comentario"}».`,
        citations: [{ label: "Firma del dictamen", tab: "dictamen" }],
        actions: [{ label: "Ver dictamen", tab: "dictamen" }],
      };
    }
    return {
      text: "Está pendiente de firma. Puede firmarlo alguien con el permiso de firmar dictámenes (QA, Líder técnico o Arquitecta) siempre que no sea quien lanzó la ejecución. Yo no puedo firmar ni aprobar: solo te llevo a la pantalla.",
      actions: [{ label: "Ir al dictamen", tab: "dictamen" }],
    };
  }

  // resumen
  if (has(q, "resum", "comité", "comite", "ejecutiv", "cuenta", "estado")) {
    const crit = findings.filter((f) => f.severity === "critica").length;
    const high = findings.filter((f) => f.severity === "alta").length;
    return {
      text: [
        `**${req.id} · ${req.title}**`,
        `Cambio: ${d.code.changeMap.length} archivo(s). Clasificación: ${req.phi === "no" ? "sin PHI" : req.phi === "si" ? "maneja PHI" : "PHI sin confirmar"}.`,
        `Dictamen de la IA: ${VERDICT_LABELS[d.verdict.verdict]} · ${findings.length} hallazgos consolidados (${crit} críticos, ${high} altos).`,
        view.run.signoff ? `Firmado por una persona: ${VERDICT_LABELS[view.run.signoff.finalVerdict]}.` : "Pendiente de firma humana.",
        `Siguiente paso: ${crit ? "corregir los hallazgos críticos y volver a ejecutar" : high ? "corregir los hallazgos altos antes del pase" : "firmar el dictamen"}.`,
      ].join("\n"),
      citations: [{ label: "Dictamen", tab: "dictamen" }, { label: "Traza de la ejecución", tab: "ejecucion" }],
      actions: [{ label: "Ver dictamen", tab: "dictamen" }],
    };
  }

  return {
    text: "No encuentro eso en los datos de esta ejecución, y prefiero decírtelo antes que suponerlo. Puedo contarte el dictamen y por qué salió así, los hallazgos por prioridad, la privacidad y la PHI detectada, las pruebas, Kiuwan, SQL, UI/UX, el VTR, el coste o el estado de la firma.",
    fallback: true,
  };
}

// ------------------------------------------------------------------ coste simulado

export function estimateUsage(question: string, answer: ChatAnswer, profile: AgentProfile, contextChars: number) {
  const tokensIn = Math.round((question.length + contextChars) / 4) + 400;
  const tokensOut = Math.round(answer.text.length / 4);
  const info = modelInfo(profile.provider, profile.model);
  return { tokensIn, tokensOut, costUsd: (tokensIn * info.inPerM + tokensOut * info.outPerM) / 1_000_000 };
}

/** Tamaño aproximado del contexto que se enviaría al modelo (para estimar tokens y explicarlo en la UI). */
export function contextSize(ctx: ChatContext): number {
  if (!ctx.view) return 0;
  const d = ctx.view.deliverables;
  return JSON.stringify({ findings: consolidatedFindings(d, ctx.view.completed), events: ctx.view.events.length, code: d.code.summary }).length;
}

export type { ChatAction, ChatCitation };
