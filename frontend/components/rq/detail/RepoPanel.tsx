"use client";

import { useState } from "react";
import { ErrorState } from "@/components/rq/AsyncState";
import { fmtDate } from "@/components/rq/ui";
import { api } from "@/lib/api/client";
import type { Repo, Requirement } from "@/lib/api/types";

const STATUS_LABEL: Record<string, string> = {
  added: "nuevo",
  modified: "modificado",
  removed: "eliminado",
  renamed: "renombrado",
};

const STATUS_CLASS: Record<string, string> = {
  added: "border-ok/30 bg-ok-soft text-ok",
  modified: "border-info/30 bg-info-soft text-info",
  removed: "border-danger/30 bg-danger-soft text-danger",
  renamed: "border-warn/30 bg-warn-soft text-warn",
};

export default function RepoPanel({
  requirement,
  onChanged,
}: {
  requirement: Requirement;
  onChanged: () => void;
}) {
  const repo = requirement.attachments?.find((a) => a.kind === "repo")?.repo ?? null;
  return (
    <section className="panel space-y-3 p-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="panel-title">Repositorio</h2>
        {repo && (
          <span className="font-mono text-[11.5px] text-ink-400">
            commit revisado {repo.headSha.slice(0, 12)}
          </span>
        )}
      </div>
      {repo ? <RepoCard repo={repo} /> : null}
      <ConnectForm requirement={requirement} connected={repo} onChanged={onChanged} />
    </section>
  );
}

function RepoCard({ repo }: { repo: Repo }) {
  const [verTodo, setVerTodo] = useState(false);
  const files = repo.files ?? [];
  const visibles = verTodo ? files : files.slice(0, 12);
  const added = files.reduce((s, f) => s + (f.additions ?? 0), 0);
  const removed = files.reduce((s, f) => s + (f.deletions ?? 0), 0);

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1 text-[13px]">
        {repo.htmlUrl ? (
          <a href={repo.htmlUrl} target="_blank" rel="noreferrer" className="text-accent hover:underline">
            {repo.fullName || repo.name}
          </a>
        ) : (
          <span className="text-ink-900">{repo.fullName || repo.name}</span>
        )}
        <span className="chip chip-neutral">{repo.branch}</span>
        <span className="text-[12px] text-ink-500">{repo.rangeLabel}</span>
        <span className="font-mono text-[11.5px] text-ok">+{added}</span>
        <span className="font-mono text-[11.5px] text-danger">−{removed}</span>
        <span className="text-[12px] text-ink-400">
          {files.length} archivo(s) · {repo.aheadBy} commit(s)
        </span>
      </div>

      {repo.filesTruncated && (
        <p className="text-[12px] text-warn">
          El cambio es muy grande y el diff se recortó: los agentes revisan lo que cabe y lo dicen
          en su informe.
        </p>
      )}

      <ul className="divide-y divide-line text-[12.5px]">
        {visibles.map((file) => (
          <li key={file.path} className="flex items-baseline gap-2 py-1.5">
            <span className={`chip shrink-0 ${STATUS_CLASS[file.status] ?? "chip-neutral"}`}>
              {STATUS_LABEL[file.status] ?? file.status}
            </span>
            <span className="min-w-0 flex-1 truncate font-mono text-ink-700">{file.path}</span>
            <span className="shrink-0 font-mono text-[11px] text-ink-400">
              +{file.additions} −{file.deletions}
            </span>
          </li>
        ))}
      </ul>
      {files.length > visibles.length && (
        <button className="btn-ghost" onClick={() => setVerTodo(true)}>
          Ver los {files.length} archivos
        </button>
      )}

      {(repo.commits ?? []).length > 0 && (
        <details className="text-[12.5px]">
          <summary className="cursor-pointer text-ink-500">Commits del rango</summary>
          <ul className="mt-2 space-y-1">
            {(repo.commits ?? []).map((commit) => (
              <li key={commit.sha} className="flex gap-2">
                <span className="shrink-0 font-mono text-[11px] text-ink-400">
                  {commit.sha.slice(0, 8)}
                </span>
                <span className="min-w-0 flex-1 text-ink-700">{commit.message}</span>
                <span className="shrink-0 text-[11.5px] text-ink-400">{commit.author}</span>
              </li>
            ))}
          </ul>
        </details>
      )}

      {repo.fetchedAt && (
        <p className="text-[11.5px] text-ink-400">Conectado el {fmtDate(repo.fetchedAt)}</p>
      )}
    </div>
  );
}

function ConnectForm({
  requirement,
  connected,
  onChanged,
}: {
  requirement: Requirement;
  connected: Repo | null;
  onChanged: () => void;
}) {
  const [abierto, setAbierto] = useState(!connected);
  const [url, setUrl] = useState("");
  const [branch, setBranch] = useState("");
  const [base, setBase] = useState("");
  const [conectando, setConectando] = useState(false);
  const [error, setError] = useState<unknown>(null);

  async function conectar(event: React.FormEvent) {
    event.preventDefault();
    if (!url.trim() || conectando) return;
    setConectando(true);
    setError(null);
    try {
      await api.requirements.connectRepo(requirement.id, {
        url: url.trim(),
        branch: branch.trim(),
        base: base.trim(),
        lastCommits: 1,
      });
      setAbierto(false);
      onChanged();
    } catch (cause) {
      setError(cause);
    } finally {
      setConectando(false);
    }
  }

  if (!abierto) {
    return (
      <button className="btn-ghost" onClick={() => setAbierto(true)}>
        Conectar otra rama o commit
      </button>
    );
  }

  return (
    <form className="space-y-2 border-t border-line pt-3" onSubmit={conectar}>
      <p className="text-[12px] text-ink-500">
        El servidor clona el repositorio y calcula el diff. Para uno privado, la credencial se
        configura en el servidor: aquí no se escribe ningún token.
      </p>
      <input
        value={url}
        onChange={(e) => setUrl(e.target.value)}
        placeholder="https://github.com/organizacion/repositorio.git"
        className="w-full rounded-lg border border-line bg-surface px-3 py-2 font-mono text-[12.5px] outline-none focus:border-accent"
      />
      <div className="grid gap-2 sm:grid-cols-[1fr_1fr_auto]">
        <input
          value={branch}
          onChange={(e) => setBranch(e.target.value)}
          placeholder="rama del desarrollo (vacío = la principal)"
          className="rounded-lg border border-line bg-surface px-3 py-2 text-[13px] outline-none focus:border-accent"
        />
        <input
          value={base}
          onChange={(e) => setBase(e.target.value)}
          placeholder="rama base (vacío = el commit anterior)"
          className="rounded-lg border border-line bg-surface px-3 py-2 text-[13px] outline-none focus:border-accent"
        />
        <button className="btn-primary" disabled={conectando || !url.trim()}>
          {conectando ? "Clonando…" : "Conectar"}
        </button>
      </div>
      {conectando && (
        <p className="text-[12px] text-ink-500">
          Clonando y calculando el diff en el servidor. En un repositorio grande tarda un poco.
        </p>
      )}
      {error !== null && <ErrorState error={error} title="No se pudo conectar el repositorio" />}
    </form>
  );
}
