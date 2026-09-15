"use client";

import { useState } from "react";
import { GitHubError, connectRepo, fetchRepoMeta, languageSummary, parseRepoUrl, type CompareMode, type RepoMeta } from "@/lib/rq/github";
import type { RepoInfo } from "@/lib/rq/types";
import { fmtDate } from "./ui";

const input = "rounded-md border border-line bg-surface px-2 py-1.5 text-[12px] outline-none focus:border-accent disabled:opacity-60";

const EXAMPLES = ["expressjs/express", "pallets/flask", "spring-projects/spring-petclinic"];

export function RepoConnector({ initialUrl = "", onConnected }: { initialUrl?: string; onConnected: (repo: RepoInfo) => void }) {
  const [url, setUrl] = useState(initialUrl);
  const [meta, setMeta] = useState<RepoMeta | null>(null);
  const [busy, setBusy] = useState<"meta" | "compare" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [branch, setBranch] = useState("");
  const [modeKind, setModeKind] = useState<CompareMode["kind"]>("commits");
  const [base, setBase] = useState("");
  const [count, setCount] = useState(5);

  const verify = async (value = url) => {
    const parsed = parseRepoUrl(value);
    if (!parsed) {
      setError("Formato no reconocido. Usa https://github.com/propietario/repositorio o propietario/repositorio.");
      return;
    }
    setBusy("meta");
    setError(null);
    setMeta(null);
    try {
      const m = await fetchRepoMeta(parsed.owner, parsed.name);
      setMeta(m);
      setBranch(m.defaultBranch);
      setBase(m.defaultBranch);
      setModeKind("commits");
    } catch (e) {
      setError(e instanceof GitHubError ? e.message : "Error inesperado al consultar GitHub.");
    } finally {
      setBusy(null);
    }
  };

  const connect = async () => {
    if (!meta) return;
    setBusy("compare");
    setError(null);
    try {
      const mode: CompareMode = modeKind === "base" ? { kind: "base", base } : { kind: "commits", count };
      onConnected(await connectRepo(meta, branch, mode));
    } catch (e) {
      setError(e instanceof GitHubError ? e.message : "Error inesperado al obtener el diff.");
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="space-y-2">
      <form
        className="flex flex-wrap gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          verify();
        }}
      >
        <input
          value={url}
          onChange={(e) => {
            setUrl(e.target.value);
            setMeta(null);
          }}
          placeholder="https://github.com/propietario/repositorio"
          aria-label="URL del repositorio de GitHub"
          className={`${input} min-w-0 flex-1 font-mono`}
          disabled={busy !== null}
        />
        <button className="btn-ghost" type="submit" disabled={busy !== null || !url.trim()}>
          {busy === "meta" ? "verificando…" : "verificar"}
        </button>
      </form>
      {!meta && !busy && (
        <p className="flex flex-wrap items-center gap-1 text-[11.5px] text-ink-400">
          Solo repositorios públicos de GitHub. Ejemplos:
          {EXAMPLES.map((ex) => (
            <button
              key={ex}
              className="chip chip-neutral hover:border-line-strong"
              onClick={() => {
                setUrl(`https://github.com/${ex}`);
                verify(ex);
              }}
            >
              {ex}
            </button>
          ))}
        </p>
      )}

      {meta && (
        <div className="space-y-2.5 rounded-lg border border-line bg-sunken/60 p-2.5">
          <div>
            <a href={meta.htmlUrl} target="_blank" rel="noreferrer" className="font-mono text-[12.5px] font-semibold text-ink-900 hover:underline">
              {meta.fullName}
            </a>
            <span className="ml-2 text-[11px] text-ink-400">★ {meta.stars.toLocaleString("es-ES")}</span>
            {meta.description && <p className="text-[12px] leading-5 text-ink-500">{meta.description}</p>}
            <p className="font-mono text-[11px] text-ink-400">{languageSummary(meta.languages)}</p>
          </div>
          <label className="block text-[11.5px] font-semibold text-ink-700">
            Rama del desarrollo
            <select value={branch} onChange={(e) => setBranch(e.target.value)} className={`${input} mt-1 block w-full font-mono`}>
              {meta.branches.map((b) => (
                <option key={b} value={b}>
                  {b}
                  {b === meta.defaultBranch ? " (principal)" : ""}
                </option>
              ))}
            </select>
          </label>
          <fieldset className="space-y-1.5 text-[12px] text-ink-700">
            <legend className="mb-1 text-[11.5px] font-semibold">Qué cambios revisar</legend>
            <label className="flex flex-wrap items-center gap-2">
              <input type="radio" checked={modeKind === "commits"} onChange={() => setModeKind("commits")} />
              últimos
              <input type="number" min={1} max={30} value={count} onChange={(e) => setCount(Math.max(1, Math.min(30, Number(e.target.value) || 1)))} className={`${input} w-16`} disabled={modeKind !== "commits"} />
              commits de la rama
            </label>
            <label className="flex flex-wrap items-center gap-2">
              <input type="radio" checked={modeKind === "base"} onChange={() => setModeKind("base")} />
              diferencias contra la rama
              <select value={base} onChange={(e) => setBase(e.target.value)} className={`${input} font-mono`} disabled={modeKind !== "base"}>
                {meta.branches.map((b) => (
                  <option key={b} value={b}>
                    {b}
                  </option>
                ))}
              </select>
            </label>
          </fieldset>
          <button className="btn-primary w-full py-1.5" onClick={connect} disabled={busy !== null || (modeKind === "base" && base === branch)}>
            {busy === "compare" ? "obteniendo diff…" : "Conectar repositorio"}
          </button>
          {modeKind === "base" && base === branch && <p className="text-[11.5px] text-warn">La rama base debe ser distinta de la rama del desarrollo.</p>}
        </div>
      )}

      {error && (
        <p role="alert" className="rounded-md border border-danger/30 bg-danger-soft px-2.5 py-1.5 text-[12px] leading-5 text-danger">
          {error}
        </p>
      )}
    </div>
  );
}

