"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import ComplianceView from "@/components/rq/monitor/ComplianceView";
import { AgentChip, Avatar, Stat, StatusDot, Tabs, fmtTokens, fmtUsd } from "@/components/rq/ui";
import { AGENTS, modelLabel } from "@/lib/rq/agents";
import { buildMonitor } from "@/lib/rq/monitor";
import { useNow, useRq } from "@/lib/rq/store";

type Filter = "todos" | "en_linea";
type MonitorTab = "actividad" | "cumplimiento";

export default function MonitorPage() {
  const { requirements, currentUserId, location, setLocation, profiles } = useRq();
  const now = useNow(true, 2000);
  const [filter, setFilter] = useState<Filter>("todos");
  const [tab, setTab] = useState<MonitorTab>("actividad");

  useEffect(() => setLocation({ page: "monitor" }), [setLocation]);

  const data = useMemo(() => buildMonitor(requirements, currentUserId, location, now), [requirements, currentUserId, location, now]);
  const online = data.users.filter((u) => u.online);
  const workingAgents = data.agents.filter((a) => a.workingNow.length > 0);
  const totalCost = data.agents.reduce((s, a) => s + a.costToday, 0);
  const maxCost = Math.max(...data.agents.map((a) => a.costToday), 1e-9);
  const users = filter === "en_linea" ? online : data.users;

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="font-serif text-[26px] leading-tight text-ink-900">Monitor</h1>
          <p className="mt-1 max-w-2xl text-[13px] text-ink-500">
            Quién usa la aplicación y qué agentes trabajan ahora, y el estado de cumplimiento HIPAA de los requerimientos. Se actualiza solo.
          </p>
        </div>
        <span className="chip border-warn/30 bg-warn-soft text-warn">otros usuarios simulados · tus ejecuciones son reales en esta sesión</span>
      </div>

      <Tabs<MonitorTab>
        value={tab}
        onChange={setTab}
        tabs={[
          { id: "actividad", label: "Actividad" },
          { id: "cumplimiento", label: "Cumplimiento HIPAA" },
        ]}
      />

      {tab === "cumplimiento" ? (
        <ComplianceView />
      ) : (
        <div className="space-y-5">

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label="Usuarios en línea" value={`${online.length}/${data.users.length}`} />
        <Stat label="Agentes trabajando" value={workingAgents.reduce((s, a) => s + a.workingNow.length, 0)} hint={`${workingAgents.length} tipos de agente distintos`} />
        <Stat label="Llamadas LLM hoy" value={data.agents.reduce((s, a) => s + a.callsToday, 0).toLocaleString("es-ES")} />
        <Stat label="Coste LLM hoy" value={fmtUsd(totalCost)} hint={`${fmtTokens(data.agents.reduce((s, a) => s + a.tokensToday, 0))} tokens`} />
      </div>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1.25fr)_minmax(0,1fr)]">
        <section className="panel">
          <div className="panel-title">
            <span>Usuarios</span>
            <span className="flex gap-1 normal-case tracking-normal">
              {(["todos", "en_linea"] as Filter[]).map((f) => (
                <button key={f} onClick={() => setFilter(f)} className={`pill ${filter === f ? "pill-active" : "pill-idle"}`}>
                  {f === "todos" ? "todos" : "en línea"}
                </button>
              ))}
            </span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[640px] text-left text-[12.5px]">
              <thead className="bg-sunken text-[11px] uppercase tracking-[0.06em] text-ink-500">
                <tr>
                  <th className="px-4 py-1.5 font-semibold">Usuario</th>
                  <th className="px-4 py-1.5 font-semibold">Dónde está</th>
                  <th className="px-4 py-1.5 font-semibold">Agentes en uso ahora</th>
                  <th className="px-4 py-1.5 text-right font-semibold">Ejecuciones hoy</th>
                  <th className="px-4 py-1.5 text-right font-semibold">Coste hoy</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {users.map((u) => (
                  <tr key={u.user.id} className={u.isYou ? "bg-accent-soft/40" : ""}>
                    <td className="px-4 py-2.5">
                      <span className="flex items-center gap-2.5">
                        <Avatar user={u.user} online={u.online} />
                        <span>
                          <span className="block font-medium text-ink-900">
                            {u.user.name}
                            {u.isYou && <span className="ml-1 text-[11px] font-normal text-accent">(tú)</span>}
                          </span>
                          <span className="text-[11.5px] text-ink-500">{u.online ? u.user.role : `${u.user.role} · hace ${u.lastSeenMin} min`}</span>
                        </span>
                      </span>
                    </td>
                    <td className="px-4 py-2.5 text-ink-700">
                      {u.requirementId && u.online ? (
                        <Link href={`/requerimiento?id=${u.requirementId}`} className="hover:underline">
                          {u.where}
                        </Link>
                      ) : (
                        u.where
                      )}
                    </td>
                    <td className="px-4 py-2.5">
                      <span className="flex flex-wrap gap-1">
                        {u.workingAgents.length ? u.workingAgents.map((a) => <AgentChip key={a} id={a} />) : <span className="text-ink-300">—</span>}
                      </span>
                    </td>
                    <td className="px-4 py-2.5 text-right font-mono text-ink-700">{u.runsToday}</td>
                    <td className="px-4 py-2.5 text-right font-mono text-ink-700">{fmtUsd(u.costToday)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <section className="panel">
          <div className="panel-title">
            <span>Actividad reciente</span>
          </div>
          <ol className="divide-y divide-line">
            {data.feed.map((f, i) => (
              <li key={`${f.at}-${i}`} className="flex items-start gap-2.5 px-4 py-2">
                <Avatar user={f.user} size={24} />
                <span className="min-w-0 flex-1 text-[12.5px] leading-5 text-ink-700">
                  <span className="font-medium text-ink-900">{f.user.name}</span> {f.text}
                </span>
                <span className="shrink-0 font-mono text-[10.5px] text-ink-400">
                  {new Date(f.at).toLocaleTimeString("es-ES", { hour: "2-digit", minute: "2-digit" })}
                </span>
              </li>
            ))}
          </ol>
        </section>
      </div>

      <section className="panel">
        <div className="panel-title">
          <span>Agentes en uso</span>
          <span className="font-mono normal-case tracking-normal text-ink-400">hoy · {fmtUsd(totalCost)}</span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[820px] text-left text-[12.5px]">
            <thead className="bg-sunken text-[11px] uppercase tracking-[0.06em] text-ink-500">
              <tr>
                <th className="px-4 py-1.5 font-semibold">Agente</th>
                <th className="px-4 py-1.5 font-semibold">Trabajando ahora</th>
                <th className="px-4 py-1.5 text-right font-semibold">Llamadas</th>
                <th className="px-4 py-1.5 text-right font-semibold">Tokens</th>
                <th className="px-4 py-1.5 text-right font-semibold">Guardarraíles</th>
                <th className="w-[220px] px-4 py-1.5 font-semibold">Coste hoy</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {data.agents.map((a) => {
                const p = profiles[a.agentId];
                return (
                  <tr key={a.agentId}>
                    <td className="px-4 py-2.5">
                      <span className="flex items-center gap-2.5">
                        <span className="h-7 w-1.5 rounded-full" style={{ background: AGENTS[a.agentId].color }} />
                        <span>
                          <span className="block font-medium text-ink-900">{AGENTS[a.agentId].label}</span>
                          <span className="font-mono text-[11px] text-ink-500">{modelLabel(p.provider, p.model)}</span>
                        </span>
                      </span>
                    </td>
                    <td className="px-4 py-2.5">
                      {a.workingNow.length ? (
                        <span className="flex flex-wrap items-center gap-1.5">
                          <StatusDot status="trabajando" />
                          {a.workingNow.map((w, i) => (
                            <span key={i} className="chip chip-neutral">
                              {w.userName.split(" ")[0]} · {w.requirementId}
                            </span>
                          ))}
                        </span>
                      ) : (
                        <span className="text-ink-300">inactivo</span>
                      )}
                    </td>
                    <td className="px-4 py-2.5 text-right font-mono text-ink-700">{a.callsToday}</td>
                    <td className="px-4 py-2.5 text-right font-mono text-ink-700">{fmtTokens(a.tokensToday)}</td>
                    <td className="px-4 py-2.5 text-right font-mono text-ink-700">{a.guardrailsToday}</td>
                    <td className="px-4 py-2.5">
                      <span className="flex items-center gap-2" title={`${AGENTS[a.agentId].label}: ${fmtUsd(a.costToday)} hoy`}>
                        <span className="h-2 flex-1 overflow-hidden rounded-full bg-sunken">
                          <span className="block h-full rounded-full bg-accent" style={{ width: `${(a.costToday / maxCost) * 100}%` }} />
                        </span>
                        <span className="w-14 text-right font-mono text-ink-900">{fmtUsd(a.costToday)}</span>
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>
      </div>
      )}
    </div>
  );
}
