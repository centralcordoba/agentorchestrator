"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { AsyncState, ErrorState, Refreshing } from "@/components/rq/AsyncState";
import { PHI_POLICY, PhiBadge, PhiSelector } from "@/components/rq/PhiControl";
import { AgentChip, Avatar, VerdictBadge, fmtDate } from "@/components/rq/ui";
import { api } from "@/lib/api/client";
import type { RequirementPage, RunSummary } from "@/lib/api/types";
import { invalidate, useResource } from "@/lib/api/useResource";
import { can, missingPermissionText } from "@/lib/rq/governance";
import { USERS } from "@/lib/rq/mockData";
import { ATTACHMENT_LABELS } from "@/lib/rq/planner";
import { useRq } from "@/lib/rq/store";
import type { AttachmentKind, PhiClassification } from "@/lib/rq/types";

/** Estado de la fila, derivado de la última ejecución que devuelve la API. */
type RowStatus = "borrador" | "planificado" | "en_curso" | "completado" | "cancelado" | "fallido";

const STATUS_LABELS: Record<RowStatus, string> = {
  borrador: "Borrador",
  planificado: "Planificado",
  en_curso: "En ejecución",
  completado: "Completado",
  cancelado: "Cancelado",
  fallido: "Con error",
};

const STATUS_CLASS: Record<RowStatus, string> = {
  borrador: "chip-neutral",
  planificado: "border-info/30 bg-info-soft text-info",
  en_curso: "border-violet/30 bg-violet-soft text-violet",
  completado: "border-ok/30 bg-ok-soft text-ok",
  cancelado: "border-line bg-sunken text-ink-500",
  fallido: "border-danger/30 bg-danger-soft text-danger",
};

function rowStatus(lastRun: RunSummary | null | undefined, planned: number): RowStatus {
  if (!lastRun) return planned ? "planificado" : "borrador";
  switch (lastRun.status) {
    case "en_curso":
      return "en_curso";
    case "cancelada":
      return "cancelado";
    case "fallida":
      return "fallido";
    default:
      return "completado";
  }
}

const KINDS: AttachmentKind[] = ["repo", "vtr_template", "kiuwan_csv", "sql"];
const KIND_SHORT: Record<AttachmentKind, string> = {
  repo: "git",
  vtr_template: "VTR",
  kiuwan_csv: "Kiuwan",
  sql: "SQL",
};

const PAGE_SIZE = 25;

