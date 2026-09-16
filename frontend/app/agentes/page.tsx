"use client";

import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import ProfileEditor from "@/components/rq/ProfileEditor";
import { AGENTS, ALL_AGENTS, PROVIDER_LABELS, modelLabel } from "@/lib/rq/agents";
import { useRq } from "@/lib/rq/store";
import type { AgentId } from "@/lib/rq/types";

export default function AgentsPage() {
  return (
    <Suspense fallback={null}>
      <Agents />
    </Suspense>
  );
}

function Agents() {
  const params = useSearchParams();
  const { profiles, requirements, setLocation, changeRequests } = useRq();
  const initial = ALL_AGENTS.includes((params.get("agent") ?? "") as AgentId) ? (params.get("agent") as AgentId) : "code";
  const [selected, setSelected] = useState<AgentId>(initial);

  useEffect(() => setLocation({ page: "agentes" }), [setLocation]);

  const overrides = (id: AgentId) => requirements.filter((r) => r.profileOverrides[id]).map((r) => r.id);

  return (
    <div className="space-y-5">
      <div>
        <h1 className="font-serif text-[26px] leading-tight text-ink-900">Agentes</h1>
        <p className="mt-1 max-w-2xl text-[13px] text-ink-500">
          Configuración predeterminada de cada agente: proveedor, modelo y prompt versionado. Cada requerimiento puede ajustarla
          para sí mismo desde su panel de agente.
        </p>
      </div>

      <div className="grid gap-5 lg:grid-cols-[320px_minmax(0,1fr)]">
        <ul className="panel divide-y divide-line self-start">
          {ALL_AGENTS.map((id) => {
            const p = profiles[id];
            const a = AGENTS[id];
            const ov = overrides(id);
            return (
              <li key={id}>
                <button
                  onClick={() => setSelected(id)}
                  aria-current={selected === id}
                  className={`flex w-full gap-3 px-4 py-3 text-left transition ${selected === id ? "bg-sunken" : "hover:bg-sunken/60"}`}
                >
                  <span className="mt-0.5 h-9 w-1.5 shrink-0 rounded-full" style={{ background: a.color }} />
                  <span className="min-w-0 flex-1">
                    <span className="flex items-center gap-2">
                      <span className="text-[13.5px] font-semibold text-ink-900">{a.label}</span>
                      {!a.optional && <span className="chip chip-neutral">fijo</span>}
                      <span className="ml-auto font-mono text-[10.5px] text-ink-400">v{p.promptVersion}</span>
                    </span>
                    {changeRequests.some((c) => c.agentId === id && c.status === "pendiente") && (
                      <span className="chip border-warn/30 bg-warn-soft text-warn">solicitud pendiente</span>
                    )}
                    <span className="block truncate font-mono text-[11px] text-ink-500">
                      {PROVIDER_LABELS[p.provider]} · {modelLabel(p.provider, p.model)}
                    </span>
                    {ov.length > 0 && <span className="block text-[11px] text-accent">ajustado en {ov.join(", ")}</span>}
                  </span>
                </button>
              </li>
            );
          })}
        </ul>

        <section className="panel">
          <div className="panel-title">
            <span>{AGENTS[selected].label} · configuración predeterminada</span>
          </div>
          <div className="space-y-4 p-4">
            <p className="text-[13px] leading-5 text-ink-700">{AGENTS[selected].role}</p>
            <ProfileEditor key={selected} agentId={selected} />
          </div>
        </section>
      </div>
    </div>
  );
}