const STATUS_LABEL = { added: "nuevo", modified: "mod.", removed: "elim.", renamed: "renom." } as const;

export function RepoCard({ repo, onRefresh, onRemove, busy, readOnly }: { repo: RepoInfo; onRefresh: () => void; onRemove: () => void; busy: boolean; readOnly: boolean }) {
  const [open, setOpen] = useState<"archivos" | "commits" | null>(null);
  const added = repo.files.reduce((s, f) => s + f.additions, 0);
  const removed = repo.files.reduce((s, f) => s + f.deletions, 0);

  return (
    <div className="space-y-2 rounded-lg border border-line bg-sunken/60 p-2.5">
      <div className="flex flex-wrap items-start gap-2">
        <div className="min-w-0 flex-1">
          <a href={repo.htmlUrl} target="_blank" rel="noreferrer" className="font-mono text-[12.5px] font-semibold text-ink-900 hover:underline">
            {repo.fullName}
          </a>
          <span className="ml-1.5 chip border-ok/30 bg-ok-soft text-ok">conectado</span>
          <p className="font-mono text-[11px] text-ink-500">
            rama {repo.branch} · {repo.rangeLabel}
          </p>
        </div>
        {!readOnly && (
          <span className="flex gap-1">
            <button className="btn-ghost" onClick={onRefresh} disabled={busy}>
              {busy ? "actualizando…" : "actualizar"}
            </button>
            <button className="btn-ghost" onClick={onRemove} disabled={busy}>
              cambiar
            </button>
          </span>
        )}
      </div>
      <div className="flex flex-wrap gap-x-3 gap-y-1 font-mono text-[11.5px] text-ink-700">
        <span>{repo.aheadBy} commits</span>
        <span>
          {repo.files.length}
          {repo.filesTruncated ? "+" : ""} archivos
        </span>
        <span>
          <span className="text-ok">+{added}</span> <span className="text-danger">−{removed}</span>
        </span>
        <span>{repo.findings.length} hallazgos por reglas</span>
        <a href={repo.compareUrl} target="_blank" rel="noreferrer" className="text-accent hover:underline">
          ver diff en GitHub ↗
        </a>
      </div>
      <p className="text-[11px] text-ink-400">
        {languageSummary(repo.languages)} · leído {fmtDate(repo.fetchedAt)}
      </p>
      <div className="flex gap-1">
        {(["archivos", "commits"] as const).map((k) => (
          <button key={k} className={`pill ${open === k ? "pill-active" : "pill-idle"}`} onClick={() => setOpen(open === k ? null : k)}>
            {k}
          </button>
        ))}
      </div>
      {open === "archivos" && (
        <ul className="max-h-56 divide-y divide-line overflow-y-auto rounded-md border border-line bg-surface">
          {repo.files.map((f) => (
            <li key={f.path} className="flex items-center gap-2 px-2 py-1 font-mono text-[11px]">
              <span className="w-11 shrink-0 text-ink-400">{STATUS_LABEL[f.status]}</span>
              <span className="min-w-0 flex-1 truncate text-ink-900" title={f.path}>
                {f.path}
              </span>
              <span className="text-ok">+{f.additions}</span>
              <span className="text-danger">−{f.deletions}</span>
            </li>
          ))}
        </ul>
      )}
      {open === "commits" && (
        <ul className="max-h-56 divide-y divide-line overflow-y-auto rounded-md border border-line bg-surface">
          {repo.commits.map((c) => (
            <li key={c.sha} className="px-2 py-1.5 text-[11.5px]">
              <a href={c.url} target="_blank" rel="noreferrer" className="font-mono text-accent hover:underline">
                {c.sha.slice(0, 7)}
              </a>{" "}
              <span className="text-ink-900">{c.message}</span>
              <span className="block text-[10.5px] text-ink-400">
                {c.author} · {c.date ? fmtDate(c.date) : ""}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
