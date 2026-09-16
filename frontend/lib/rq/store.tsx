"use client";

// Estado del prototipo sin backend: requerimientos, perfiles de agentes y sesión.
// Se persiste en localStorage (si está disponible) para sobrevivir a recargas.
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { AGENT_ORDER } from "./agents";
import { appendAudit, evaluateChange, snapshot } from "./governance";
import { USERS, applyToProfile, seedGovernance, seedRequirements } from "./mockData";
import { suggestPlan } from "./planner";
import type { AgentId, AgentProfile, Attachment, AuditAction, AuditEntry, ChangeRequest, ChatMessage, PhiClassification, ProfileSnapshot, Requirement, Run, RunSpeed, ScenarioId, Verdict } from "./types";

// v4: asistente de consulta (historial de chat por requerimiento).
const STORAGE_KEY = "rq-prototipo-v4";

interface Persisted {
  requirements: Requirement[];
  profiles: Record<AgentId, AgentProfile>;
  currentUserId: string;
  changeRequests: ChangeRequest[];
  audit: AuditEntry[];
  /** Historial del asistente, una conversación por requerimiento. */
  chats: Record<string, ChatMessage[]>;
}

export interface ViewLocation {
  requirementId?: string;
  tab?: string;
  page: string;
}

interface Store extends Persisted {
  ready: boolean;
  location: ViewLocation;
  setLocation: (l: ViewLocation) => void;
  setCurrentUser: (id: string) => void;
  createRequirement: (input: { title: string; description: string; criteria: string[]; phi: PhiClassification }) => string;
  setPhi: (id: string, phi: PhiClassification) => void;
  updateRequirement: (id: string, patch: Partial<Pick<Requirement, "title" | "description" | "acceptanceCriteria">>) => void;
  addAttachment: (id: string, a: Omit<Attachment, "id" | "addedBy" | "addedAt">) => void;
  removeAttachment: (id: string, attachmentId: string) => void;
  requestPlan: (id: string) => void;
  togglePlanItem: (id: string, agentId: AgentId) => void;
  startRun: (id: string, speed: RunSpeed) => string | null;
  cancelRun: (id: string, runId: string) => void;
  effectiveProfile: (agentId: AgentId, requirementId?: string) => AgentProfile;
  saveProfile: (agentId: AgentId, next: Omit<AgentProfile, "versions" | "promptVersion">, note: string, requirementId?: string) => void;
  clearOverride: (agentId: AgentId, requirementId: string) => void;
  requestChange: (agentId: AgentId, after: Omit<ProfileSnapshot, "promptVersion">, justification: string) => string;
  evaluateChangeRequest: (id: string) => void;
  approveChange: (id: string, comment: string) => void;
  rejectChange: (id: string, comment: string) => void;
  withdrawChange: (id: string) => void;
  signRun: (requirementId: string, runId: string, aiVerdict: Verdict, finalVerdict: Verdict, comment: string) => void;
  askChat: (input: {
    requirementId: string;
    question: string;
    agentScope?: AgentId;
    answer: Pick<ChatMessage, "text" | "citations" | "actions" | "fallback">;
    usage: { tokensIn: number; tokensOut: number; costUsd: number };
    redactedTypes?: string[];
  }) => void;
  clearChat: (requirementId: string) => void;
  resetDemo: () => void;
}

const Ctx = createContext<Store | null>(null);

function initial(): Persisted {
  const g = seedGovernance();
  return { requirements: seedRequirements(), profiles: g.profiles, currentUserId: USERS[0].id, changeRequests: g.changeRequests, audit: g.audit, chats: {} };
}

