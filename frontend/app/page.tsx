"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { PHI_POLICY, PhiBadge, PhiSelector } from "@/components/rq/PhiControl";
import { AgentChip, Avatar, VerdictBadge, fmtDate } from "@/components/rq/ui";
import { REQ_STATUS_LABELS, latestRun, requirementStatus, runView, type RequirementStatus } from "@/lib/rq/derive";
import { can, missingPermissionText } from "@/lib/rq/governance";
import { USERS } from "@/lib/rq/mockData";
import { ATTACHMENT_LABELS } from "@/lib/rq/planner";
import { useNow, useRq } from "@/lib/rq/store";
import type { AttachmentKind, PhiClassification } from "@/lib/rq/types";

const STATUS_CLASS: Record<RequirementStatus, string> = {
  borrador: "chip-neutral",
  planificado: "border-info/30 bg-info-soft text-info",
  en_curso: "border-violet/30 bg-violet-soft text-violet",
  completado: "border-ok/30 bg-ok-soft text-ok",
  pendiente_firma: "border-warn/30 bg-warn-soft text-warn",
  cancelado: "border-line bg-sunken text-ink-500",
};

const KINDS: AttachmentKind[] = ["repo", "vtr_template", "kiuwan_csv", "sql"];
const KIND_SHORT: Record<AttachmentKind, string> = { repo: "git", vtr_template: "VTR", kiuwan_csv: "Kiuwan", sql: "SQL" };

