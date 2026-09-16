"use client";

import Link from "next/link";
import { AGENTS, ALL_AGENTS, PROVIDER_BAA, PROVIDER_LABELS, modelLabel } from "@/lib/rq/agents";
import { AGENT_CARDS } from "@/lib/rq/governance";
import { USERS } from "@/lib/rq/mockData";
import { useRq } from "@/lib/rq/store";
import type { AgentId } from "@/lib/rq/types";
import { Avatar, fmtDate } from "../ui";
import { ChangeStatusChip } from "./ChangeRequestsView";

const PHI_LABEL = {
  redactada: { text: "Recibe contexto con PHI redactada", cls: "border-teal/30 bg-teal-soft text-teal" },
  metadatos: { text: "Solo metadatos y hallazgos", cls: "chip-neutral text-ink-600" },
  no: { text: "No recibe datos del cambio", cls: "chip-neutral text-ink-500" },
} as const;

/** Ficha por agente: para qué sirve, quién responde de él, qué datos ve y con qué modelo. */
export default function AgentCardsView() {
  const { profiles, changeRequests, requirements } = useRq();

  return (
    <div className="space-y-3">
      <p className="text-[13px] leading-5 text-ink-500">
        Cada agente tiene una persona responsable, un alcance de datos declarado y limitaciones conocidas. Es la ficha que se
        presenta en una auditoría para explicar qué hace la IA y con qué información.
      </p>
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {ALL_AGENTS.map((id: AgentId) => {
          const a = AGENTS[id];
          const card = AGENT_CARDS[id];
          const p = profiles[id];
          const owner = USERS.find((u) => u.id === card.owner);
          const pending = changeRequests.find((c) => c.agentId === id && c.status === "pendiente");
          const lastApproved = changeRequests.find((c) => c.agentId === id && c.status === "aprobada");
          const baa = PROVIDER_BAA[p.provider];
          const phiRisk = card.receivesPhi === "redactada" && baa === false;
          const overrides = requirements.filter((r) => r.profileOverrides[id]).map((r) => r.id);
          return (
            <article key={id} className="panel flex flex-col gap-3 p-4" aria-labelledby={`card-${id}`}>
              <header className="flex items-start gap-2">
                <span className="mt-0.5 h-8 w-1.5 shrink-0 rounded-full" style={{ background: a.color }} />
                <div className="min-w-0 flex-1">
                  <h3 id={`card-${id}`} className="text-[14px] font-semibold text-ink-900">
                    {a.label}
                  </h3>
                  <p className="text-[12px] leading-5 text-ink-500">{a.role}</p>
                </div>
                {pending && <ChangeStatusChip status="pendiente" />}
              </header>

              <dl className="space-y-1.5 text-[12.5px]">
                <div className="flex gap-2">
                  <dt className="w-[92px] shrink-0 text-ink-500">Responsable</dt>
                  <dd className="flex items-center gap-1.5 text-ink-900">
                    {owner && <Avatar user={owner} size={18} />}
                    {owner?.name} <span className="text-ink-400">({owner?.role})</span>
                  </dd>
                </div>
                <div className="flex gap-2">
                  <dt className="w-[92px] shrink-0 text-ink-500">Modelo</dt>
                  <dd className="text-ink-900">
                    {modelLabel(p.provider, p.model)}
                    <span className="block font-mono text-[11px] text-ink-400">
                      {PROVIDER_LABELS[p.provider]} · prompt v{p.promptVersion}
                    </span>
                  </dd>
                </div>
                <div className="flex gap-2">
                  <dt className="w-[92px] shrink-0 text-ink-500">Datos</dt>
                  <dd className="text-ink-700">{card.dataAccess.join(" · ")}</dd>
                </div>
                <div className="flex gap-2">
                  <dt className="w-[92px] shrink-0 text-ink-500">Herramientas</dt>
                  <dd className="flex flex-wrap gap-1">
                    {a.tools.map((t) => (
                      <span key={t} className="chip chip-neutral">
                        {t}
                      </span>
                    ))}
                  </dd>
                </div>
                <div className="flex gap-2">
                  <dt className="w-[92px] shrink-0 text-ink-500">Límites</dt>
                  <dd className="text-ink-700">{card.limitations.join(" ")}</dd>
                </div>
              </dl>

              <div className="mt-auto space-y-2 border-t border-line pt-2">
                <div className="flex flex-wrap gap-1.5">
                  <span className={`chip ${PHI_LABEL[card.receivesPhi].cls}`}>{PHI_LABEL[card.receivesPhi].text}</span>
                  <span className={`chip ${baa === true ? "border-ok/30 bg-ok-soft text-ok" : baa === false ? "border-danger/30 bg-danger-soft text-danger" : "chip-neutral"}`}>
                    {baa === true ? "proveedor con BAA" : baa === false ? "proveedor sin BAA" : "proveedor mock"}
                  </span>
                </div>
                {phiRisk && (
                  <p className="text-[11.5px] leading-5 text-danger">
                    Riesgo: recibe contexto de requerimientos con PHI y su proveedor no tiene BAA. Solo le llega texto redactado, pero conviene moverlo a un proveedor con BAA.
                  </p>
                )}
                {overrides.length > 0 && <p className="text-[11.5px] text-ink-500">Ajustado en: {overrides.join(", ")}</p>}
                <p className="text-[11.5px] text-ink-400">
                  {lastApproved ? `Último cambio aprobado: ${lastApproved.id} · ${fmtDate(lastApproved.review?.at ?? lastApproved.createdAt)}` : "Sin cambios aprobados todavía."}
                </p>
                <Link href={`/agentes?agent=${id}`} className="btn-ghost inline-flex">
                  ver y proponer cambios →
                </Link>
              </div>
            </article>
          );
        })}
      </div>
    </div>
  );
}
