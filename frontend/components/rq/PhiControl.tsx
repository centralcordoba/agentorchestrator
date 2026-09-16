"use client";

import { useId } from "react";
import type { PhiClassification } from "@/lib/rq/types";

const OPTIONS: { value: PhiClassification; label: string; hint: string }[] = [
  { value: "si", label: "Sí", hint: "Toca datos de pacientes, afiliados, historia clínica o facturación médica." },
  { value: "desconocido", label: "No lo sé", hint: "Se aplica la política de PHI hasta que alguien lo confirme." },
  { value: "no", label: "No", hint: "Confirmo que el cambio no maneja información de salud." },
];

/** Selector de clasificación PHI con radios nativos (teclado y lectores de pantalla sin trabajo extra). */
export function PhiSelector({
  value,
  onChange,
  disabled,
  compact,
}: {
  value: PhiClassification | null;
  onChange: (v: PhiClassification) => void;
  disabled?: boolean;
  compact?: boolean;
}) {
  const name = useId();
  return (
    <fieldset disabled={disabled} className="space-y-2">
      <legend className="text-[12px] font-semibold text-ink-700">
        ¿Puede tocar información de salud protegida (PHI)? <span className="font-normal text-danger">*</span>
      </legend>
      <div className="grid gap-2 sm:grid-cols-3">
        {OPTIONS.map((o) => {
          const checked = value === o.value;
          return (
            <label
              key={o.value}
              className={`flex cursor-pointer gap-2 rounded-lg border px-3 py-2 transition focus-within:ring-2 focus-within:ring-accent-ring ${
                checked ? (o.value === "no" ? "border-ink-700 bg-sunken" : "border-teal bg-teal-soft") : "border-line bg-surface hover:border-line-strong"
              } ${disabled ? "cursor-not-allowed opacity-60" : ""}`}
            >
              <input type="radio" name={name} value={o.value} checked={checked} onChange={() => onChange(o.value)} className="mt-0.5 accent-[#0F6E6E]" />
              <span>
                <span className="block text-[13px] font-medium text-ink-900">{o.label}</span>
                {!compact && <span className="block text-[11.5px] leading-4 text-ink-500">{o.hint}</span>}
              </span>
            </label>
          );
        })}
      </div>
    </fieldset>
  );
}

export function PhiBadge({ phi }: { phi: PhiClassification }) {
  if (phi === "no") return <span className="chip chip-neutral text-ink-500" title="Clasificado sin PHI">sin PHI</span>;
  return (
    <span
      className={`chip ${phi === "si" ? "border-teal/30 bg-teal-soft text-teal" : "border-warn/30 bg-warn-soft text-warn"}`}
      title={phi === "si" ? "Maneja información de salud protegida" : "Sin clasificar: se trata como PHI"}
    >
      <span aria-hidden>⛨</span>
      {phi === "si" ? "PHI" : "PHI sin confirmar"}
    </span>
  );
}

export const PHI_POLICY = [
  "Privacidad HIPAA pasa a ser obligatorio en el plan.",
  "Antes de cada llamada a un modelo se redactan los identificadores de pacientes.",
  "El dictamen no puede ser «Aprobado» sin la revisión de Privacidad.",
  "El VTR incluye la sección «Impacto en PHI y controles HIPAA».",
];
