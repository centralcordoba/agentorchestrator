import { deliverablesFor } from "./scenarios";
import { completedAgents, runState, visibleEvents, type RunState } from "./simulator";
import type { Deliverables, Requirement, Run, TraceEvent, Verdict } from "./types";

export type RequirementStatus = "borrador" | "planificado" | RunState | "pendiente_firma";

export const REQ_STATUS_LABELS: Record<RequirementStatus, string> = {
  borrador: "Borrador",
  planificado: "Planificado",
  en_curso: "En ejecución",
  completado: "Firmado",
  pendiente_firma: "Pendiente de firma",
  cancelado: "Cancelado",
};

export function latestRun(req: Requirement): Run | undefined {
  return req.runs[req.runs.length - 1];
}

export function requirementStatus(req: Requirement, now: number): RequirementStatus {
  const run = latestRun(req);
  if (run) {
    const state = runState(req, run, now);
    return state === "completado" && !run.signoff ? "pendiente_firma" : state;
  }
  return req.plan ? "planificado" : "borrador";
}

export interface RunView {
  run: Run;
  events: TraceEvent[];
  state: RunState;
  deliverables: Deliverables;
  completed: ReturnType<typeof completedAgents>;
  verdict: Verdict | null;
}

export function runView(req: Requirement, run: Run, now: number): RunView {
  const events = visibleEvents(req, run, now);
  const completed = completedAgents(events);
  const deliverables = deliverablesFor(req, completed);
  const state = runState(req, run, now);
  return { run, events, state, deliverables, completed, verdict: completed.includes("verdict") ? run.signoff?.finalVerdict ?? deliverables.verdict.verdict : null };
}
