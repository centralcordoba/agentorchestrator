// Simulador de ejecución sin backend. A partir del requerimiento y de la ejecución genera una
// traza determinista (misma ejecución → mismos eventos) con desfases temporales. La UI muestra
// en cada momento los eventos cuyo desfase ya transcurrió, así que sobrevive a recargas.
import { AGENTS, modelInfo } from "./agents";
import { consolidatedFindings, deliverablesFor } from "./scenarios";
import type { AgentId, AgentRunStatus, Requirement, Run, RunSpeed, TraceEvent } from "./types";

export const SPEED_FACTOR: Record<RunSpeed, number> = { rapido: 0.35, normal: 1, lento: 2 };
export const SPEED_LABELS: Record<RunSpeed, string> = { rapido: "Rápido", normal: "Normal", lento: "Lento" };

const PARALLEL: AgentId[] = ["tests", "kiuwan", "sql", "uiux"];

function rng(seed: string) {
  let h = 2166136261;
  for (let i = 0; i < seed.length; i++) h = Math.imul(h ^ seed.charCodeAt(i), 16777619);
  return () => {
    h = Math.imul(h ^ (h >>> 15), 2246822507);
    h = Math.imul(h ^ (h >>> 13), 3266489909);
    return ((h ^= h >>> 16) >>> 0) / 4294967296;
  };
}

type Draft = Omit<TraceEvent, "seq" | "offsetMs">;
interface Step extends Draft {
  gap: number; // ms antes de este evento (sin escalar)
}

class Track {
  t: number;
  events: (Draft & { at: number })[] = [];
  constructor(start: number) {
    this.t = start;
  }
  push(s: Step) {
    const { gap, ...ev } = s;
    this.t += gap;
    this.events.push({ ...ev, at: this.t });
  }
}

const timelineCache = new Map<string, TraceEvent[]>();

