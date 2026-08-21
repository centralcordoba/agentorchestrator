"use client";

import { useEffect, useState } from "react";
import { AGENT_MODE_LABELS, PACE_OPTIONS, type AgentMode } from "@/lib/types";

// Presets válidos tanto con datos simulados como reales (Yahoo Finance).
const PRESETS: { label: string; symbols: string[]; hint: string }[] = [
  {
    label: "Cartera big tech",
    symbols: ["AAPL", "MSFT", "NVDA", "AMZN", "META"],
    hint: "Flujo completo: cinco símbolos analizados en paralelo",
  },
  {
    label: "Discrepancias y errores",
    symbols: ["TSLA", "META", "XYZ123"],
    hint: "TSLA: riesgo alto y reto del escéptico · META: el técnico concede · XYZ123: símbolo inexistente → NO_ANALIZABLE",
  },
];

interface Props {
  busy: boolean;
  maxSymbols: number;
  /** Retardo por mensaje por defecto del servidor (ms). */
  defaultDelayMs: number;
  /** Modo de agentes por defecto del servidor. */
  defaultMode: AgentMode;
  llmSupportsTools: boolean;
  onSubmit: (symbols: string[], messageDelayMs: number, agentMode: AgentMode) => void;
  rejected?: Record<string, string>;
  error?: string | null;
}

function Segmented<T extends string>({
  value,
  options,
  onChange,
  label,
  columns,
}: {
  value: T;
  options: { value: T; label: string; hint: string; disabled?: boolean }[];
  onChange: (v: T) => void;
  label: string;
  columns: number;
}) {
  return (
    <div role="radiogroup" aria-label={label} className="grid gap-1 rounded-lg border border-line bg-sunken p-1" style={{ gridTemplateColumns: `repeat(${columns}, minmax(0, 1fr))` }}>
      {options.map((o) => {
        const active = o.value === value;
        return (
          <button
            key={o.value}
            type="button"
            role="radio"
            aria-checked={active}
            title={o.hint}
            disabled={o.disabled}
            onClick={() => onChange(o.value)}
            className={`rounded-md px-1 py-1 text-[11px] font-medium transition disabled:cursor-not-allowed disabled:opacity-40 ${
              active ? "bg-surface text-ink-900 shadow-panel" : "text-ink-500 hover:text-ink-900"
            }`}
          >
            {o.label}
          </button>
        );
      })}
    </div>
  );
}

export default function AnalysisForm({ busy, maxSymbols, defaultDelayMs, defaultMode, llmSupportsTools, onSubmit, rejected, error }: Props) {
  const [value, setValue] = useState(PRESETS[0].symbols.join(", "));
  const [delay, setDelay] = useState<number>(defaultDelayMs);
  const [mode, setMode] = useState<AgentMode>(defaultMode);

  // Si la configuración del servidor llega después del primer render, adoptamos sus valores por defecto.
  useEffect(() => setDelay(defaultDelayMs), [defaultDelayMs]);
  useEffect(() => setMode(defaultMode), [defaultMode]);

  const parse = (raw: string) =>
    raw
      .split(/[\s,;]+/)
      .map((s) => s.trim().toUpperCase())
      .filter(Boolean);

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    const symbols = parse(value);
    if (symbols.length) onSubmit(symbols, delay, mode);
  };

  const count = parse(value).length;
  const overLimit = count > maxSymbols;

  return (
    <form onSubmit={submit} className="panel p-4">
      <label htmlFor="symbols" className="mb-2 block text-[11px] font-semibold uppercase tracking-[0.08em] text-ink-500">
        Símbolos a analizar
      </label>
      <textarea
        id="symbols"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        rows={2}
        spellCheck={false}
        className="w-full resize-none rounded-lg border border-line bg-sunken px-3 py-2 font-mono text-[13px] text-ink-900 outline-none transition placeholder:text-ink-300 focus:border-accent focus:bg-surface focus:ring-2 focus:ring-accent-ring"
        placeholder="AAPL, MSFT, NVDA"
      />
      <div className="mt-1.5 flex items-center justify-between text-[11px] text-ink-400">
        <span className={overLimit ? "text-danger" : ""}>
          {count} símbolo{count === 1 ? "" : "s"} · máx. {maxSymbols}
        </span>
        <span>coma o espacio</span>
      </div>

      <div className="mt-3 flex flex-wrap gap-1.5">
        {PRESETS.map((p) => (
          <button key={p.label} type="button" title={p.hint} onClick={() => setValue(p.symbols.join(", "))} className="btn-ghost">
            {p.label}
          </button>
        ))}
      </div>

      <div className="mt-4">
        <div className="mb-1.5 text-[11px] font-semibold uppercase tracking-[0.08em] text-ink-500">Agentes</div>
        <Segmented
          label="Modo de los agentes"
          value={mode}
          columns={2}
          onChange={setMode}
          options={[
            { value: "rules", label: AGENT_MODE_LABELS.rules.label, hint: AGENT_MODE_LABELS.rules.hint },
            {
              value: "llm",
              label: AGENT_MODE_LABELS.llm.label,
              hint: llmSupportsTools ? AGENT_MODE_LABELS.llm.hint : "El proveedor LLM actual no soporta herramientas",
              disabled: !llmSupportsTools,
            },
          ]}
        />
        <p className="mt-1.5 text-[11px] leading-4 text-ink-400">{AGENT_MODE_LABELS[mode].hint}.</p>
      </div>

      <div className="mt-4">
        <div className="mb-1.5 flex items-baseline justify-between">
          <span className="text-[11px] font-semibold uppercase tracking-[0.08em] text-ink-500">Ritmo</span>
          <span className="whitespace-nowrap font-mono text-[11px] text-ink-400">{delay} ms / mensaje</span>
        </div>
        <Segmented
          label="Ritmo de la comunicación"
          value={String(delay)}
          columns={4}
          onChange={(v) => setDelay(Number(v))}
          options={PACE_OPTIONS.map((p) => ({ value: String(p.ms), label: p.label, hint: p.hint }))}
        />
        <p className="mt-1.5 text-[11px] leading-4 text-ink-400">Retardo añadido a cada mensaje entre agentes para poder seguir el flujo en el grafo.</p>
      </div>

      <button type="submit" disabled={busy || count === 0} className="btn-primary mt-4 w-full">
        {busy ? "Ejecutando…" : "Iniciar ejecución"}
      </button>

      {error && <p className="mt-3 rounded-lg border border-danger/30 bg-danger-soft p-2.5 text-[12px] text-danger">{error}</p>}
      {rejected && Object.keys(rejected).length > 0 && (
        <ul className="mt-3 space-y-1 rounded-lg border border-warn/30 bg-warn-soft p-2.5 text-[12px] text-warn">
          {Object.entries(rejected).map(([sym, why]) => (
            <li key={sym}>
              <span className="font-mono font-semibold">{sym}</span> · {why}
            </li>
          ))}
        </ul>
      )}
    </form>
  );
}