export function RqProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<Persisted>(initial);
  const [ready, setReady] = useState(false);
  const [location, setLocation] = useState<ViewLocation>({ page: "requerimientos" });

  useEffect(() => {
    try {
      const raw = window.localStorage.getItem(STORAGE_KEY);
      if (raw) setState(JSON.parse(raw) as Persisted);
    } catch {
      /* sin almacenamiento: se usa el estado inicial */
    }
    setReady(true);
  }, []);

  // Solo se guarda tras cargar: así el doble montaje de StrictMode no pisa lo guardado con la semilla.
  useEffect(() => {
    if (!ready) return;
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    } catch {
      /* ignorar */
    }
  }, [state, ready]);

  const mutateReq = useCallback((id: string, fn: (r: Requirement) => Requirement) => {
    setState((s) => ({ ...s, requirements: s.requirements.map((r) => (r.id === id ? fn(r) : r)) }));
  }, []);

  /** Añade una entrada al registro de auditoría encadenado (actor = usuario de la sesión). */
  const audit = useCallback((action: AuditAction, target: string, detail: string) => {
    setState((s) => ({ ...s, audit: appendAudit(s.audit, s.currentUserId, action, target, detail) }));
  }, []);

  const effectiveProfile = useCallback(
    (agentId: AgentId, requirementId?: string) => {
      const req = requirementId ? state.requirements.find((r) => r.id === requirementId) : undefined;
      return req?.profileOverrides[agentId] ?? state.profiles[agentId];
    },
    [state],
  );

  const store = useMemo<Store>(
    () => ({
      ...state,
      ready,
      location,
      setLocation,
      setCurrentUser: (id) => setState((s) => ({ ...s, currentUserId: id })),

      createRequirement: ({ title, description, criteria, phi }) => {
        const nums = state.requirements.map((r) => Number(r.id.replace(/\D/g, ""))).filter(Boolean);
        const id = `REQ-${Math.max(1061, ...nums) + 1}`;
        const text = `${title} ${description}`.toLowerCase();
        const scenario: ScenarioId = /pantalla|formulario|portal|web|interfaz|vista/.test(text) ? "portal" : "pagos";
        const req: Requirement = {
          id,
          title,
          description,
          acceptanceCriteria: criteria,
          owner: state.currentUserId,
          createdAt: new Date().toISOString(),
          scenario,
          phi,
          phiSetBy: state.currentUserId,
          attachments: [],
          plan: null,
          runs: [],
          profileOverrides: {},
        };
        setState((s) => ({ ...s, requirements: [req, ...s.requirements] }));
        audit("requerimiento_creado", id, title);
        audit("clasificacion_phi", id, `Clasificado: ${phi === "si" ? "Sí, puede tocar PHI" : phi === "no" ? "No toca PHI" : "No se sabe"}`);
        return id;
      },

      updateRequirement: (id, patch) => mutateReq(id, (r) => ({ ...r, ...patch })),

      // Cambiar la clasificación re-evalúa el plan: Privacidad se vuelve obligatorio con PHI.
      setPhi: (id, phi) => {
        mutateReq(id, (r) => {
          const next = { ...r, phi, phiSetBy: state.currentUserId };
          return r.plan ? { ...next, plan: { ...suggestPlan(next), overriddenBy: undefined } } : next;
        });
        audit("clasificacion_phi", id, `Clasificado: ${phi === "si" ? "Sí, puede tocar PHI" : phi === "no" ? "No toca PHI" : "No se sabe"}`);
      },

      addAttachment: (id, a) =>
        mutateReq(id, (r) => ({
          ...r,
          attachments: [
            ...r.attachments.filter((x) => !(a.kind !== "sql" && x.kind === a.kind)),
            { ...a, id: `att-${Date.now()}`, addedBy: state.currentUserId, addedAt: new Date().toISOString() },
          ],
        })),

      removeAttachment: (id, attachmentId) =>
        mutateReq(id, (r) => ({ ...r, attachments: r.attachments.filter((x) => x.id !== attachmentId) })),

      requestPlan: (id) => mutateReq(id, (r) => ({ ...r, plan: suggestPlan(r) })),

      togglePlanItem: (id, agentId) =>
        mutateReq(id, (r) =>
          r.plan
            ? {
                ...r,
                plan: {
                  ...r.plan,
                  overriddenBy: state.currentUserId,
                  items: r.plan.items.map((i) => (i.agentId === agentId ? { ...i, enabled: !i.enabled } : i)),
                },
              }
            : r,
        ),

      startRun: (id, speed) => {
        const req = state.requirements.find((r) => r.id === id);
        if (!req?.plan) return null;
        const enabled: AgentId[] = ["orchestrator", ...req.plan.items.filter((i) => i.enabled).map((i) => i.agentId), "verdict"];
        const profiles = Object.fromEntries(
          AGENT_ORDER.map((a) => {
            const p = req.profileOverrides[a] ?? state.profiles[a];
            return [a, { provider: p.provider, model: p.model, promptVersion: p.promptVersion }];
          }),
        ) as Run["profiles"];
        const run: Run = {
          id: `run-${id.replace("REQ-", "")}-${Date.now().toString(36)}`,
          requirementId: id,
          startedBy: state.currentUserId,
          startedAt: Date.now(),
          speed,
          enabledAgents: AGENT_ORDER.filter((a) => enabled.includes(a)),
          profiles,
        };
        mutateReq(id, (r) => ({ ...r, runs: [...r.runs, run] }));
        audit("ejecucion_iniciada", id, `${run.id} · ${run.enabledAgents.length - 2} agentes especialistas`);
        return run.id;
      },

      cancelRun: (id, runId) =>
        mutateReq(id, (r) => ({ ...r, runs: r.runs.map((x) => (x.id === runId ? { ...x, cancelledAt: Date.now() } : x)) })),

      effectiveProfile,

      // Solo para ajustes de un requerimiento (se aplican al momento y quedan auditados).
      // Los cambios de la configuración predeterminada pasan por requestChange + aprobación.
      saveProfile: (agentId, next, note, requirementId) => {
        const author = USERS.find((u) => u.id === state.currentUserId)?.name ?? state.currentUserId;
        const { agentId: _ignored, ...fields } = next;
        if (requirementId) {
          mutateReq(requirementId, (r) => ({
            ...r,
            profileOverrides: { ...r.profileOverrides, [agentId]: applyToProfile(r.profileOverrides[agentId] ?? state.profiles[agentId], fields, author, note) },
          }));
          audit("ajuste_local", requirementId, `${agentId} · ${next.provider}/${next.model}${note ? ` · ${note}` : ""}`);
        } else {
          setState((s) => ({ ...s, profiles: { ...s.profiles, [agentId]: applyToProfile(s.profiles[agentId], fields, author, note) } }));
        }
      },

      requestChange: (agentId, after, justification) => {
        const nums = state.changeRequests.map((c) => Number(c.id.replace(/\D/g, ""))).filter(Boolean);
        const id = `CR-${String(Math.max(0, ...nums) + 1).padStart(3, "0")}`;
        const before = snapshot(state.profiles[agentId]);
        const promptChanged = before.systemPrompt !== after.systemPrompt || before.taskPrompt !== after.taskPrompt;
        const cr: ChangeRequest = {
          id,
          agentId,
          createdBy: state.currentUserId,
          createdAt: new Date().toISOString(),
          justification,
          before,
          after: { ...after, promptVersion: promptChanged ? Math.max(...state.profiles[agentId].versions.map((v) => v.version)) + 1 : before.promptVersion },
          status: "pendiente",
        };
        setState((s) => ({ ...s, changeRequests: [cr, ...s.changeRequests] }));
        audit("cambio_solicitado", id, `${agentId} · ${justification.slice(0, 80)}`);
        return id;
      },

      evaluateChangeRequest: (id) => {
        const cr = state.changeRequests.find((c) => c.id === id);
        if (!cr) return;
        const evaluation = evaluateChange(cr, state.currentUserId);
        setState((s) => ({ ...s, changeRequests: s.changeRequests.map((c) => (c.id === id ? { ...c, evaluation } : c)) }));
        audit("cambio_evaluado", id, `${evaluation.regressions} regresión(es) · ${evaluation.improvements} mejora(s)${evaluation.complianceBlockers.length ? " · bloqueo de cumplimiento" : ""}`);
      },

      approveChange: (id, comment) => {
        const cr = state.changeRequests.find((c) => c.id === id);
        if (!cr || cr.status !== "pendiente") return;
        const author = USERS.find((u) => u.id === cr.createdBy)?.name ?? cr.createdBy;
        const { promptVersion: _v, ...fields } = cr.after;
        setState((s) => ({
          ...s,
          profiles: { ...s.profiles, [cr.agentId]: applyToProfile(s.profiles[cr.agentId], fields, author, `${cr.id} · ${cr.justification.slice(0, 60)}`) },
          changeRequests: s.changeRequests.map((c) => (c.id === id ? { ...c, status: "aprobada", review: { by: s.currentUserId, at: new Date().toISOString(), comment } } : c)),
        }));
        audit("cambio_aprobado", id, `${cr.agentId} actualizado${comment ? ` · ${comment.slice(0, 80)}` : ""}`);
      },

      rejectChange: (id, comment) => {
        setState((s) => ({ ...s, changeRequests: s.changeRequests.map((c) => (c.id === id ? { ...c, status: "rechazada", review: { by: s.currentUserId, at: new Date().toISOString(), comment } } : c)) }));
        audit("cambio_rechazado", id, comment.slice(0, 100));
      },

      withdrawChange: (id) => {
        setState((s) => ({ ...s, changeRequests: s.changeRequests.map((c) => (c.id === id ? { ...c, status: "retirada" } : c)) }));
        audit("cambio_retirado", id, "Retirada por quien la solicitó");
      },

      signRun: (requirementId, runId, aiVerdict, finalVerdict, comment) => {
        const signoff = { by: state.currentUserId, at: new Date().toISOString(), decision: aiVerdict === finalVerdict ? ("confirmado" as const) : ("modificado" as const), aiVerdict, finalVerdict, comment };
        mutateReq(requirementId, (r) => ({ ...r, runs: r.runs.map((x) => (x.id === runId ? { ...x, signoff } : x)) }));
        audit("dictamen_firmado", requirementId, `${runId} · ${signoff.decision === "confirmado" ? `confirma ${finalVerdict}` : `cambia ${aiVerdict} → ${finalVerdict}`}${comment ? ` · ${comment.slice(0, 80)}` : ""}`);
      },

      clearOverride: (agentId, requirementId) =>
        mutateReq(requirementId, (r) => {
          const rest = { ...r.profileOverrides };
          delete rest[agentId];
          return { ...r, profileOverrides: rest };
        }),

      // El asistente solo lee: guarda la conversación y deja constancia en la auditoría (sin el texto de la pregunta).
      askChat: ({ requirementId, question, agentScope, answer, usage, redactedTypes }) => {
        const at = new Date().toISOString();
        const base = Date.now().toString(36);
        const user: ChatMessage = { id: `m-${base}-u`, role: "user", at, author: state.currentUserId, agentScope, text: question };
        const assistant: ChatMessage = { id: `m-${base}-a`, role: "assistant", at, agentScope, ...answer, ...usage, redactedTypes };
        setState((s) => ({ ...s, chats: { ...s.chats, [requirementId]: [...(s.chats[requirementId] ?? []), user, assistant] } }));
        audit(
          "chat_consulta",
          requirementId,
          `${agentScope ? `alcance ${agentScope}` : "alcance requerimiento"} · ${usage.tokensIn + usage.tokensOut} tokens · ${redactedTypes?.length ? `${redactedTypes.length} tipo(s) de PHI redactados` : "sin PHI en el contexto"}${answer.fallback ? " · sin respuesta en los datos" : ""}`,
        );
      },

      clearChat: (requirementId) => setState((s) => ({ ...s, chats: { ...s.chats, [requirementId]: [] } })),

      resetDemo: () => setState(initial()),
    }),
    [state, ready, location, mutateReq, effectiveProfile, audit],
  );

  return <Ctx.Provider value={store}>{children}</Ctx.Provider>;
}

export function useRq(): Store {
  const s = useContext(Ctx);
  if (!s) throw new Error("useRq debe usarse dentro de <RqProvider>");
  return s;
}

/** Reloj que avanza mientras `active` sea true (para animar ejecuciones en curso). */
export function useNow(active = true, intervalMs = 250): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!active) return;
    const t = setInterval(() => setNow(Date.now()), intervalMs);
    return () => clearInterval(t);
  }, [active, intervalMs]);
  return now;
}
