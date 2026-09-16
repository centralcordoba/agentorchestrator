// Datos del panel Monitor. Combina lo que ocurre de verdad en esta sesión (usuario actual y sus
// ejecuciones) con actividad simulada de otros usuarios, estable dentro de cada ventana de 20 s.
import { AGENT_ORDER } from "./agents";
import { runView } from "./derive";
import { USERS } from "./mockData";
import { agentStats } from "./simulator";
import type { ViewLocation } from "./store";
import type { AgentId, AppUser, Requirement } from "./types";

export interface UserActivity {
  user: AppUser;
  online: boolean;
  lastSeenMin: number;
  where: string;
  requirementId?: string;
  workingAgents: AgentId[];
  runsToday: number;
  costToday: number;
  isYou: boolean;
}

export interface AgentUsage {
  agentId: AgentId;
  workingNow: { userName: string; requirementId: string }[];
  callsToday: number;
  tokensToday: number;
  costToday: number;
  guardrailsToday: number;
}

export interface FeedItem {
  at: number;
  user: AppUser;
  text: string;
  agent?: AgentId;
}

const TAB_LABEL: Record<string, string> = {
  requerimiento: "Requerimiento",
  plan: "Plan de agentes",
  ejecucion: "Ejecución",
  codigo: "Código y Tests",
  kiuwan: "Kiuwan",
  sql: "SQL",
  uiux: "UI/UX",
  vtr: "VTR",
  dictamen: "Dictamen",
};

// FNV-1a con mezcla final: claves parecidas ("feed:123", "feed:124") dan valores muy distintos.
function hash(s: string) {
  let h = 2166136261;
  for (let i = 0; i < s.length; i++) h = Math.imul(h ^ s.charCodeAt(i), 16777619);
  h = Math.imul(h ^ (h >>> 16), 2246822507);
  h = Math.imul(h ^ (h >>> 13), 3266489909);
  return (h ^ (h >>> 16)) >>> 0;
}

function describe(loc: ViewLocation): string {
  if (loc.page === "requerimiento" && loc.requirementId) return `${loc.requirementId} · ${TAB_LABEL[loc.tab ?? ""] ?? "detalle"}`;
  if (loc.page === "agentes") return "Configuración de agentes";
  if (loc.page === "monitor") return "Monitor";
  return "Lista de requerimientos";
}

// Uso "base" del día para que el panel no aparezca vacío (llamadas, tokens, coste por agente).
const BASE_AGENT: Record<AgentId, [number, number, number]> = {
  orchestrator: [46, 88_000, 0.04],
  code: [132, 1_420_000, 4.1],
  tests: [118, 980_000, 3.2],
  kiuwan: [61, 310_000, 0.19],
  sql: [34, 150_000, 0.31],
  uiux: [52, 290_000, 0.88],
  privacy: [49, 410_000, 1.64],
  vtr: [58, 520_000, 0.42],
  verdict: [23, 110_000, 0.29],
  chat: [94, 640_000, 1.12],
};