export default function RequirementsPage() {
  const { requirements, createRequirement, setLocation, currentUserId } = useRq();
  const canCreate = can(USERS.find((u) => u.id === currentUserId), "crear_requerimiento");
  const router = useRouter();
  const now = useNow(true, 1000);
  const [creating, setCreating] = useState(false);
  const [query, setQuery] = useState("");

  useEffect(() => setLocation({ page: "requerimientos" }), [setLocation]);

  const rows = useMemo(() => {
    const q = query.trim().toLowerCase();
    return requirements.filter((r) => !q || `${r.id} ${r.title}`.toLowerCase().includes(q));
  }, [requirements, query]);

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="font-serif text-[26px] leading-tight text-ink-900">Requerimientos</h1>
          <p className="mt-1 max-w-2xl text-[13px] text-ink-500">
            Todo el proceso parte de un requerimiento: adjuntas el repositorio y los archivos, el orquestador sugiere qué agentes usar
            y tú decides cuáles ejecutar.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Buscar por código o título…"
            className="w-56 rounded-lg border border-line bg-surface px-3 py-2 text-[13px] outline-none focus:border-accent"
          />
          <button className="btn-primary" onClick={() => setCreating((v) => !v)} disabled={!canCreate && !creating} title={!canCreate ? missingPermissionText("crear_requerimiento") : undefined}>
            {creating ? "Cancelar" : "Nuevo requerimiento"}
          </button>
        </div>
      </div>

      {creating && (
        <NewRequirementForm
          onCreate={(input) => {
            const id = createRequirement(input);
            setCreating(false);
            router.push(`/requerimiento?id=${id}`);
          }}
        />
      )}

      <div className="panel overflow-x-auto">
        <table className="w-full min-w-[860px] text-left text-[13px]">
          <thead className="bg-sunken text-[11px] uppercase tracking-[0.06em] text-ink-500">
            <tr>
              <th className="px-4 py-2 font-semibold">Requerimiento</th>
              <th className="px-4 py-2 font-semibold">Responsable</th>
              <th className="px-4 py-2 font-semibold">Adjuntos</th>
              <th className="px-4 py-2 font-semibold">Agentes</th>
              <th className="px-4 py-2 font-semibold">Estado</th>
              <th className="px-4 py-2 font-semibold">Dictamen</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {rows.map((r) => {
              const status = requirementStatus(r, now);
              const run = latestRun(r);
              const view = run ? runView(r, run, now) : null;
              const owner = USERS.find((u) => u.id === r.owner) ?? USERS[0];
              const agents = run ? run.enabledAgents : r.plan?.items.filter((i) => i.enabled).map((i) => i.agentId) ?? [];
              return (
                <tr key={r.id} className="cursor-pointer transition hover:bg-sunken/60" onClick={() => router.push(`/requerimiento?id=${r.id}`)}>
                  <td className="px-4 py-3">
                    <Link href={`/requerimiento?id=${r.id}`} className="block" onClick={(e) => e.stopPropagation()}>
                      <span className="flex items-center gap-1.5">
                        <span className="font-mono text-[11.5px] text-accent">{r.id}</span>
                        <PhiBadge phi={r.phi} />
                      </span>
                      <span className="block font-medium text-ink-900">{r.title}</span>
                      <span className="text-[11.5px] text-ink-400">creado {fmtDate(r.createdAt)}</span>
                    </Link>
                  </td>
                  <td className="px-4 py-3">
                    <span className="flex items-center gap-2">
                      <Avatar user={owner} size={24} />
                      <span className="text-ink-700">{owner.name}</span>
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <span className="flex flex-wrap gap-1">
                      {KINDS.map((k) => {
                        const on = r.attachments.some((a) => a.kind === k);
                        return (
                          <span
                            key={k}
                            title={`${ATTACHMENT_LABELS[k]}: ${on ? "adjunto" : "falta"}`}
                            className={`chip ${on ? "chip-neutral" : "border-dashed border-line bg-transparent text-ink-300"}`}
                          >
                            {KIND_SHORT[k]}
                          </span>
                        );
                      })}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <span className="flex max-w-[260px] flex-wrap gap-1">
                      {agents.length ? (
                        agents.filter((a) => a !== "orchestrator" && a !== "verdict").map((a) => <AgentChip key={a} id={a} />)
                      ) : (
                        <span className="text-[12px] text-ink-400">sin plan</span>
                      )}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`chip ${STATUS_CLASS[status]}`}>{REQ_STATUS_LABELS[status]}</span>
                    {view?.state === "en_curso" && (
                      <span className="mt-1 block font-mono text-[11px] text-ink-400">
                        {view.completed.length}/{run!.enabledAgents.length} agentes
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3">{view?.verdict ? <VerdictBadge verdict={view.verdict} /> : <span className="text-ink-300">—</span>}</td>
                </tr>
              );
            })}
            {!rows.length && (
              <tr>
                <td colSpan={6} className="px-4 py-10 text-center text-ink-500">
                  No hay requerimientos que coincidan.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function NewRequirementForm({ onCreate }: { onCreate: (i: { title: string; description: string; criteria: string[]; phi: PhiClassification }) => void }) {
  const [phi, setPhi] = useState<PhiClassification | null>(null);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [criteria, setCriteria] = useState("");
  const list = criteria.split("\n").map((c) => c.trim()).filter(Boolean);
  const valid = title.trim().length > 3 && description.trim().length > 10 && phi !== null;

  return (
    <form
      className="panel grid gap-4 p-4 md:grid-cols-2"
      onSubmit={(e) => {
        e.preventDefault();
        if (valid && phi) onCreate({ title: title.trim(), description: description.trim(), criteria: list, phi });
      }}
    >
      <div className="space-y-3">
        <label className="block">
          <span className="text-[12px] font-semibold text-ink-700">Título</span>
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Ej.: Nueva pantalla de consulta de movimientos"
            className="mt-1 w-full rounded-lg border border-line bg-surface px-3 py-2 text-[13px] outline-none focus:border-accent"
          />
        </label>
        <label className="block">
          <span className="text-[12px] font-semibold text-ink-700">Descripción</span>
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={5}
            placeholder="Qué hay que construir y para quién."
            className="mt-1 w-full rounded-lg border border-line bg-surface px-3 py-2 text-[13px] outline-none focus:border-accent"
          />
        </label>
      </div>
      <div className="flex flex-col gap-3">
        <label className="block flex-1">
          <span className="text-[12px] font-semibold text-ink-700">Criterios de aceptación</span>
          <span className="ml-1 text-[11.5px] text-ink-400">(uno por línea)</span>
          <textarea
            value={criteria}
            onChange={(e) => setCriteria(e.target.value)}
            rows={7}
            placeholder={"El usuario puede filtrar por fecha.\nLa consulta responde en menos de 2 s."}
            className="mt-1 w-full rounded-lg border border-line bg-surface px-3 py-2 text-[13px] outline-none focus:border-accent"
          />
        </label>
      </div>
      <div className="space-y-2 md:col-span-2">
        <PhiSelector value={phi} onChange={setPhi} />
        {phi && phi !== "no" && (
          <ul className="grid gap-x-4 gap-y-0.5 rounded-lg border border-teal/20 bg-teal-soft/50 px-3 py-2 text-[12px] leading-5 text-teal sm:grid-cols-2">
            {PHI_POLICY.map((p) => (
              <li key={p}>• {p}</li>
            ))}
          </ul>
        )}
        <div className="flex flex-wrap items-center justify-between gap-3 pt-1">
          <span className="text-[12px] text-ink-500">
            {phi === null ? "Indica si puede tocar PHI para poder crear el requerimiento." : "Después podrás adjuntar el repositorio, la plantilla VTR, el CSV de Kiuwan y los SQL."}
          </span>
          <button type="submit" className="btn-primary" disabled={!valid}>
            Crear
          </button>
        </div>
      </div>
    </form>
  );
}
