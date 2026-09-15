"use client";

import { useState } from "react";
import { USERS } from "@/lib/rq/mockData";
import { ATTACHMENT_LABELS } from "@/lib/rq/planner";
import { useRq } from "@/lib/rq/store";
import { GitHubError, connectRepo, fetchRepoMeta, type CompareMode } from "@/lib/rq/github";
import type { AttachmentKind, RepoInfo, Requirement } from "@/lib/rq/types";
import { RepoCard, RepoConnector } from "../RepoConnector";
import { Avatar, fmtDate } from "../ui";

const KIND_HINT: Record<AttachmentKind, string> = {
  repo: "Repositorio público de GitHub y rama del desarrollo. Se lee el diff real; lo usan Código, Tests, SQL y UI/UX.",
  vtr_template: "Documento Word modelo. El agente VTR lo rellena respetando su estructura.",
  kiuwan_csv: "Exportación CSV del análisis de Kiuwan sobre el código.",
  sql: "Scripts o migraciones SQL del cambio (puedes adjuntar varios).",
};

const ACCEPT: Record<Exclude<AttachmentKind, "repo">, string> = {
  vtr_template: ".docx",
  kiuwan_csv: ".csv",
  sql: ".sql",
};

function kb(bytes: number) {
  return `${Math.max(1, Math.round(bytes / 1024))} KB`;
}