export function buildMonitor(requirements: Requirement[], currentUserId: string, location: ViewLocation, now: number) {
  const bucket = Math.floor(now / 20_000);
  const minuteOfDay = new Date(now).getHours() * 60 + new Date(now).getMinutes();
  const dayStart = new Date(now).setHours(0, 0, 0, 0);
  const reqIds = requirements.map((r) => r.id);
  const tabs = ["plan", "ejecucion", "codigo", "kiuwan", "vtr", "dictamen"];

  const realWorking: { userId: string; requirementId: string; agents: AgentId[] }[] = [];
  const realAgent: Record<AgentId, { calls: number; tokens: number; cost: number; guardrails: number }> = Object.fromEntries(
    AGENT_ORDER.map((a) => [a, { calls: 0, tokens: 0, cost: 0, guardrails: 0 }]),
  ) as never;
  const realUser: Record<string, { runs: number; cost: number }> = {};

  for (const req of requirements) {
    for (const run of req.runs) {
      if (run.startedAt < dayStart) continue;
      const v = runView(req, run, now);
      realUser[run.startedBy] ??= { runs: 0, cost: 0 };
      realUser[run.startedBy].runs += 1;
      const working: AgentId[] = [];
      for (const a of AGENT_ORDER) {
        const s = agentStats(v.events, a, run.enabledAgents.includes(a));
        realAgent[a].calls += s.llmCalls;
        realAgent[a].tokens += s.tokensIn + s.tokensOut;
        realAgent[a].cost += s.costUsd;
        realUser[run.startedBy].cost += s.costUsd;
        realAgent[a].guardrails += v.events.filter((e) => e.agent === a && e.type === "guardrail_applied").length;
        if (v.state === "en_curso" && s.status === "trabajando" && a !== "orchestrator") working.push(a);
      }
      if (v.state === "en_curso") realWorking.push({ userId: run.startedBy, requirementId: req.id, agents: working });
    }
  }

  const users: UserActivity[] = USERS.map((user, i) => {
    const isYou = user.id === currentUserId;
    const real = realWorking.filter((w) => w.userId === user.id);
    const h = hash(`${user.id}:${bucket}`);
    const online = isYou || h % 10 < (i === 4 ? 2 : 8);
    const requirementId = isYou ? location.requirementId : reqIds[(h >>> 3) % reqIds.length];
    const simRunning = !isYou && online && (h >>> 5) % 2 === 0;
    const simAgents: AgentId[] = simRunning ? [AGENT_ORDER[1 + ((h >>> 7) % 7)]] : [];
    if (simRunning && (h >>> 9) % 2 === 0) simAgents.push(AGENT_ORDER[1 + ((h >>> 11) % 7)]);
    return {
      user,
      isYou,
      online,
      lastSeenMin: online ? 0 : 5 + ((h >>> 2) % 55),
      requirementId: isYou ? requirementId : online ? requirementId : undefined,
      where: isYou ? describe(location) : online ? `${requirementId} · ${TAB_LABEL[tabs[(h >>> 4) % tabs.length]]}` : "—",
      workingAgents: Array.from(new Set([...real.flatMap((w) => w.agents), ...simAgents])),
      runsToday: (realUser[user.id]?.runs ?? 0) + (isYou ? 0 : 1 + ((hash(user.id) + Math.floor(minuteOfDay / 90)) % 5)),
      costToday: (realUser[user.id]?.cost ?? 0) + (isYou ? 0 : 0.6 + (hash(user.id) % 300) / 100 + minuteOfDay / 900),
    };
  });

  const agents: AgentUsage[] = AGENT_ORDER.map((a) => {
    const [calls, tokens, cost] = BASE_AGENT[a];
    const growth = minuteOfDay / 600;
    const workingNow = [
      ...realWorking.filter((w) => w.agents.includes(a)).map((w) => ({ userName: USERS.find((u) => u.id === w.userId)?.name ?? w.userId, requirementId: w.requirementId })),
      ...users
        .filter((u) => !u.isYou && u.workingAgents.includes(a) && !realWorking.some((w) => w.userId === u.user.id))
        .map((u) => ({ userName: u.user.name, requirementId: u.requirementId ?? "—" })),
    ];
    return {
      agentId: a,
      workingNow,
      callsToday: Math.round(calls * growth) + realAgent[a].calls,
      tokensToday: Math.round(tokens * growth) + realAgent[a].tokens,
      costToday: cost * growth + realAgent[a].cost,
      guardrailsToday: Math.round((calls * growth) / 9) + realAgent[a].guardrails,
    };
  });

  const verbs: [string, AgentId | undefined][] = [
    ["ejecutó la revisión de", "orchestrator"],
    ["cambió el modelo de Tests en", "tests"],
    ["guardó una nueva versión del prompt de Código en", "code"],
    ["descargó el VTR de", "vtr"],
    ["adjuntó un CSV de Kiuwan a", "kiuwan"],
    ["desactivó UI/UX en el plan de", "uiux"],
    ["revisó el dictamen de", "verdict"],
  ];
  const feed: FeedItem[] = [];
  for (let k = 0; k < 8; k++) {
    const hb = hash(`feed:${bucket - k}`);
    const user = USERS[1 + (hb % (USERS.length - 1))];
    const [verb, agent] = verbs[(hb >>> 4) % verbs.length];
    feed.push({ at: (bucket - k) * 20_000 - ((hb >>> 6) % 15_000), user, text: `${verb} ${reqIds[(hb >>> 8) % reqIds.length]}`, agent });
  }
  for (const req of requirements) {
    for (const run of req.runs) {
      if (run.startedAt < dayStart) continue;
      const user = USERS.find((u) => u.id === run.startedBy) ?? USERS[0];
      feed.push({ at: run.startedAt, user, text: `inició una ejecución de ${req.id} con ${run.enabledAgents.length - 2} agentes`, agent: "orchestrator" });
    }
  }
  feed.sort((a, b) => b.at - a.at);

  return { users, agents, feed: feed.slice(0, 10) };
}
