"use client";

// Lo obligatorio (Privacidad con PHI) no se puede desactivar, y el backend lo impide aunque
// se fuerce la petición.
import { useEffect, useMemo, useState } from "react";
import { ErrorState } from "@/components/rq/AsyncState";
import { AgentChip, fmtDate } from "@/components/rq/ui";
import { ApiError, api, errorMessage } from "@/lib/api/client";
import type { PlanView, Requirement } from "@/lib/api/types";
import { AGENTS } from "@/lib/rq/agents";
import type { AgentId } from "@/lib/rq/types";

export default function PlanPanel({
  requirement,
  plan,
  onPlanChanged,
  onRunStarted,
}: {
  requirement: Requirement;
  plan: PlanView | undefined;
  onPlanChanged: () => void;
  onRunStarted: (runId: string) => void;
}) {
  const [enabled, setEnabled] = useState<string[]>([]);
  const [busy, setBusy] = useState<"" | "sugerir" | "guardar" | "ejecutar">("");
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    setEnabled(plan?.plan.enabledAgents ?? []);
  }, [plan]);

  const dirty = useMemo(() => {
    const current = new Set(plan?.plan.enabledAgents ?? []);
    return enabled.length !== current.size || enabled.some((a) => !current.has(a));
  }, [enabled, plan]);

  const blocking = (plan?.warnings ?? []).filter((w) => w.blocks);
  const advisory = (plan?.warnings ?? []).filter((w) => !w.blocks);

  async function act(kind: "sugerir" | "guardar" | "ejecutar", assisted = false) {
    if (busy) return;
    setBusy(kind);
    setError(null);
    try {
      if (kind === "sugerir") {
        await api.requirements.suggestPlan(requirement.id, { assisted });
        onPlanChanged();
      } else if (kind === "guardar") {
        await api.requirements.updatePlan(requirement.id, {
          enabledAgents: enabled as never[],
        });
        onPlanChanged();
      } else {
        const run = await api.requirements.startRun(requirement.id, {
        });
        onRunStarted(run.id);
      }
    } catch (cause) {
      setError(cause);
    } finally {
      setBusy("");
    }
  }

  if (!plan) {
    return (
      <div className="panel flex flex-col items-center gap-3 px-6 py-12 text-center">
        <AgentChip id="orchestrator" />
        <p className="font-serif text-[20px] text-ink-900">
          El orquestador todavía no ha propuesto un plan
        </p>
        <p className="max-w-lg text-[13px] leading-5 text-ink-500">
          Leerá el requerimiento y los adjuntos y propondrá qué agentes intervienen. Tú decides
          cuáles se ejecutan.
        </p>
        {error !== null && <ErrorState error={error} />}
        <div className="flex gap-2">
          <button className="btn-primary" onClick={() => act("sugerir")} disabled={busy !== ""}>
            {busy === "sugerir" ? "Pensando…" : "Pedir plan"}
          </button>
          <button
            className="btn-ghost"
            onClick={() => act("sugerir", true)}
            disabled={busy !== ""}
            title="Además de las reglas, el Orquestador revisa la propuesta con el modelo"
          >
            Pedir plan asistido
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-[12px] text-ink-500">
          Propuesto {fmtDate(plan.plan.suggestedAt)}
          {plan.plan.overriddenBy ? ` · ajustado por ${plan.plan.overriddenBy}` : ""}
        </p>
        <div className="flex gap-2">
          <button className="btn-ghost" onClick={() => act("sugerir")} disabled={busy !== ""}>
            {busy === "sugerir" ? "Pensando…" : "Volver a proponer"}
          </button>
          <button className="btn-ghost" onClick={() => act("sugerir", true)} disabled={busy !== ""}>
            Proponer con el Orquestador
          </button>
        </div>
      </div>

      {error !== null && <ErrorState error={error} onRetry={() => setError(null)} />}

      {blocking.length > 0 && (
        <div className="panel border-danger/30 bg-danger-soft p-3" role="alert">
          <p className="text-[13px] font-medium text-ink-900">
            No se puede ejecutar todavía
          </p>
          <ul className="mt-1 list-disc space-y-0.5 pl-5 text-[13px] text-ink-700">
            {blocking.map((warning) => (
              <li key={warning.text}>{warning.text}</li>
            ))}
          </ul>
        </div>
      )}

      <ul className="grid gap-2 md:grid-cols-2">
        {plan.plan.items.map((item) => {
          const definition = AGENTS[item.agentId as AgentId];
          const on = enabled.includes(item.agentId);
          const locked =
            item.agentId === "privacy" && requirement.handlesPhi
              ? "Obligatorio con PHI"
              : null;
          return (
            <li key={item.agentId} className="panel flex items-start gap-3 p-3">
              <input
                id={`agent-${item.agentId}`}
                type="checkbox"
                className="mt-1 h-4 w-4 accent-[color:var(--accent,#C2562E)]"
                checked={on}
                disabled={locked !== null || busy !== ""}
                onChange={(e) =>
                  setEnabled((current) =>
                    e.target.checked
                      ? [...current, item.agentId]
                      : current.filter((a) => a !== item.agentId),
                  )
                }
              />
              <label htmlFor={`agent-${item.agentId}`} className="min-w-0 flex-1 cursor-pointer">
                <span className="flex flex-wrap items-center gap-2">
                  <span className="text-[13px] font-medium text-ink-900">
                    {definition?.label ?? item.agentId}
                  </span>
                  {item.source === "orquestador" && (
                    <span className="chip chip-neutral" title="Propuesta revisada por el Orquestador">
                      orquestador
                    </span>
                  )}
                  {locked && <span className="chip border-teal/30 bg-teal-soft text-teal">{locked}</span>}
                </span>
                <span className="mt-0.5 block text-[12px] leading-5 text-ink-500">{item.reason}</span>
              </label>
            </li>
          );
        })}
      </ul>

      {advisory.length > 0 && (
        <ul className="space-y-1 text-[12px] text-warn">
          {advisory.map((warning) => (
            <li key={warning.text}>⚠ {warning.text}</li>
          ))}
        </ul>
      )}

      <div className="flex flex-wrap items-center justify-end gap-2">
        {dirty && (
          <button className="btn-ghost" onClick={() => act("guardar")} disabled={busy !== ""}>
            {busy === "guardar" ? "Guardando…" : "Guardar cambios del plan"}
          </button>
        )}
        <button
          className="btn-primary"
          onClick={() => act("ejecutar")}
          disabled={busy !== "" || blocking.length > 0 || dirty}
          title={
            dirty
              ? "Guarda primero los cambios del plan"
              : blocking.length
                ? blocking.map((w) => w.text).join(" · ")
                : undefined
          }
        >
          {busy === "ejecutar" ? "Lanzando…" : "Ejecutar revisión"}
        </button>
      </div>
      {error instanceof ApiError && error.reasons.length > 0 && (
        <p className="text-right text-[12px] text-danger">{errorMessage(error)}</p>
      )}
    </div>
  );
}