export default function RequirementsPage() {
  const { setLocation, currentUserId } = useRq();
  const currentUser = USERS.find((u) => u.id === currentUserId);
  const canCreate = can(currentUser, "crear_requerimiento");
  const router = useRouter();
  const [creating, setCreating] = useState(false);
  const [query, setQuery] = useState("");
  const [offset, setOffset] = useState(0);

  useEffect(() => setLocation({ page: "requerimientos" }), [setLocation]);

  const page = useResource<RequirementPage>(
    `requirements:${offset}`,
    () => api.requirements.list({ limit: PAGE_SIZE, offset }),
    // Hay ejecuciones en marcha: la lista se refresca sola mientras se mira.
    { refreshMs: 5000 },
  );

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="font-serif text-[26px] leading-tight text-ink-900">Requerimientos</h1>
          <p className="mt-1 max-w-2xl text-[13px] text-ink-500">
            Todo el proceso parte de un requerimiento: adjuntas el repositorio y los archivos, el
            orquestador sugiere qué agentes usar y tú decides cuáles ejecutar.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Refreshing active={page.refreshing && !page.loading} />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Buscar por código o título…"
            className="w-56 rounded-lg border border-line bg-surface px-3 py-2 text-[13px] outline-none focus:border-accent"
          />
          <button
            className="btn-primary"
            onClick={() => setCreating((v) => !v)}
            disabled={!canCreate && !creating}
            title={!canCreate ? missingPermissionText("crear_requerimiento") : undefined}
          >
            {creating ? "Cancelar" : "Nuevo requerimiento"}
          </button>
        </div>
      </div>

      {creating && (
        <NewRequirementForm
          onCreated={(id) => {
            setCreating(false);
            invalidate("requirements:");
            router.push(`/requerimiento?id=${id}`);
          }}
        />
      )}

      <AsyncState
        resource={page}
        empty={{
          title: "Todavía no hay requerimientos",
          description: "Crea el primero para que el orquestador proponga un plan de agentes.",
        }}
      >
        {(data) => {
          const q = query.trim().toLowerCase();
          const rows = data.items.filter(
            (r) => !q || `${r.id} ${r.title}`.toLowerCase().includes(q),
          );
          return (
            <div className="space-y-3">
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
                      const planned = r.plannedAgents ?? [];
                      const status = rowStatus(r.lastRun, planned.length);
                      return (
                        <tr
                          key={r.id}
                          className="cursor-pointer transition hover:bg-sunken/60"
                          onClick={() => router.push(`/requerimiento?id=${r.id}`)}
                        >
                          <td className="px-4 py-3">
                            <Link
                              href={`/requerimiento?id=${r.id}`}
                              className="block"
                              onClick={(e) => e.stopPropagation()}
                            >
                              <span className="flex items-center gap-1.5">
                                <span className="font-mono text-[11.5px] text-accent">{r.id}</span>
                                <PhiBadge phi={r.phi as PhiClassification} />
                              </span>
                              <span className="block font-medium text-ink-900">{r.title}</span>
                              <span className="text-[11.5px] text-ink-400">
                                creado {fmtDate(r.createdAt)}
                              </span>
                            </Link>
                          </td>
                          <td className="px-4 py-3">
                            {/* El responsable es el usuario autenticado que lo creó (ORQ-5). */}
                            <span className="flex items-center gap-2">
                              <span
                                aria-hidden
                                className="flex h-6 w-6 items-center justify-center rounded-md bg-sunken font-mono text-[10px] font-semibold text-ink-700"
                              >
                                {initialsOf(r.owner)}
                              </span>
                              <span className="text-ink-700">{r.owner}</span>
                            </span>
                          </td>
                          <td className="px-4 py-3">
                            <span className="flex flex-wrap gap-1">
                              {KINDS.map((k) => {
                                const on = (r.attachments ?? []).some((a) => a.kind === k);
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
                              {planned.length ? (
                                planned
                                  .filter((a) => a !== "orchestrator" && a !== "verdict")
                                  .map((a) => <AgentChip key={a} id={a as never} />)
                              ) : (
                                <span className="text-[12px] text-ink-400">sin plan</span>
                              )}
                            </span>
                          </td>
                          <td className="px-4 py-3">
                            <span className={`chip ${STATUS_CLASS[status]}`}>
                              {STATUS_LABELS[status]}
                            </span>
                            {r.lastRun && status === "en_curso" && (
                              <span className="mt-1 block font-mono text-[11px] text-ink-400">
                                {r.lastRun.completedAgents}/{r.lastRun.totalAgents} agentes
                              </span>
                            )}
                          </td>
                          <td className="px-4 py-3">
                            <span className="flex items-center gap-2">
                              {r.lastRun?.verdict ? (
                                <VerdictBadge verdict={r.lastRun.verdict as never} />
                              ) : (
                                <span className="text-ink-300">—</span>
                              )}
                              {r.lastRun && (
                                <Link
                                  href={`/ejecucion?run=${r.lastRun.id}`}
                                  className="text-[12px] text-accent hover:underline"
                                  onClick={(e) => e.stopPropagation()}
                                >
                                  ver ejecución
                                </Link>
                              )}
                            </span>
                          </td>
                        </tr>
                      );
                    })}
                    {!rows.length && (
                      <tr>
                        <td colSpan={6} className="px-4 py-10 text-center text-ink-500">
                          Ningún requerimiento coincide con «{query}».
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>

              {data.total > PAGE_SIZE && (
                <div className="flex items-center justify-between text-[12px] text-ink-500">
                  <span>
                    {data.offset + 1}–{data.offset + data.items.length} de {data.total}
                  </span>
                  <span className="flex gap-2">
                    <button
                      className="btn-ghost"
                      disabled={offset === 0}
                      onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
                    >
                      Anteriores
                    </button>
                    <button
                      className="btn-ghost"
                      disabled={data.offset + data.items.length >= data.total}
                      onClick={() => setOffset(offset + PAGE_SIZE)}
                    >
                      Siguientes
                    </button>
                  </span>
                </div>
              )}
            </div>
          );
        }}
      </AsyncState>
    </div>
  );
}

function NewRequirementForm({ onCreated }: { onCreated: (id: string) => void }) {
  const [phi, setPhi] = useState<PhiClassification | null>(null);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [criteria, setCriteria] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<unknown>(null);

  const list = useMemo(
    () => criteria.split("\n").map((c) => c.trim()).filter(Boolean),
    [criteria],
  );
  const valid = title.trim().length > 3 && description.trim().length > 10 && phi !== null;

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!valid || !phi || saving) return;
    setSaving(true);
    setError(null);
    try {
      const created = await api.requirements.create({
        title: title.trim(),
        description: description.trim(),
        acceptanceCriteria: list,
        phi,
      });
      onCreated(created.id);
    } catch (cause) {
      setError(cause);
    } finally {
      setSaving(false);
    }
  }

  return (
    <form className="panel grid gap-4 p-4 md:grid-cols-2" onSubmit={submit}>
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
        <PhiSelector value={phi} onChange={setPhi} disabled={saving} />
        {phi && phi !== "no" && (
          <ul className="grid gap-x-4 gap-y-0.5 rounded-lg border border-teal/20 bg-teal-soft/50 px-3 py-2 text-[12px] leading-5 text-teal sm:grid-cols-2">
            {PHI_POLICY.map((p) => (
              <li key={p}>• {p}</li>
            ))}
          </ul>
        )}
        {error !== null && <ErrorState error={error} title="No se pudo crear el requerimiento" />}
        <div className="flex items-center justify-end gap-3">
          {!valid && (
            <span className="text-[12px] text-ink-400">
              Faltan título, descripción y clasificación de PHI.
            </span>
          )}
          <button className="btn-primary" type="submit" disabled={!valid || saving}>
            {saving ? "Creando…" : "Crear requerimiento"}
          </button>
        </div>
      </div>
    </form>
  );
}

/** Iniciales a partir del correo, para el avatar de la lista. */
function initialsOf(email: string): string {
  const nombre = (email || "").split("@")[0];
  const partes = nombre.split(/[._-]+/).filter(Boolean);
  return (partes.slice(0, 2).map((p) => p[0]).join("") || nombre.slice(0, 2)).toUpperCase();
}