export default function RequirementTab({ req, readOnly }: { req: Requirement; readOnly: boolean }) {
  const { updateRequirement, addAttachment, removeAttachment } = useRq();
  const [editing, setEditing] = useState(false);
  const [title, setTitle] = useState(req.title);
  const [description, setDescription] = useState(req.description);
  const [criteria, setCriteria] = useState(req.acceptanceCriteria.join("\n"));
  const [refreshing, setRefreshing] = useState(false);
  const [refreshError, setRefreshError] = useState<string | null>(null);

  // Vuelve a leer el repositorio con el mismo rango (misma base o mismo número de commits).
  const refreshRepo = async (repo: RepoInfo) => {
    setRefreshing(true);
    setRefreshError(null);
    try {
      const meta = await fetchRepoMeta(repo.owner, repo.name);
      const mode: CompareMode = meta.branches.includes(repo.base) ? { kind: "base", base: repo.base } : { kind: "commits", count: Math.max(1, repo.aheadBy) };
      const next = await connectRepo(meta, repo.branch, mode);
      addAttachment(req.id, { kind: "repo", name: next.htmlUrl, detail: next.branch, repo: next });
    } catch (e) {
      setRefreshError(e instanceof GitHubError ? e.message : "No se pudo actualizar el repositorio.");
    } finally {
      setRefreshing(false);
    }
  };
  const owner = USERS.find((u) => u.id === req.owner) ?? USERS[0];

  const onFile = async (kind: Exclude<AttachmentKind, "repo">, files: FileList | null) => {
    if (!files) return;
    for (const f of Array.from(files)) {
      let detail = kb(f.size);
      if (kind === "kiuwan_csv") {
        const text = await f.text();
        const rows = text.split(/\r?\n/).filter((l) => l.trim()).length - 1;
        detail = `${Math.max(0, rows)} filas · ${detail}`;
      }
      addAttachment(req.id, { kind, name: f.name, detail });
    }
  };

  return (
    <div className="grid gap-5 lg:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
      <section className="panel">
        <div className="panel-title">
          <span>Definición</span>
          {!readOnly && (
            <button
              className="btn-ghost normal-case tracking-normal"
              onClick={() => {
                if (editing) {
                  updateRequirement(req.id, {
                    title: title.trim(),
                    description: description.trim(),
                    acceptanceCriteria: criteria.split("\n").map((c) => c.trim()).filter(Boolean),
                  });
                }
                setEditing((v) => !v);
              }}
            >
              {editing ? "Guardar" : "Editar"}
            </button>
          )}
        </div>
        <div className="space-y-4 p-4">
          {editing ? (
            <>
              <input value={title} onChange={(e) => setTitle(e.target.value)} className="w-full rounded-lg border border-line px-3 py-2 text-[14px] outline-none focus:border-accent" />
              <textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={4} className="w-full rounded-lg border border-line px-3 py-2 text-[13px] outline-none focus:border-accent" />
              <label className="block">
                <span className="text-[12px] font-semibold text-ink-700">Criterios de aceptación (uno por línea)</span>
                <textarea value={criteria} onChange={(e) => setCriteria(e.target.value)} rows={5} className="mt-1 w-full rounded-lg border border-line px-3 py-2 text-[13px] outline-none focus:border-accent" />
              </label>
            </>
          ) : (
            <>
              <p className="text-[14px] leading-6 text-ink-700">{req.description}</p>
              <div>
                <div className="mb-2 text-[11px] font-semibold uppercase tracking-[0.08em] text-ink-500">Criterios de aceptación</div>
                <ol className="space-y-2">
                  {req.acceptanceCriteria.map((c, i) => (
                    <li key={i} className="flex gap-2.5 text-[13.5px] leading-5 text-ink-700">
                      <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-accent-soft font-mono text-[10.5px] font-semibold text-accent">
                        {i + 1}
                      </span>
                      {c}
                    </li>
                  ))}
                  {!req.acceptanceCriteria.length && <li className="text-[13px] text-ink-400">Sin criterios definidos.</li>}
                </ol>
              </div>
            </>
          )}
          <div className="flex items-center gap-2 border-t border-line pt-3 text-[12px] text-ink-500">
            <Avatar user={owner} size={22} />
            <span>
              {owner.name} · creado {fmtDate(req.createdAt)}
            </span>
          </div>
        </div>
      </section>

      <section className="panel">
        <div className="panel-title">
          <span>Adjuntos</span>
          <span className="font-mono normal-case tracking-normal text-ink-400">{req.attachments.length}</span>
        </div>
        <div className="divide-y divide-line">
          {(["repo", "vtr_template", "kiuwan_csv", "sql"] as AttachmentKind[]).map((kind) => {
            const items = req.attachments.filter((a) => a.kind === kind);
            return (
              <div key={kind} className="space-y-2 px-4 py-3">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-[13px] font-semibold text-ink-900">{ATTACHMENT_LABELS[kind]}</span>
                  {!items.length && <span className="chip border-dashed border-line-strong bg-transparent text-ink-400">falta</span>}
                </div>
                <p className="text-[12px] leading-5 text-ink-500">{KIND_HINT[kind]}</p>
                {items.map((a) =>
                  a.repo ? (
                    <RepoCard
                      key={a.id}
                      repo={a.repo}
                      readOnly={readOnly}
                      busy={refreshing}
                      onRemove={() => removeAttachment(req.id, a.id)}
                      onRefresh={() => refreshRepo(a.repo!)}
                    />
                  ) : (
                    <div key={a.id} className="flex items-center gap-2 rounded-lg border border-line bg-sunken/60 px-2.5 py-1.5">
                      <span className="min-w-0 flex-1">
                        <span className="block truncate font-mono text-[12px] text-ink-900" title={a.name}>
                          {a.name}
                        </span>
                        <span className="block truncate text-[11px] text-ink-500">
                          {a.kind === "repo" ? `rama ${a.detail} · ejemplo sin conectar` : a.detail} · {USERS.find((u) => u.id === a.addedBy)?.name ?? a.addedBy}
                        </span>
                      </span>
                      {!readOnly && (
                        <button onClick={() => removeAttachment(req.id, a.id)} className="btn-ghost" aria-label={`Quitar ${a.name}`}>
                          {a.kind === "repo" ? "cambiar" : "quitar"}
                        </button>
                      )}
                    </div>
                  ),
                )}
                {refreshError && kind === "repo" && <p role="alert" className="text-[12px] text-danger">{refreshError}</p>}
                {!readOnly && kind === "repo" && !items.length && <RepoConnector onConnected={(repo) => addAttachment(req.id, { kind: "repo", name: repo.htmlUrl, detail: repo.branch, repo })} />}
                {!readOnly && kind !== "repo" && (kind === "sql" || !items.length) && (
                  <label className="inline-flex cursor-pointer items-center gap-2 rounded-md border border-dashed border-line-strong px-3 py-1.5 text-[12px] text-ink-700 transition hover:border-accent hover:text-accent">
                    <input type="file" accept={ACCEPT[kind]} multiple={kind === "sql"} className="sr-only" onChange={(e) => onFile(kind, e.target.files)} />
                    + adjuntar {ACCEPT[kind]}
                  </label>
                )}
              </div>
            );
          })}
        </div>
      </section>
    </div>
  );
}
