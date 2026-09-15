"use client";

import { AGENTS } from "@/lib/rq/agents";
import { SEVERITY_LABELS, VERDICT_LABELS } from "@/lib/rq/scenarios";
import type { AgentId, AgentRunStatus, AppUser, Finding, Severity, Verdict } from "@/lib/rq/types";

export function fmtUsd(v: number): string {
  if (v === 0) return "$0";
  return v < 0.01 ? `$${v.toFixed(4)}` : `$${v.toFixed(v < 1 ? 3 : 2)}`;
}

export function fmtTokens(v: number): string {
  return v >= 1_000_000 ? `${(v / 1_000_000).toFixed(1)}M` : v >= 1000 ? `${(v / 1000).toFixed(1)}k` : String(v);
}

export function fmtDate(iso: string | number): string {
  const d = new Date(iso);
  return d.toLocaleString("es-ES", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });
}

export function fmtDuration(ms: number): string {
  const s = Math.max(0, Math.round(ms / 1000));
  return s < 60 ? `${s} s` : `${Math.floor(s / 60)} min ${s % 60} s`;
}

export function Tabs<T extends string>({
  tabs,
  value,
  onChange,
}: {
  tabs: { id: T; label: string; badge?: React.ReactNode; hidden?: boolean }[];
  value: T;
  onChange: (t: T) => void;
}) {
  return (
    <div className="-mx-4 overflow-x-auto px-4 sm:mx-0 sm:px-0">
      <div role="tablist" className="flex min-w-max gap-1 border-b border-line">
        {tabs
          .filter((t) => !t.hidden)
          .map((t) => {
            const active = t.id === value;
            return (
              <button
                key={t.id}
                role="tab"
                aria-selected={active}
                onClick={() => onChange(t.id)}
                className={`-mb-px inline-flex items-center gap-1.5 border-b-2 px-3 py-2 text-[13px] transition ${
                  active ? "border-accent font-semibold text-ink-900" : "border-transparent text-ink-500 hover:text-ink-900"
                }`}
              >
                {t.label}
                {t.badge}
              </button>
            );
          })}
      </div>
    </div>
  );
}

const SEV_CLASS: Record<Severity, string> = {
  critica: "border-danger/30 bg-danger-soft text-danger",
  alta: "border-rose/30 bg-rose-soft text-rose",
  media: "border-warn/30 bg-warn-soft text-warn",
  baja: "border-info/30 bg-info-soft text-info",
  info: "border-line bg-sunken text-ink-500",
};

const SEV_ICON: Record<Severity, string> = { critica: "⛔", alta: "▲", media: "●", baja: "▽", info: "i" };

export function SeverityBadge({ severity }: { severity: Severity }) {
  return (
    <span className={`chip ${SEV_CLASS[severity]}`}>
      <span aria-hidden>{SEV_ICON[severity]}</span>
      {SEVERITY_LABELS[severity]}
    </span>
  );
}

const VERDICT_CLASS: Record<Verdict, string> = {
  APROBADO: "border-ok/30 bg-ok-soft text-ok",
  APROBADO_CON_OBSERVACIONES: "border-warn/30 bg-warn-soft text-warn",
  RECHAZADO: "border-danger/30 bg-danger-soft text-danger",
};
const VERDICT_ICON: Record<Verdict, string> = { APROBADO: "✓", APROBADO_CON_OBSERVACIONES: "!", RECHAZADO: "✕" };

export function VerdictBadge({ verdict, large = false }: { verdict: Verdict; large?: boolean }) {
  return (
    <span className={`chip ${VERDICT_CLASS[verdict]} ${large ? "px-2.5 py-1 text-[13px] font-semibold" : ""}`}>
      <span aria-hidden>{VERDICT_ICON[verdict]}</span>
      {VERDICT_LABELS[verdict]}
    </span>
  );
}

const STATUS_CLASS: Record<AgentRunStatus, string> = {
  pendiente: "bg-ink-300",
  trabajando: "bg-info",
  completado: "bg-ok",
  omitido: "bg-line-strong",
};