export function buildTimeline(req: Requirement, run: Run): TraceEvent[] {
  const realRepo = req.attachments.find((a) => a.kind === "repo")?.repo;
  const key = `${run.id}:${run.enabledAgents.join(",")}:${run.speed}:${realRepo?.headSha ?? ""}`;
  const cached = timelineCache.get(key);
  if (cached) return cached;

  const rand = rng(run.id);
  const jitter = (base: number) => Math.round(base * (0.7 + rand() * 0.6));
  const on = (a: AgentId) => run.enabledAgents.includes(a);
  const d = deliverablesFor(req, run.enabledAgents);
  const all: (Draft & { at: number })[] = [];

  const llm = (agent: AgentId, step: number, title: string, inBase: number, outBase: number, gap = 1400): Step => {
    const p = run.profiles[agent];
    const tokensIn = jitter(inBase);
    const tokensOut = jitter(outBase);
    const info = modelInfo(p.provider, p.model);
    const costUsd = (tokensIn * info.inPerM + tokensOut * info.outPerM) / 1_000_000;
    return { gap: jitter(gap), type: "llm_call", agent, step, title, tokensIn, tokensOut, costUsd, data: { modelo: p.model } };
  };
  const tool = (agent: AgentId, name: string, args: Record<string, unknown>, result: Record<string, unknown>, gap = 700): Step => ({
    gap: jitter(gap),
    type: "tool_called",
    agent,
    title: name,
    data: { argumentos: args, resultado: result },
  });
  const msg = (agent: AgentId, to: AgentId, title: string, detail: string, gap = 500): Step => ({
    gap: jitter(gap),
    type: "message_sent",
    agent,
    to,
    title,
    detail,
  });

  // ------------------------------------------------------------ 1. orquestador
  const orch = new Track(0);
  orch.push({ gap: 0, type: "run_started", agent: "orchestrator", title: `Ejecución iniciada para ${req.id}`, detail: `${run.enabledAgents.length - 2} agentes especialistas activos.` });
  orch.push(tool("orchestrator", "list_attachments", { requerimiento: req.id }, { adjuntos: req.attachments.map((a) => a.name) }));
  orch.push(llm("orchestrator", 1, "Interpreta el requerimiento y confirma el plan", 1800, 260));
  for (const a of ["code", ...PARALLEL, "vtr"] as AgentId[]) {
    if (!on(a)) orch.push({ gap: 120, type: "agent_skipped", agent: a, title: `${AGENTS[a].label} omitido`, detail: "Desactivado en el plan de este requerimiento." });
  }
  all.push(...orch.events);

  // ------------------------------------------------------------ 2. código
  const repo = req.attachments.find((a) => a.kind === "repo");
  const code = new Track(orch.t);
  if (on("code")) {
    code.push(msg("orchestrator", "code", "task_request", `Revisar ${realRepo ? `${realRepo.fullName} (${realRepo.rangeLabel})` : repo?.detail ?? "la rama"} contra ${req.acceptanceCriteria.length} criterios.`));
    code.push({ gap: 300, type: "agent_started", agent: "code", title: "Revisión de código iniciada" });
    const added = d.code.changeMap.reduce((s, c) => s + c.added, 0);
    const removed = d.code.changeMap.reduce((s, c) => s + c.removed, 0);
    code.push(tool("code", "git_diff", realRepo ? { repo: realRepo.fullName, base: realRepo.base.slice(0, 12), rama: realRepo.branch } : { repo: repo?.name, rama: repo?.detail }, { archivos: d.code.changeMap.length, lineas: `+${added} −${removed}`, ...(realRepo ? { commits: realRepo.aheadBy, origen: "api.github.com" } : {}) }, 900));
    code.push(llm("code", 1, "Analiza el diff y decide qué archivos leer", 6400, 420));
    for (const c of d.code.changeMap.slice(0, 2)) {
      code.push(tool("code", "read_file", { ruta: c.file }, { lineas: c.added + 20 }, 600));
    }
    code.push(llm("code", 2, "Contrasta el cambio con los criterios de aceptación", 9800, 700, 1800));
    code.push(
      realRepo
        ? tool("code", "apply_diff_rules", { lineas_añadidas: added }, { hallazgos: realRepo.findings.length }, 600)
        : tool("code", "search_code", { patron: "catch (Exception" }, { coincidencias: 2 }, 600),
    );
    code.push(llm("code", 3, "Redacta hallazgos y mapa del cambio", 11200, 1300, 1900));
    code.push({ gap: 300, type: "guardrail_applied", agent: "code", title: "Validación de citas", detail: "Todos los hallazgos citan archivo y línea existentes en el diff." });
    code.push(msg("code", "orchestrator", "task_result", `Mapa del cambio (${d.code.changeMap.length} archivos) y ${d.code.findings.length} hallazgos.`));
    code.push({ gap: 150, type: "agent_completed", agent: "code", title: `${d.code.findings.length} hallazgos`, data: { stack: d.code.stack } });
    all.push(...code.events);
  }

  // ------------------------------------------------------------ 3. paralelo
  const parStart = code.t;
  let parEnd = parStart;
  const hasCode = on("code");
  const ctxNote = hasCode ? "Recibe el mapa del cambio." : "Sin mapa del cambio: lee el diff directamente.";

  if (on("tests")) {
    const tr = new Track(parStart);
    tr.push(msg("orchestrator", "tests", "task_request", ctxNote, 200));
    tr.push({ gap: 300, type: "agent_started", agent: "tests", title: "Generación de pruebas iniciada" });
    tr.push(tool("tests", "read_change_map", {}, { archivos: d.code.changeMap.length }, 500));
    tr.push(llm("tests", 1, "Diseña casos por criterio de aceptación", 7200, 1600, 1700));
    for (const file of Array.from(new Set(d.tests.tests.map((t) => t.file)))) {
      tr.push(tool("tests", "write_test", { archivo: file }, { pruebas: d.tests.tests.filter((t) => t.file === file).length }, 500));
    }
    const failed = d.tests.tests.filter((t) => t.status === "fallo");
    tr.push(tool("tests", "run_tests", { comando: d.tests.command }, { total: d.tests.tests.length, pasan: d.tests.tests.length - failed.length, fallan: failed.length }, 2200));
    if (failed.length) {
      tr.push(llm("tests", 2, "Analiza fallos: ¿bug del código o prueba mal escrita?", 5400, 500));
      if (hasCode) {
        tr.push(msg("tests", "code", "info_request", `¿El fallo en «${failed[0].name}» coincide con algún hallazgo?`));
        tr.push(msg("code", "tests", "info_response", realRepo ? "No hay un hallazgo del diff que lo explique: se reporta como fallo de prueba." : "Sí: coincide con un hallazgo de severidad alta ya reportado.", 1100));
      }
      tr.push({ gap: 300, type: "guardrail_applied", agent: "tests", title: "No se modifica el código del desarrollador", detail: `${failed.length} prueba(s) fallan por bugs reales: se reportan como hallazgos, no se corrigen.` });
    }
    tr.push({ gap: 300, type: "agent_completed", agent: "tests", title: `${d.tests.tests.length - failed.length}/${d.tests.tests.length} pruebas pasan · cobertura ${d.tests.coverage} %` });
    all.push(...tr.events);
    parEnd = Math.max(parEnd, tr.t);
  }

  if (on("kiuwan")) {
    const kt = new Track(parStart + 150);
    const csv = req.attachments.find((a) => a.kind === "kiuwan_csv");
    kt.push(msg("orchestrator", "kiuwan", "task_request", `Analizar ${csv?.name ?? "CSV"}.`, 200));
    kt.push({ gap: 300, type: "agent_started", agent: "kiuwan", title: "Análisis de Kiuwan iniciado" });
    const bySev = d.kiuwan.defects.reduce<Record<string, number>>((acc, x) => ({ ...acc, [x.severity]: (acc[x.severity] ?? 0) + 1 }), {});
    kt.push(tool("kiuwan", "parse_kiuwan_csv", { archivo: csv?.name }, { filas: d.kiuwan.rows, columnas: ["Rule code", "Priority", "File", "Line", "Characteristic"] }, 600));
    kt.push(tool("kiuwan", "group_defects", { por: "severidad" }, bySev, 400));
    kt.push(llm("kiuwan", 1, "Prioriza defectos y detecta posibles falsos positivos", 5200, 600));
    const fp = d.kiuwan.defects.find((x) => x.falsePositive);
    const crit = d.kiuwan.defects.find((x) => x.severity === "critica");
    if (hasCode && (crit || fp)) {
      const target = crit ?? fp!;
      kt.push(msg("kiuwan", "code", "info_request", `¿Es real «${target.rule}» en ${target.file}:${target.line}?`));
      kt.push(msg("code", "kiuwan", "info_response", target.note, 1300));
    }
    if (crit) kt.push({ gap: 300, type: "guardrail_applied", agent: "kiuwan", title: "Crítico confirmado → bloqueante", detail: `${crit.rule} no puede marcarse como falso positivo sin evidencia.` });
    kt.push(llm("kiuwan", 2, "Redacta el informe de defectos", 3600, 700));
    kt.push({ gap: 200, type: "agent_completed", agent: "kiuwan", title: `${d.kiuwan.rows} filas · ${d.kiuwan.defects.filter((x) => x.falsePositive).length} falso(s) positivo(s)` });
    all.push(...kt.events);
    parEnd = Math.max(parEnd, kt.t);
  }

  if (on("sql")) {
    const st = new Track(parStart + 300);
    st.push(msg("orchestrator", "sql", "task_request", `Revisar SQL (${d.sql.engine}).`, 200));
    st.push({ gap: 300, type: "agent_started", agent: "sql", title: "Revisión SQL iniciada" });
    st.push(tool("sql", "parse_sql", { scripts: d.sql.scripts.map((s) => s.file) }, { sentencias: d.sql.scripts.reduce((s, x) => s + x.statements, 0) }, 700));
    st.push(tool("sql", "lint_sql", { motor: d.sql.engine }, { reglas_disparadas: d.sql.findings.length }, 600));
    st.push(llm("sql", 1, "Evalúa rendimiento, seguridad y reversibilidad", 4200, 650, 1600));
    st.push({ gap: 200, type: "agent_completed", agent: "sql", title: `${d.sql.findings.length} hallazgos SQL` });
    all.push(...st.events);
    parEnd = Math.max(parEnd, st.t);
  }

  if (on("uiux")) {
    const ut = new Track(parStart + 450);
    ut.push(msg("orchestrator", "uiux", "task_request", "Probar pantallas afectadas con Playwright.", 200));
    ut.push({ gap: 300, type: "agent_started", agent: "uiux", title: "Pruebas de interfaz iniciadas" });
    ut.push(llm("uiux", 1, "Diseña escenarios Playwright a partir de los criterios", 5600, 1200, 1600));
    for (const sc of d.uiux.scenarios) {
      ut.push(tool("uiux", "playwright_run", { escenario: sc.name, navegador: sc.browser }, { estado: sc.status, duracion_ms: sc.durationMs }, Math.min(2600, sc.durationMs / 3)));
    }
    ut.push(tool("uiux", "axe_scan", { url: d.uiux.baseUrl }, { incidencias: d.uiux.scenarios.reduce((s, x) => s + x.a11yIssues, 0) }, 900));
    ut.push(llm("uiux", 2, "Evalúa usabilidad y accesibilidad", 4800, 700));
    ut.push({ gap: 200, type: "agent_completed", agent: "uiux", title: `${d.uiux.scenarios.filter((s) => s.status === "paso").length}/${d.uiux.scenarios.length} escenarios pasan` });
    all.push(...ut.events);
    parEnd = Math.max(parEnd, ut.t);
  }

  // ------------------------------------------------------------ 4. VTR
  const vt = new Track(parEnd);
  if (on("vtr")) {
    vt.push(msg("orchestrator", "vtr", "task_request", "Generar VTR con los resultados disponibles.", 300));
    vt.push({ gap: 300, type: "agent_started", agent: "vtr", title: "Generación del VTR iniciada" });
    vt.push(tool("vtr", "read_vtr_template", { plantilla: d.vtr.templateName }, { secciones: d.vtr.sections.length }, 600));
    vt.push(llm("vtr", 1, "Redacta secciones 1–5", 8200, 1800, 1800));
    vt.push(llm("vtr", 2, "Redacta secciones 6–9", 6900, 1500, 1600));
    const partial = d.vtr.sections.filter((s) => s.status !== "completa");
    if (partial.length) vt.push({ gap: 300, type: "guardrail_applied", agent: "vtr", title: "Secciones sin fuente marcadas", detail: partial.map((s) => s.title).join(" · ") });
    vt.push(tool("vtr", "render_docx", { salida: d.vtr.outputName }, { paginas: 7, bytes: 61234 }, 900));
    vt.push({ gap: 200, type: "agent_completed", agent: "vtr", title: `${d.vtr.outputName} generado` });
    all.push(...vt.events);
  }

  // ------------------------------------------------------------ 5. dictamen
  const dt = new Track(vt.t);
  const findings = consolidatedFindings(d, run.enabledAgents);
  dt.push(msg("orchestrator", "verdict", "task_request", "Consolidar hallazgos y emitir dictamen.", 300));
  dt.push({ gap: 300, type: "agent_started", agent: "verdict", title: "Consolidación iniciada" });
  dt.push(tool("verdict", "dedupe_findings", {}, { salida: findings.length }, 500));
  dt.push(llm("verdict", 1, "Redacta la justificación del dictamen", 4600, 500));
  for (const g of d.verdict.guardrails) dt.push({ gap: 250, type: "guardrail_applied", agent: "verdict", title: g.split(" · ")[0], detail: g.split(" · ").slice(1).join(" · ") });
  dt.push(msg("verdict", "orchestrator", "decision", d.verdict.verdict));
  dt.push({ gap: 150, type: "agent_completed", agent: "verdict", title: d.verdict.verdict.replaceAll("_", " ") });
  dt.push({ gap: 200, type: "run_completed", agent: "orchestrator", title: "Ejecución completada", detail: d.verdict.verdict });
  all.push(...dt.events);

  const factor = SPEED_FACTOR[run.speed];
  const events = all
    .sort((a, b) => a.at - b.at)
    .map((e, i) => {
      const { at, ...rest } = e;
      return { ...rest, seq: i + 1, offsetMs: Math.round(at * factor) };
    });
  timelineCache.set(key, events);
  return events;
}

