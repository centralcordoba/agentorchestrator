"use client";

import { useEffect, useMemo, useState } from "react";
import { AGENTS, PROVIDER_BAA, PROVIDER_LABELS, modelLabel } from "@/lib/rq/agents";
import { EVAL_CASES, approvalGate, changedFields, wordDiff } from "@/lib/rq/governance";
import { USERS } from "@/lib/rq/mockData";
import { useRq } from "@/lib/rq/store";
import type { ChangeRequest, ChangeStatus, ProfileSnapshot } from "@/lib/rq/types";
import { AgentChip, Avatar, EmptyState, fmtDate } from "../ui";

type Filter = "pendiente" | "resueltas" | "todas";

export const CHANGE_STATUS: Record<ChangeStatus, { label: string; cls: string; icon: string }> = {
  pendiente: { label: "Pendiente", cls: "border-warn/30 bg-warn-soft text-warn", icon: "●" },
  aprobada: { label: "Aprobada", cls: "border-ok/30 bg-ok-soft text-ok", icon: "✓" },
  rechazada: { label: "Rechazada", cls: "border-danger/30 bg-danger-soft text-danger", icon: "✕" },
  retirada: { label: "Retirada", cls: "chip-neutral text-ink-500", icon: "–" },
};

export function ChangeStatusChip({ status }: { status: ChangeStatus }) {
  const s = CHANGE_STATUS[status];
  return (
    <span className={`chip ${s.cls}`}>
      <span aria-hidden>{s.icon}</span>
      {s.label}
    </span>
  );
}

