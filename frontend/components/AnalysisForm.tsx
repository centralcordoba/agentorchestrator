"use client";

import { useState } from "react";

const PRESETS: { label: string; symbols: string[]; hint: string }[] = [
  { label: "Big tech", symbols: ["AAPL", "MSFT", "NVDA", "AMZN", "META"], hint: "Flujo completo con 5 símbolos en paralelo" },
  { label: "Con discrepancias", symbols: ["META", "TSLA", "INTC"], hint: "El escéptico reta al analista técnico" },
  { label: "Con errores", symbols: ["AAPL", "XYZ123", "NODATA", "FAIL"], hint: "Símbolo desconocido, datos insuficientes y fallo del proveedor" },
];

interface Props {
  busy: boolean;
  maxSymbols: number;
  onSubmit: (symbols: string[]) => void;
  rejected?: Record<string, string>;
  error?: string | null;
}

export default function AnalysisForm({ busy, maxSymbols, onSubmit, rejected, error }: Props) {
  const [value, setValue] = useState(PRESETS[0].symbols.join(", "));

  const parse = (raw: string) =>
    raw
      .split(/[\s,;]+/)
      .map((s) => s.trim().toUpperCase())
      .filter(Boolean);

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    const symbols = parse(value);
    if (symbols.length) onSubmit(symbols);
  };

  const count = parse(value).length;

  return (
    <form onSubmit={submit} className="panel p-4">
      <label htmlFor="symbols" className="mb-1 block text-xs font-semibold uppercase tracking-wider text-slate-400">
        Símbolos a analizar
      </label>
      <textarea
        id="symbols"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        rows={2}
        spellCheck={false}
        className="w-full resize-none rounded-lg border border-ink-600 bg-ink-950 px-3 py-2 font-mono text-sm text-slate-100 outline-none focus:border-sky-500"
        placeholder="AAPL, MSFT, NVDA"
      />
      <div className="mt-1 flex items-center justify-between text-[11px] text-slate-500">
        <span>
          {count} símbolo{count === 1 ? "" : "s"} · máx. {maxSymbols}
        </span>
        <span>Separados por coma o espacio</span>
      </div>

      <div className="mt-3 flex flex-wrap gap-1.5">
        {PRESETS.map((p) => (
          <button
            key={p.label}
            type="button"
            title={p.hint}
            onClick={() => setValue(p.symbols.join(", "))}
            className="rounded-md border border-ink-600 bg-ink-800 px-2 py-1 text-[11px] text-slate-300 hover:border-sky-500 hover:text-white"
          >
            {p.label}
          </button>
        ))}
      </div>

      <button
        type="submit"
        disabled={busy || count === 0}
        className="mt-4 w-full rounded-lg bg-sky-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-sky-500 disabled:cursor-not-allowed disabled:opacity-50"
      >
        {busy ? "Ejecutando…" : "Iniciar ejecución"}
      </button>

      {error && <p className="mt-2 rounded-md border border-rose-500/40 bg-rose-500/10 p-2 text-xs text-rose-200">{error}</p>}
      {rejected && Object.keys(rejected).length > 0 && (
        <ul className="mt-2 space-y-1 text-xs text-amber-300">
          {Object.entries(rejected).map(([sym, why]) => (
            <li key={sym}>
              <span className="font-mono">{sym}</span>: {why}
            </li>
          ))}
        </ul>
      )}
    </form>
  );
}