export function visibleEvents(req: Requirement, run: Run, now: number): TraceEvent[] {
  const limit = (run.cancelledAt ?? now) - run.startedAt;
  return buildTimeline(req, run).filter((e) => e.offsetMs <= limit);
}

export function runDurationMs(req: Requirement, run: Run): number {
  const tl = buildTimeline(req, run);
  return tl[tl.length - 1]?.offsetMs ?? 0;
}

export type RunState = "en_curso" | "completado" | "cancelado";

export function runState(req: Requirement, run: Run, now: number): RunState {
  if (run.cancelledAt && run.cancelledAt - run.startedAt < runDurationMs(req, run)) return "cancelado";
  return now - run.startedAt >= runDurationMs(req, run) ? "completado" : "en_curso";
}

export interface AgentStats {
  status: AgentRunStatus;
  llmCalls: number;
  tools: number;
  tokensIn: number;
  tokensOut: number;
  costUsd: number;
  lastTitle: string | null;
  step: number;
}

export function agentStats(events: TraceEvent[], agent: AgentId, enabled: boolean): AgentStats {
  const s: AgentStats = { status: enabled ? "pendiente" : "omitido", llmCalls: 0, tools: 0, tokensIn: 0, tokensOut: 0, costUsd: 0, lastTitle: null, step: 0 };
  for (const e of events) {
    if (e.agent !== agent) continue;
    if (e.type === "agent_started" || e.type === "run_started") s.status = "trabajando";
    if (e.type === "agent_completed") s.status = "completado";
    if (e.type === "agent_skipped") s.status = "omitido";
    if (e.type === "run_completed") s.status = "completado";
    if (e.type === "llm_call") {
      s.llmCalls += 1;
      s.tokensIn += e.tokensIn ?? 0;
      s.tokensOut += e.tokensOut ?? 0;
      s.costUsd += e.costUsd ?? 0;
      s.step = e.step ?? s.step;
    }
    if (e.type === "tool_called") s.tools += 1;
    if (e.type !== "message_sent") s.lastTitle = e.title;
  }
  return s;
}

export function completedAgents(events: TraceEvent[]): AgentId[] {
  return events.filter((e) => e.type === "agent_completed").map((e) => e.agent);
}
