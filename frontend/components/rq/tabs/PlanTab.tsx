"use client";

import { useState } from "react";
import { AGENTS, modelLabel } from "@/lib/rq/agents";
import { USERS } from "@/lib/rq/mockData";
import { planWarnings } from "@/lib/rq/planner";
import { SPEED_LABELS } from "@/lib/rq/simulator";
import { useRq } from "@/lib/rq/store";
import type { AgentId, Requirement, RunSpeed } from "@/lib/rq/types";
import { AgentChip, fmtDate } from "../ui";

interface Props {
  req: Requirement;
  running: boolean;
  onStarted: () => void;
  onConfigure: (a: AgentId) => void;
}

export default function PlanTab({ req, running, onStarted, onConfigure }: Props) {
  const { requestPlan, togglePlanItem, startRun, effectiveProfile } = useRq();
  const [thinking, setThinking] = useState(false);
  const [speed, setSpeed] = useState<RunSpeed>("normal");

  const suggest = () => {
    setThinking(true);
    setTimeout(() => {
      requestPlan(req.id);
      setThinking(false);
    }, 1400);
  };

  if (!req.plan) {
    return (
      <div className="panel flex flex-col items-center gap-3 px-6 py-12 text-center">
        <AgentChip id="orchestrator" />
        <p className="font-serif text-[20px] text-ink-900">El orquestador todavía no ha propuesto un plan</p>
        <p className="max-w-lg text-[13px] leading-5 text-ink-500">
          Leerá la descripción, los criterios y los adjuntos para sugerir qué agentes deben intervenir. Después podrás activar o
          desactivar cualquiera antes de ejecutar.
        </p>
        <button className="btn-primary mt-2" onClick={suggest} disabled={thinking}>
          {thinking ? "Analizando requerimiento…" : "Pedir sugerencia al orquestador"}
        </button>
      </div>
    );
  }

  const plan = req.plan;
  const warnings = planWarnings(req, plan);
  const blocked = warnings.some((w) => w.level === "bloqueo");
  const changed = plan.items.filter((i) => i.enabled !== i.suggested);
  const overrider = USERS.find((u) => u.id === plan.overriddenBy);

  return (
    <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_320px]">
      <section className="panel">
        <div className="panel-title">
          <span>Plan sugerido por el orquestador</span>
          <span className="flex items-center gap-2 normal-case tracking-normal">
            <span className="text-ink-400">{fmtDate(plan.suggestedAt)}</span>
            <button className="btn-ghost" onClick={suggest} disabled={thinking || running}>
              {thinking ? "analizando…" : "volver a sugerir"}
            </button>
          </span>
        </div>
        <ul className="divide-y divide-line">
          <FixedRow id="orchestrator" text="Siempre activo: coordina la ejecución." model={modelLabel(effectiveProfile("orchestrator", req.id).provider, effectiveProfile("orchestrator", req.id).model)} onConfigure={onConfigure} />
          {plan.items.map((item) => {
            const p = effectiveProfile(item.agentId, req.id);
            const overridden = item.enabled !== item.suggested;
            const itemWarnings = warnings.filter((w) => w.agentId === item.agentId);
            return (
              <li key={item.agentId} className={`flex gap-3 px-4 py-3 ${item.enabled ? "" : "bg-sunken/40"}`}>
                <button
                  role="switch"
                  aria-checked={item.enabled}
                  aria-label={`${item.enabled ? "Desactivar" : "Activar"} ${AGENTS[item.agentId].label}`}
                  disabled={running}
                  onClick={() => togglePlanItem(req.id, item.agentId)}
                  className={`relative mt-0.5 h-5 w-9 shrink-0 rounded-full transition disabled:opacity-50 ${item.enabled ? "bg-accent" : "bg-line-strong"}`}
                >
                  <span className={`absolute top-0.5 h-4 w-4 rounded-full bg-white shadow transition-all ${item.enabled ? "left-[18px]" : "left-0.5"}`} />
                </button>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <AgentChip id={item.agentId} dim={!item.enabled} />
                    <span className={`chip ${item.suggested ? "border-ok/30 bg-ok-soft text-ok" : "chip-neutral text-ink-500"}`}>
                      {item.suggested ? "sugerido" : "no sugerido"}
                    </span>
                    {overridden && <span className="chip border-accent/30 bg-accent-soft text-accent">cambio manual</span>}
                    <button onClick={() => onConfigure(item.agentId)} className="ml-auto font-mono text-[11px] text-ink-500 underline decoration-line-strong underline-offset-2 hover:text-ink-900">
                      {modelLabel(p.provider, p.model)} · prompt v{p.promptVersion}
                      {req.profileOverrides[item.agentId] ? " · ajustado" : ""}
                    </button>
                  </div>
                  <p className="mt-1 text-[13px] leading-5 text-ink-700">{item.reason}</p>
                  <p className="text-[12px] leading-5 text-ink-400">{AGENTS[item.agentId].role}</p>
                  {itemWarnings.map((w, i) => (
                    <p key={i} className={`mt-1 text-[12px] leading-5 ${w.level === "bloqueo" ? "text-danger" : "text-warn"}`}>
                      {w.level === "bloqueo" ? "⛔ " : "⚠ "}
                      {w.text}
                    </p>
                  ))}
                </div>
              </li>
            );
          })}
          <FixedRow id="verdict" text="Siempre activo: consolida y emite el dictamen." model={modelLabel(effectiveProfile("verdict", req.id).provider, effectiveProfile("verdict", req.id).model)} onConfigure={onConfigure} />
        </ul>
      </section>

      <aside className="space-y-4">
        <div className="panel space-y-3 p-4">
          <div className="text-[11px] font-semibold uppercase tracking-[0.08em] text-ink-500">Ejecutar</div>
          <p className="text-[13px] leading-5 text-ink-700">
            {plan.items.filter((i) => i.enabled).length} agentes especialistas activos
            {changed.length > 0 && (
              <>
                {" "}· {changed.length} cambio(s) respecto a la sugerencia{overrider ? ` (${overrider.name})` : ""}
              </>
            )}
            .
          </p>
          <label className="block">
            <span className="text-[12px] text-ink-500">Ritmo de la simulación</span>
            <select value={speed} onChange={(e) => setSpeed(e.target.value as RunSpeed)} className="mt-1 w-full rounded-lg border border-line bg-surface px-2 py-1.5 text-[13px] outline-none focus:border-accent">
              {(Object.keys(SPEED_LABELS) as RunSpeed[]).map((s) => (
                <option key={s} value={s}>
                  {SPEED_LABELS[s]}
                </option>
              ))}
            </select>
          </label>
          <button
            className="btn-primary w-full"
            disabled={blocked || running}
            onClick={() => {
              if (startRun(req.id, speed)) onStarted();
            }}
          >
            {running ? "Hay una ejecución en curso" : "Ejecutar revisión"}
          </button>
          {blocked && <p className="text-[12px] leading-5 text-danger">Resuelve los bloqueos (adjuntos faltantes) o desactiva esos agentes.</p>}
        </div>
        <div className="panel space-y-2 p-4 text-[12.5px] leading-5 text-ink-500">
          <div className="text-[11px] font-semibold uppercase tracking-[0.08em] text-ink-500">Cómo se ejecuta</div>
          <p>1. Código revisa el diff y genera el mapa del cambio.</p>
          <p>2. Tests, Kiuwan, SQL y UI/UX trabajan en paralelo con ese mapa.</p>
          <p>3. VTR redacta el documento con lo que produjeron los demás.</p>
          <p>4. Dictamen consolida y aplica los umbrales.</p>
        </div>
      </aside>
    </div>
  );
}

function FixedRow({ id, text, model, onConfigure }: { id: AgentId; text: string; model: string; onConfigure: (a: AgentId) => void }) {
  return (
    <li className="flex gap-3 px-4 py-3">
      <span className="relative mt-0.5 h-5 w-9 shrink-0 rounded-full bg-ink-700 opacity-60" aria-hidden>
        <span className="absolute left-[18px] top-0.5 h-4 w-4 rounded-full bg-white" />
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <AgentChip id={id} />
          <span className="chip chip-neutral text-ink-500">fijo</span>
          <button onClick={() => onConfigure(id)} className="ml-auto font-mono text-[11px] text-ink-500 underline decoration-line-strong underline-offset-2 hover:text-ink-900">
            {model}
          </button>
        </div>
        <p className="mt-1 text-[13px] leading-5 text-ink-700">{text}</p>
      </div>
    </li>
  );
}