export default function ChangeRequestsView({ selectedId, onSelect }: { selectedId: string | null; onSelect: (id: string) => void }) {
  const { changeRequests } = useRq();
  const [filter, setFilter] = useState<Filter>("pendiente");
  const pendingCount = changeRequests.filter((c) => c.status === "pendiente").length;

  const list = useMemo(
    () =>
      changeRequests.filter((c) => (filter === "todas" ? true : filter === "pendiente" ? c.status === "pendiente" : c.status !== "pendiente")),
    [changeRequests, filter],
  );
  const selected = changeRequests.find((c) => c.id === selectedId) ?? list[0] ?? null;

  // Si la solicitud abierta por URL no está en el filtro actual, se muestra "todas".
  useEffect(() => {
    if (selectedId && !list.some((c) => c.id === selectedId) && changeRequests.some((c) => c.id === selectedId)) setFilter("todas");
  }, [selectedId, list, changeRequests]);

  return (
    <div className="grid gap-5 lg:grid-cols-[340px_minmax(0,1fr)]">
      <aside className="panel self-start" aria-label="Solicitudes de cambio">
        <div className="flex flex-wrap gap-1 border-b border-line px-3 py-2">
          {(
            [
              ["pendiente", `pendientes (${pendingCount})`],
              ["resueltas", "resueltas"],
              ["todas", "todas"],
            ] as [Filter, string][]
          ).map(([f, label]) => (
            <button key={f} onClick={() => setFilter(f)} aria-pressed={filter === f} className={`pill ${filter === f ? "pill-active" : "pill-idle"}`}>
              {label}
            </button>
          ))}
        </div>
        {list.length ? (
          <ul className="divide-y divide-line">
            {list.map((c) => {
              const author = USERS.find((u) => u.id === c.createdBy);
              const active = selected?.id === c.id;
              return (
                <li key={c.id}>
                  <button onClick={() => onSelect(c.id)} aria-current={active} className={`w-full px-4 py-3 text-left transition ${active ? "bg-sunken" : "hover:bg-sunken/60"}`}>
                    <span className="flex flex-wrap items-center gap-2">
                      <span className="font-mono text-[12px] text-accent">{c.id}</span>
                      <AgentChip id={c.agentId} />
                      <span className="ml-auto">
                        <ChangeStatusChip status={c.status} />
                      </span>
                    </span>
                    <span className="mt-1 line-clamp-2 block text-[12.5px] leading-5 text-ink-700">{c.justification}</span>
                    <span className="mt-1 block text-[11.5px] text-ink-400">
                      {changedFields(c).join(" · ")} · {author?.name} · {fmtDate(c.createdAt)}
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
        ) : (
          <p className="px-4 py-8 text-center text-[13px] text-ink-500">
            {filter === "pendiente" ? "No hay solicitudes pendientes." : "No hay solicitudes en este filtro."}
          </p>
        )}
        <p className="border-t border-line px-4 py-2 text-[11.5px] leading-5 text-ink-500">
          Para proponer un cambio, edita un agente en <span className="font-medium text-ink-700">Agentes</span> y pulsa «Solicitar aprobación».
        </p>
      </aside>

      {selected ? <ChangeRequestDetail key={selected.id} cr={selected} /> : <EmptyState title="Sin solicitudes">Todavía no hay cambios propuestos.</EmptyState>}
    </div>
  );
}

function ChangeRequestDetail({ cr }: { cr: ChangeRequest }) {
  const { currentUserId, evaluateChangeRequest, approveChange, rejectChange, withdrawChange } = useRq();
  const user = USERS.find((u) => u.id === currentUserId);
  const author = USERS.find((u) => u.id === cr.createdBy);
  const reviewer = USERS.find((u) => u.id === cr.review?.by);
  const [evaluating, setEvaluating] = useState(false);
  const [comment, setComment] = useState("");
  const gate = approvalGate(cr, user);
  const commentOkForApprove = !gate.commentRequired || comment.trim().length >= 20;
  const commentOkForReject = comment.trim().length >= 10;
  const isAuthor = user?.id === cr.createdBy;

  const runEval = () => {
    setEvaluating(true);
    setTimeout(() => {
      evaluateChangeRequest(cr.id);
      setEvaluating(false);
    }, 1500);
  };

  return (
    <section className="space-y-4" aria-labelledby="cr-title">
      <div className="panel p-4">
        <div className="flex flex-wrap items-center gap-2">
          <h2 id="cr-title" className="font-mono text-[15px] font-semibold text-ink-900">
            {cr.id}
          </h2>
          <ChangeStatusChip status={cr.status} />
          <AgentChip id={cr.agentId} />
          <span className="text-[12px] text-ink-500">
            prompt v{cr.before.promptVersion} → v{cr.after.promptVersion}
          </span>
        </div>
        <p className="mt-2 text-[14px] leading-6 text-ink-900">{cr.justification}</p>
        <p className="mt-2 flex items-center gap-2 text-[12px] text-ink-500">
          {author && <Avatar user={author} size={20} />}
          Solicitado por {author?.name} ({author?.role}) · {fmtDate(cr.createdAt)}
        </p>
      </div>

      <div className="panel">
        <div className="panel-title">
          <span>Qué cambia</span>
          <span className="normal-case tracking-normal text-ink-400">{changedFields(cr).join(" · ")}</span>
        </div>
        <ParamsTable before={cr.before} after={cr.after} />
        {(cr.before.systemPrompt !== cr.after.systemPrompt || cr.before.taskPrompt !== cr.after.taskPrompt) && (
          <div className="space-y-3 border-t border-line p-4">
            <PromptDiff label="Prompt de sistema" before={cr.before.systemPrompt} after={cr.after.systemPrompt} />
            {cr.before.taskPrompt !== cr.after.taskPrompt && <PromptDiff label="Plantilla de tarea" before={cr.before.taskPrompt} after={cr.after.taskPrompt} />}
            <p className="flex flex-wrap gap-3 text-[11.5px] text-ink-500">
              <span>
                <span className="rounded bg-ok-soft px-1 text-ok">texto añadido</span>
              </span>
              <span>
                <span className="rounded bg-danger-soft px-1 text-danger line-through">texto eliminado</span>
              </span>
            </p>
          </div>
        )}
      </div>

      <EvaluationPanel cr={cr} evaluating={evaluating} onRun={cr.status === "pendiente" ? runEval : undefined} />

      {cr.status === "pendiente" ? (
        <div className="panel space-y-3 p-4" aria-labelledby="review-title">
          <h3 id="review-title" className="text-[13.5px] font-semibold text-ink-900">
            Revisión (cuatro ojos)
          </h3>
          <ul className="grid gap-1 sm:grid-cols-2">
            {gate.checks.map((c) => (
              <li key={c.label} className={`flex gap-2 text-[12.5px] leading-5 ${c.ok ? "text-ok" : "text-ink-500"}`}>
                <span aria-hidden className="font-mono">{c.ok ? "✓" : "○"}</span>
                <span>
                  <span className="sr-only">{c.ok ? "Cumplido: " : "Pendiente: "}</span>
                  {c.label}
                </span>
              </li>
            ))}
          </ul>
          <label className="block">
            <span className="text-[12px] font-semibold text-ink-700">
              Comentario de la revisión{" "}
              {gate.commentRequired ? <span className="font-normal text-warn">(obligatorio para aprobar con regresiones, mín. 20)</span> : <span className="font-normal text-ink-400">(obligatorio para rechazar)</span>}
            </span>
            <textarea value={comment} onChange={(e) => setComment(e.target.value)} rows={2} className="mt-1 w-full rounded-lg border border-line bg-surface px-3 py-2 text-[13px] outline-none focus:border-accent" />
          </label>
          <div className="flex flex-wrap items-center gap-2">
            <button className="btn-primary" disabled={!gate.ok || !commentOkForApprove} onClick={() => approveChange(cr.id, comment.trim())}>
              Aprobar y aplicar
            </button>
            <button
              className="inline-flex items-center rounded-lg border border-danger/40 bg-surface px-4 py-2 text-sm font-semibold text-danger transition hover:bg-danger-soft disabled:cursor-not-allowed disabled:opacity-50"
              disabled={!gate.checks[0].ok || !gate.checks[1].ok || !commentOkForReject}
              onClick={() => rejectChange(cr.id, comment.trim())}
            >
              Rechazar
            </button>
            {isAuthor && (
              <button className="btn-ghost ml-auto" onClick={() => withdrawChange(cr.id)}>
                retirar mi solicitud
              </button>
            )}
          </div>
          {!gate.ok && <p className="text-[12px] text-ink-500">Cambia de usuario arriba a la derecha para revisar como otra persona (p. ej. Martín Rojas o Valentina Ortiz).</p>}
        </div>
      ) : (
        cr.review && (
          <div className={`panel border-l-4 p-4 ${cr.status === "aprobada" ? "border-l-ok" : "border-l-danger"}`}>
            <p className="text-[13px] text-ink-900">
              <span className="font-semibold">{cr.status === "aprobada" ? "Aprobada" : "Rechazada"}</span> por {reviewer?.name} ({reviewer?.role}) · {fmtDate(cr.review.at)}
            </p>
            {cr.review.comment && <p className="mt-1 text-[13px] leading-5 text-ink-700">«{cr.review.comment}»</p>}
          </div>
        )
      )}
    </section>
  );
}

function ParamsTable({ before, after }: { before: ProfileSnapshot; after: ProfileSnapshot }) {
  const rows: [string, string, string][] = [
    ["Proveedor", `${PROVIDER_LABELS[before.provider]}${PROVIDER_BAA[before.provider] === false ? " (sin BAA)" : ""}`, `${PROVIDER_LABELS[after.provider]}${PROVIDER_BAA[after.provider] === false ? " (sin BAA)" : ""}`],
    ["Modelo", modelLabel(before.provider, before.model), modelLabel(after.provider, after.model)],
    ["Temperatura", before.temperature.toFixed(1), after.temperature.toFixed(1)],
    ["Pasos máximos", String(before.maxSteps), String(after.maxSteps)],
  ];
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[420px] text-left text-[12.5px]">
        <thead className="bg-sunken text-[11px] uppercase tracking-[0.06em] text-ink-500">
          <tr>
            <th scope="col" className="px-4 py-1.5 font-semibold">Parámetro</th>
            <th scope="col" className="px-4 py-1.5 font-semibold">Actual</th>
            <th scope="col" className="px-4 py-1.5 font-semibold">Propuesto</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-line">
          {rows.map(([k, a, b]) => {
            const changed = a !== b;
            return (
              <tr key={k} className={changed ? "bg-accent-soft/40" : ""}>
                <th scope="row" className="px-4 py-2 font-medium text-ink-700">{k}</th>
                <td className="px-4 py-2 text-ink-500">{a}</td>
                <td className={`px-4 py-2 ${changed ? "font-semibold text-ink-900" : "text-ink-500"}`}>
                  {b}
                  {changed && <span className="sr-only"> (cambia)</span>}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function PromptDiff({ label, before, after }: { label: string; before: string; after: string }) {
  const parts = useMemo(() => wordDiff(before, after), [before, after]);
  return (
    <div>
      <div className="mb-1 text-[11.5px] font-semibold text-ink-700">{label}</div>
      <p className="rounded-lg border border-line bg-sunken/60 px-3 py-2 font-mono text-[12px] leading-5 text-ink-700">
        {parts.map((p, i) =>
          p.kind === "igual" ? (
            <span key={i}>{p.text}</span>
          ) : p.kind === "agregado" ? (
            <ins key={i} className="rounded bg-ok-soft text-ok no-underline">
              {p.text}
            </ins>
          ) : (
            <del key={i} className="rounded bg-danger-soft text-danger">
              {p.text}
            </del>
          ),
        )}
      </p>
    </div>
  );
}

function EvaluationPanel({ cr, evaluating, onRun }: { cr: ChangeRequest; evaluating: boolean; onRun?: () => void }) {
  const ev = cr.evaluation;
  return (
    <div className="panel" aria-labelledby="eval-title">
      <div className="panel-title">
        <span id="eval-title">Evaluación de regresión</span>
        {onRun && (
          <button className="btn-ghost normal-case tracking-normal" onClick={onRun} disabled={evaluating}>
            {evaluating ? "evaluando 6 casos…" : ev ? "volver a evaluar" : "ejecutar evaluación"}
          </button>
        )}
      </div>
      {!ev ? (
        <div className="px-4 py-6 text-center">
          <p className="text-[13px] text-ink-700">Sin evaluar. La aprobación exige comparar la versión propuesta con la actual sobre {EVAL_CASES.length} casos fijos.</p>
          <p className="mt-1 text-[12px] text-ink-500">Simulado: en el backend se relanzará el agente con cada versión.</p>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-px border-b border-line bg-line sm:grid-cols-4">
            {[
              ["Regresiones", String(ev.regressions), ev.regressions ? "text-danger" : "text-ok"],
              ["Mejoras", String(ev.improvements), "text-ink-900"],
              ["Coste", `${ev.costDeltaPct > 0 ? "+" : ""}${ev.costDeltaPct} %`, ev.costDeltaPct > 50 ? "text-warn" : "text-ink-900"],
              ["Latencia", `${ev.latencyDeltaPct > 0 ? "+" : ""}${ev.latencyDeltaPct} %`, "text-ink-900"],
            ].map(([k, v, cls]) => (
              <div key={k} className="bg-surface px-4 py-2">
                <div className="text-[10.5px] uppercase tracking-[0.08em] text-ink-400">{k}</div>
                <div className={`font-serif text-[20px] ${cls}`}>{v}</div>
              </div>
            ))}
          </div>
          {ev.complianceBlockers.map((b) => (
            <p key={b} role="alert" className="border-b border-line bg-danger-soft px-4 py-2 text-[12.5px] leading-5 text-danger">
              <span className="font-semibold">Bloqueo de cumplimiento: </span>
              {b}
            </p>
          ))}
          <div className="overflow-x-auto">
            <table className="w-full min-w-[560px] text-left text-[12.5px]">
              <thead className="bg-sunken text-[11px] uppercase tracking-[0.06em] text-ink-500">
                <tr>
                  <th scope="col" className="px-4 py-1.5 font-semibold">Caso</th>
                  <th scope="col" className="px-4 py-1.5 font-semibold">Actual</th>
                  <th scope="col" className="px-4 py-1.5 font-semibold">Propuesta</th>
                  <th scope="col" className="px-4 py-1.5 font-semibold">Observación</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {ev.results.map((r) => {
                  const c = EVAL_CASES.find((x) => x.id === r.caseId)!;
                  const regression = r.baseline === "paso" && r.candidate === "fallo";
                  return (
                    <tr key={r.caseId} className={regression ? "bg-danger-soft/40" : ""}>
                      <td className="px-4 py-2">
                        <span className="font-mono text-[11px] text-ink-400">{c.id}</span> <span className="text-ink-900">{c.name}</span>
                        <span className="block text-[11.5px] text-ink-500">Esperado: {c.expected}</span>
                      </td>
                      <td className="px-4 py-2">
                        <ResultChip value={r.baseline} />
                      </td>
                      <td className="px-4 py-2">
                        <ResultChip value={r.candidate} />
                      </td>
                      <td className="px-4 py-2 text-ink-700">{r.note}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <p className="border-t border-line px-4 py-2 text-[11.5px] text-ink-500">
            Evaluado por {USERS.find((u) => u.id === ev.runBy)?.name ?? ev.runBy} · {fmtDate(ev.runAt)} · resultados simulados
          </p>
        </>
      )}
    </div>
  );
}

function ResultChip({ value }: { value: "paso" | "fallo" }) {
  return value === "paso" ? (
    <span className="chip border-ok/30 bg-ok-soft text-ok">
      <span aria-hidden>✓</span> pasa
    </span>
  ) : (
    <span className="chip border-danger/30 bg-danger-soft text-danger">
      <span aria-hidden>✕</span> falla
    </span>
  );
}