export function StatusDot({ status }: { status: AgentRunStatus }) {
  return (
    <span className="relative inline-flex h-2 w-2">
      {status === "trabajando" && <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-info opacity-50" />}
      <span className={`relative inline-flex h-2 w-2 rounded-full ${STATUS_CLASS[status]}`} />
    </span>
  );
}

export function AgentChip({ id, dim = false }: { id: AgentId; dim?: boolean }) {
  const a = AGENTS[id];
  return (
    <span
      className={`chip border-transparent ${dim ? "opacity-50" : ""}`}
      style={{ background: a.soft, color: a.color }}
      title={a.role}
    >
      {a.label}
    </span>
  );
}

export function Avatar({ user, size = 28, online }: { user: AppUser; size?: number; online?: boolean }) {
  return (
    <span className="relative inline-flex shrink-0" style={{ width: size, height: size }}>
      <span
        className="inline-flex h-full w-full items-center justify-center rounded-full bg-sunken font-mono text-[10.5px] font-semibold text-ink-700 ring-1 ring-line"
        aria-hidden
      >
        {user.initials}
      </span>
      {online !== undefined && (
        <span
          className={`absolute -bottom-0.5 -right-0.5 h-2.5 w-2.5 rounded-full ring-2 ring-surface ${online ? "bg-ok" : "bg-ink-300"}`}
          title={online ? "en línea" : "ausente"}
        />
      )}
    </span>
  );
}

export function FindingList({ findings, empty = "Sin hallazgos." }: { findings: Finding[]; empty?: string }) {
  if (!findings.length) return <p className="px-4 py-6 text-center text-[13px] text-ink-500">{empty}</p>;
  return (
    <ul className="divide-y divide-line">
      {findings.map((f) => (
        <li key={`${f.source}-${f.id}`} className="px-4 py-3">
          <div className="flex flex-wrap items-center gap-2">
            <SeverityBadge severity={f.severity} />
            <span className="text-[13.5px] font-medium text-ink-900">{f.title}</span>
            <span className="ml-auto flex items-center gap-2">
              {f.file &&
                (f.url ? (
                  <a href={f.url} target="_blank" rel="noreferrer" className="font-mono text-[11px] text-accent hover:underline">
                    {f.file}
                    {f.line ? `:${f.line}` : ""} ↗
                  </a>
                ) : (
                  <span className="font-mono text-[11px] text-ink-500">
                    {f.file}
                    {f.line ? `:${f.line}` : ""}
                  </span>
                ))}
              <AgentChip id={f.source} />
            </span>
          </div>
          <p className="mt-1 text-[13px] leading-5 text-ink-700">{f.detail}</p>
          {f.suggestion && (
            <p className="mt-1 text-[12.5px] leading-5 text-ink-500">
              <span className="font-semibold text-ink-700">Sugerencia: </span>
              {f.suggestion}
            </p>
          )}
        </li>
      ))}
    </ul>
  );
}

export function EmptyState({ title, children }: { title: string; children?: React.ReactNode }) {
  return (
    <div className="panel flex flex-col items-center gap-2 px-6 py-12 text-center">
      <p className="font-serif text-[18px] text-ink-900">{title}</p>
      {children && <div className="max-w-md text-[13px] leading-5 text-ink-500">{children}</div>}
    </div>
  );
}

export function Stat({ label, value, hint }: { label: string; value: React.ReactNode; hint?: React.ReactNode }) {
  return (
    <div className="panel px-4 py-3">
      <div className="text-[11px] font-semibold uppercase tracking-[0.08em] text-ink-500">{label}</div>
      <div className="mt-1 font-serif text-[24px] leading-tight text-ink-900">{value}</div>
      {hint && <div className="mt-0.5 text-[12px] text-ink-500">{hint}</div>}
    </div>
  );
}

export function SourceNote({ real, children }: { real: boolean; children: React.ReactNode }) {
  return (
    <p
      className={`rounded-lg border px-3 py-2 text-[12px] leading-5 ${
        real ? "border-ok/30 bg-ok-soft text-ok" : "border-warn/30 bg-warn-soft text-warn"
      }`}
    >
      <span className="font-semibold">{real ? "Datos reales. " : "Ejemplo simulado. "}</span>
      {children}
    </p>
  );
}
