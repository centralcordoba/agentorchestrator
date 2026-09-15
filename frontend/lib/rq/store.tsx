"use client";

// Estado del prototipo sin backend: requerimientos, perfiles de agentes y sesión.
// Se persiste en localStorage (si está disponible) para sobrevivir a recargas.
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { AGENT_ORDER, defaultProfiles } from "./agents";
import { USERS, seedRequirements } from "./mockData";
import { suggestPlan } from "./planner";
import type { AgentId, AgentProfile, Attachment, Requirement, Run, RunSpeed, ScenarioId } from "./types";

const STORAGE_KEY = "rq-prototipo-v1";

interface Persisted {
  requirements: Requirement[];
  profiles: Record<AgentId, AgentProfile>;
  currentUserId: string;
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
  createRequirement: (input: { title: string; description: string; criteria: string[] }) => string;
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
  resetDemo: () => void;
}

const Ctx = createContext<Store | null>(null);

function initial(): Persisted {
  return { requirements: seedRequirements(), profiles: defaultProfiles(), currentUserId: USERS[0].id };
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

      createRequirement: ({ title, description, criteria }) => {
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
          attachments: [],
          plan: null,
          runs: [],
          profileOverrides: {},
        };
        setState((s) => ({ ...s, requirements: [req, ...s.requirements] }));
        return id;
      },

      updateRequirement: (id, patch) => mutateReq(id, (r) => ({ ...r, ...patch })),

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
        return run.id;
      },

      cancelRun: (id, runId) =>
        mutateReq(id, (r) => ({ ...r, runs: r.runs.map((x) => (x.id === runId ? { ...x, cancelledAt: Date.now() } : x)) })),

      effectiveProfile,

      saveProfile: (agentId, next, note, requirementId) => {
        const author = USERS.find((u) => u.id === state.currentUserId)?.name ?? state.currentUserId;
        const bump = (prev: AgentProfile): AgentProfile => {
          const promptChanged = prev.systemPrompt !== next.systemPrompt || prev.taskPrompt !== next.taskPrompt;
          const version = promptChanged ? Math.max(...prev.versions.map((v) => v.version)) + 1 : prev.promptVersion;
          return {
            ...next,
            promptVersion: version,
            versions: promptChanged
              ? [
                  ...prev.versions,
                  { version, savedAt: new Date().toISOString(), author, note: note || "Sin nota", systemPrompt: next.systemPrompt, taskPrompt: next.taskPrompt },
                ]
              : prev.versions,
          };
        };
        if (requirementId) {
          mutateReq(requirementId, (r) => ({
            ...r,
            profileOverrides: { ...r.profileOverrides, [agentId]: bump(r.profileOverrides[agentId] ?? state.profiles[agentId]) },
          }));
        } else {
          setState((s) => ({ ...s, profiles: { ...s.profiles, [agentId]: bump(s.profiles[agentId]) } }));
        }
      },

      clearOverride: (agentId, requirementId) =>
        mutateReq(requirementId, (r) => {
          const rest = { ...r.profileOverrides };
          delete rest[agentId];
          return { ...r, profileOverrides: rest };
        }),

      resetDemo: () => setState(initial()),
    }),
    [state, ready, location, mutateReq, effectiveProfile],
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
