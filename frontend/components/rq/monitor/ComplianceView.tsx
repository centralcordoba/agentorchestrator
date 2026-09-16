"use client";

import Link from "next/link";
import { useMemo } from "react";
import { AGENTS, PROVIDER_LABELS } from "@/lib/rq/agents";
import { buildCompliance, type ComplianceAlert } from "@/lib/rq/compliance";
import { SAFEGUARDS } from "@/lib/rq/privacy";
import { useNow, useRq } from "@/lib/rq/store";
import { PhiBadge } from "../PhiControl";
import { Stat } from "../ui";

const ALERT_STYLE: Record<ComplianceAlert["severity"], { cls: string; label: string; icon: string }> = {
  critica: { cls: "border-l-danger bg-danger-soft/40", label: "Crítica", icon: "⛔" },
  alta: { cls: "border-l-rose bg-rose-soft/40", label: "Alta", icon: "▲" },
  media: { cls: "border-l-warn bg-warn-soft/40", label: "Media", icon: "●" },
  baja: { cls: "border-l-info bg-info-soft/40", label: "Baja", icon: "▽" },
};

const SEG = [
  { key: "riesgo", label: "En riesgo", cls: "bg-danger" },
  { key: "sin_evidencia", label: "Sin evidencia", cls: "bg-warn" },
  { key: "cumple", label: "Cumple", cls: "bg-ok" },
] as const;

