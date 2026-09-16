"use client";

import { useState } from "react";
import type { RunView } from "@/lib/rq/derive";
import { can, missingPermissionText } from "@/lib/rq/governance";
import { USERS } from "@/lib/rq/mockData";
import { VERDICT_LABELS } from "@/lib/rq/scenarios";
import { useRq } from "@/lib/rq/store";
import type { Requirement, Verdict } from "@/lib/rq/types";
import { VerdictBadge, fmtDate } from "./ui";

const VERDICTS: Verdict[] = ["APROBADO", "APROBADO_CON_OBSERVACIONES", "RECHAZADO"];
const MIN_JUSTIFICATION = 20;

/** La IA recomienda; una persona con permiso, distinta de quien lanzó la ejecución, firma el dictamen. */
export default function SignoffPanel({ req, view }: { req: Requirement; view: RunView }) {
  const { currentUserId, signRun } = useRq();
  const user = USERS.find((u) => u.id === currentUserId);
  const aiVerdict = view.deliverables.verdict.verdict;
  const [mode, setMode] = useState<"idle" | "modificar">("idle");
  const [finalVerdict, setFinalVerdict] = useState<Verdict>(aiVerdict);
  const [comment, setComment] = useState("");
  const run = view.run;

  if (run.signoff) {
    const signer = USERS.find((u) => u.id === run.signoff!.by);
    const changed = run.signoff.decision === "modificado";
    return (
      <section className={`panel border-l-4 p-4 ${changed ? "border-l-warn" : "border-l-ok"}`} aria-label="Firma del dictamen">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-[11px] font-semibold uppercase tracking-[0.08em] text-ink-500">Dictamen firmado</span>
          <VerdictBadge verdict={run.signoff.finalVerdict} />
          {changed && (
            <span className="chip border-warn/30 bg-warn-soft text-warn">
              la IA recomendaba {VERDICT_LABELS[run.signoff.aiVerdict].toLowerCase()}
            </span>
          )}
        </div>
        <p className="mt-2 text-[13px] text-ink-700">
          <span className="font-medium text-ink-900">{signer?.name ?? run.signoff.by}</span> ({signer?.role}) · {fmtDate(run.signoff.at)}
        </p>
        {run.signoff.comment && <p className="mt-1 text-[13px] leading-5 text-ink-700">«{run.signoff.comment}»</p>}
      </section>
    );
  }

  const blockers: string[] = [];
  if (!can(user, "firmar_dictamen")) blockers.push(missingPermissionText("firmar_dictamen"));
  if (user?.id === run.startedBy) blockers.push("Quien lanzó la ejecución no puede firmar su dictamen (cuatro ojos).");
  const needsComment = mode === "modificar" || req.phi !== "no";
  const commentOk = !needsComment || comment.trim().length >= MIN_JUSTIFICATION;
  const changed = mode === "modificar" && finalVerdict !== aiVerdict;

  return (
    <section className="panel border-l-4 border-l-warn p-4" aria-labelledby="signoff-title">
      <div className="flex flex-wrap items-start gap-3">
        <div className="min-w-0 flex-1">
          <h2 id="signoff-title" className="text-[14px] font-semibold text-ink-900">
            Pendiente de firma humana
          </h2>
          <p className="text-[12.5px] leading-5 text-ink-500">
            El dictamen de la IA es una recomendación. Para que cuente en el pase a producción debe firmarlo una persona con permiso
            y distinta de quien ejecutó la revisión.
          </p>
        </div>
        <span className="chip chip-neutral">ejecutada por {USERS.find((u) => u.id === run.startedBy)?.name ?? run.startedBy}</span>
      </div>

      {blockers.length > 0 ? (
        <ul className="mt-3 space-y-1 rounded-lg border border-line bg-sunken/60 px-3 py-2 text-[12.5px] text-ink-700">
          {blockers.map((b) => (
            <li key={b}>
              <span aria-hidden>🔒 </span>
              {b}
            </li>
          ))}
          <li className="text-ink-500">Cambia de usuario arriba a la derecha para probar el flujo (p. ej. Martín Rojas o Lucía Fernández).</li>
        </ul>
      ) : (
        <div className="mt-3 space-y-3">
          <fieldset className="flex flex-wrap gap-2">
            <legend className="sr-only">Decisión</legend>
            <label className={`flex cursor-pointer items-center gap-2 rounded-lg border px-3 py-1.5 text-[13px] ${mode === "idle" ? "border-ink-700 bg-sunken" : "border-line"}`}>
              <input type="radio" checked={mode === "idle"} onChange={() => setMode("idle")} />
              Confirmar «{VERDICT_LABELS[aiVerdict]}»
            </label>
            <label className={`flex cursor-pointer items-center gap-2 rounded-lg border px-3 py-1.5 text-[13px] ${mode === "modificar" ? "border-ink-700 bg-sunken" : "border-line"}`}>
              <input type="radio" checked={mode === "modificar"} onChange={() => setMode("modificar")} />
              Cambiar el dictamen
            </label>
            {mode === "modificar" && (
              <select aria-label="Dictamen final" value={finalVerdict} onChange={(e) => setFinalVerdict(e.target.value as Verdict)} className="rounded-lg border border-line bg-surface px-2 py-1.5 text-[13px]">
                {VERDICTS.map((v) => (
                  <option key={v} value={v}>
                    {VERDICT_LABELS[v]}
                  </option>
                ))}
              </select>
            )}
          </fieldset>
          <label className="block">
            <span className="text-[12px] font-semibold text-ink-700">
              Justificación {needsComment ? <span className="text-danger">*</span> : <span className="font-normal text-ink-400">(opcional)</span>}
            </span>
            <textarea
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              rows={2}
              placeholder={mode === "modificar" ? "Por qué cambias la recomendación de la IA." : "Qué revisaste antes de firmar."}
              className="mt-1 w-full rounded-lg border border-line bg-surface px-3 py-2 text-[13px] outline-none focus:border-accent"
            />
            {needsComment && (
              <span className={`text-[11.5px] ${commentOk ? "text-ink-400" : "text-warn"}`}>
                {req.phi !== "no" && mode === "idle" ? "Requerimiento con PHI: la firma requiere justificación. " : ""}
                Mínimo {MIN_JUSTIFICATION} caracteres ({comment.trim().length}).
              </span>
            )}
          </label>
          <div className="flex flex-wrap items-center gap-2">
            <button
              className="btn-primary"
              disabled={!commentOk || (mode === "modificar" && !changed)}
              onClick={() => signRun(req.id, run.id, aiVerdict, mode === "modificar" ? finalVerdict : aiVerdict, comment.trim())}
            >
              {mode === "modificar" ? "Firmar con dictamen modificado" : "Firmar dictamen"}
            </button>
            {mode === "modificar" && !changed && <span className="text-[12px] text-ink-500">Elige un dictamen distinto al de la IA.</span>}
            <span className="text-[12px] text-ink-500">Firmas como {user?.name}. Queda registrado en la auditoría.</span>
          </div>
        </div>
      )}
    </section>
  );
}