export default function ComplianceView() {
  const { requirements, profiles, changeRequests } = useRq();
  const now = useNow(true, 5000);
  const data = useMemo(() => buildCompliance(requirements, profiles, changeRequests, now), [requirements, profiles, changeRequests, now]);

  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
        <Stat label="Requerimientos con PHI" value={`${data.kpis.phiRequirements}/${data.kpis.totalRequirements}`} hint="incluye los no clasificados" />
        <Stat label="Datos redactados hoy" value={data.kpis.redactionsToday} hint="antes de llamar a los modelos" />
        <Stat label="Agentes sin BAA con PHI" value={data.kpis.noBaaAgents} hint="proveedor sin acuerdo firmado" />
        <Stat label="Dictámenes sin firmar" value={data.kpis.unsigned} hint="pendientes de firma humana" />
        <Stat label="Usuarios sin MFA" value={data.kpis.noMfa} hint={`${data.kpis.pendingChanges} cambio(s) de agente pendientes`} />
      </div>

      <section className="panel" aria-labelledby="alerts-title">
        <div className="panel-title">
          <span id="alerts-title">Alertas de cumplimiento</span>
          <span className="normal-case tracking-normal text-ink-400">{data.alerts.length} abiertas · ordenadas por gravedad</span>
        </div>
        {data.alerts.length ? (
          <ul className="divide-y divide-line">
            {data.alerts.map((a) => {
              const st = ALERT_STYLE[a.severity];
              return (
                <li key={a.id} className={`flex flex-wrap items-start gap-3 border-l-4 px-4 py-3 ${st.cls}`}>
                  <span className="mt-0.5 shrink-0 font-mono text-[12px]" aria-hidden>
                    {st.icon}
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block text-[13.5px] font-medium text-ink-900">
                      <span className="sr-only">Severidad {st.label}: </span>
                      {a.title}
                    </span>
                    <span className="block text-[12.5px] leading-5 text-ink-700">{a.detail}</span>
                  </span>
                  {a.href && (
                    <Link href={a.href} className="btn-ghost shrink-0">
                      {a.action ?? "ver"} →
                    </Link>
                  )}
                </li>
              );
            })}
          </ul>
        ) : (
          <p className="px-4 py-8 text-center text-[13px] text-ok">Sin alertas abiertas.</p>
        )}
      </section>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)]">
        <section className="panel" aria-labelledby="phi-req-title">
          <div className="panel-title">
            <span id="phi-req-title">Requerimientos con PHI</span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[560px] text-left text-[12.5px]">
              <thead className="bg-sunken text-[11px] uppercase tracking-[0.06em] text-ink-500">
                <tr>
                  <th scope="col" className="px-4 py-1.5 font-semibold">Requerimiento</th>
                  <th scope="col" className="px-4 py-1.5 font-semibold">Clasificación</th>
                  <th scope="col" className="px-4 py-1.5 font-semibold">Privacidad</th>
                  <th scope="col" className="px-4 py-1.5 text-right font-semibold">Hallazgos</th>
                  <th scope="col" className="px-4 py-1.5 text-right font-semibold">Redacciones</th>
                  <th scope="col" className="px-4 py-1.5 font-semibold">Firma</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {data.rows.map((r) => (
                  <tr key={r.id}>
                    <td className="px-4 py-2">
                      <Link href={`/requerimiento?id=${r.id}&tab=privacidad`} className="font-mono text-[11.5px] text-accent hover:underline">
                        {r.id}
                      </Link>
                      <span className="block max-w-[220px] truncate text-ink-700">{r.title}</span>
                    </td>
                    <td className="px-4 py-2">
                      <PhiBadge phi={r.phi} />
                    </td>
                    <td className="px-4 py-2">
                      {r.privacyRan ? (
                        <span className="chip border-ok/30 bg-ok-soft text-ok">ejecutado</span>
                      ) : (
                        <span className="chip border-warn/30 bg-warn-soft text-warn">sin ejecutar</span>
                      )}
                    </td>
                    <td className="px-4 py-2 text-right font-mono">
                      {r.criticals > 0 && <span className="text-danger">{r.criticals} crít.</span>}
                      {r.criticals > 0 && r.highs > 0 && <span className="text-ink-400"> · </span>}
                      {r.highs > 0 && <span className="text-rose">{r.highs} alta</span>}
                      {!r.criticals && !r.highs && <span className="text-ink-400">—</span>}
                    </td>
                    <td className="px-4 py-2 text-right font-mono text-ink-700">{r.redactions || "—"}</td>
                    <td className="px-4 py-2">
                      {r.signed ? (
                        <span className="chip border-ok/30 bg-ok-soft text-ok">firmado</span>
                      ) : r.verdictPending ? (
                        <span className="chip border-warn/30 bg-warn-soft text-warn">pendiente</span>
                      ) : (
                        <span className="text-ink-400">—</span>
                      )}
                    </td>
                  </tr>
                ))}
                {!data.rows.length && (
                  <tr>
                    <td colSpan={6} className="px-4 py-6 text-center text-ink-500">
                      No hay requerimientos clasificados con PHI.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </section>

        <div className="space-y-5">
          <section className="panel" aria-labelledby="sg-roll-title">
            <div className="panel-title">
              <span id="sg-roll-title">Salvaguardas 164.312</span>
              <span className="normal-case tracking-normal text-ink-400">últimas ejecuciones</span>
            </div>
            {data.safeguards.length ? (
              <>
                <ul className="space-y-2 px-4 py-3">
                  {data.safeguards.map((s) => {
                    const meta = SAFEGUARDS.find((x) => x.id === s.id)!;
                    return (
                      <li key={s.id}>
                        <div className="flex items-baseline justify-between gap-2 text-[12.5px]">
                          <span className="text-ink-900">{meta.label}</span>
                          <span className="font-mono text-[11px] text-ink-500">
                            {s.riesgo} en riesgo · {s.sin_evidencia} sin evidencia · {s.cumple} cumple
                          </span>
                        </div>
                        <div className="mt-1 flex h-2.5 gap-0.5 overflow-hidden rounded-full bg-sunken" role="img" aria-label={`${meta.label}: ${s.riesgo} en riesgo, ${s.sin_evidencia} sin evidencia, ${s.cumple} cumple`}>
                          {SEG.map((seg) =>
                            s[seg.key] ? <span key={seg.key} className={`${seg.cls} h-full`} style={{ width: `${(s[seg.key] / s.total) * 100}%` }} /> : null,
                          )}
                        </div>
                      </li>
                    );
                  })}
                </ul>
                <p className="flex flex-wrap gap-3 border-t border-line px-4 py-2 text-[11.5px] text-ink-500">
                  {SEG.map((seg) => (
                    <span key={seg.key} className="inline-flex items-center gap-1.5">
                      <span className={`inline-block h-2.5 w-2.5 rounded-sm ${seg.cls}`} aria-hidden />
                      {seg.label}
                    </span>
                  ))}
                </p>
              </>
            ) : (
              <p className="px-4 py-6 text-center text-[13px] text-ink-500">Todavía no hay ejecuciones con el agente de Privacidad.</p>
            )}
          </section>

          <section className="panel" aria-labelledby="baa-title">
            <div className="panel-title">
              <span id="baa-title">Proveedores y BAA</span>
            </div>
            <ul className="divide-y divide-line">
              {data.providers.map((p) => (
                <li key={p.provider} className="px-4 py-2.5">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-[13px] font-medium text-ink-900">{PROVIDER_LABELS[p.provider]}</span>
                    <span className={`chip ${p.baa === true ? "border-ok/30 bg-ok-soft text-ok" : p.baa === false ? "border-danger/30 bg-danger-soft text-danger" : "chip-neutral"}`}>
                      {p.baa === true ? "BAA firmado" : p.baa === false ? "sin BAA" : "no aplica"}
                    </span>
                    <span className="ml-auto font-mono text-[11px] text-ink-400">{p.agents.length} agente(s)</span>
                  </div>
                  <p className="mt-0.5 text-[12px] leading-5 text-ink-500">
                    {p.agents.map((a) => AGENTS[a].label).join(", ")}
                    {p.phiAgents.length > 0 && p.baa === false && (
                      <span className="block text-danger">Con contexto de PHI: {p.phiAgents.map((a) => AGENTS[a].label).join(", ")}</span>
                    )}
                  </p>
                </li>
              ))}
            </ul>
            <p className="border-t border-line px-4 py-2 text-[11.5px] leading-5 text-ink-500">
              El estado de BAA es una suposición del prototipo. En producción debe venir del registro de proveedores y contratos.
            </p>
          </section>
        </div>
      </div>
    </div>
  );
}
