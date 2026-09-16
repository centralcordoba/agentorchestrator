"use client";

import type { RunView } from "@/lib/rq/derive";
import { IDENTIFIER_LABELS, PHI_LABELS, SAFEGUARDS, WHERE_LABELS } from "@/lib/rq/privacy";
import { sortFindings } from "@/lib/rq/scenarios";
import type { Requirement, SafeguardCheck } from "@/lib/rq/types";
import { PhiBadge } from "../PhiControl";
import { FindingList, SourceNote, Stat } from "../ui";
import { Gate } from "./DeliverableTabs";

const SAFEGUARD_STATUS: Record<SafeguardCheck["status"], { label: string; icon: string; cls: string }> = {
  riesgo: { label: "En riesgo", icon: "!", cls: "border-danger/30 bg-danger-soft text-danger" },
  sin_evidencia: { label: "Sin evidencia", icon: "?", cls: "border-warn/30 bg-warn-soft text-warn" },
  cumple: { label: "Cumple", icon: "✓", cls: "border-ok/30 bg-ok-soft text-ok" },
  no_aplica: { label: "No aplica", icon: "–", cls: "chip-neutral text-ink-500" },
};
const STATUS_ORDER: SafeguardCheck["status"][] = ["riesgo", "sin_evidencia", "cumple", "no_aplica"];

export default function PrivacyTab({ req, view }: { req: Requirement; view: RunView | null }) {
  return (
    <Gate view={view} agent="privacy">
      {view && <PrivacyContent req={req} view={view} />}
    </Gate>
  );
}

function PrivacyContent({ req, view }: { req: Requirement; view: RunView }) {
  const pr = view.deliverables.privacy;
  const atRisk = pr.safeguards.filter((s) => s.status === "riesgo").length;
  const serious = pr.findings.filter((f) => f.severity === "critica" || f.severity === "alta").length;
  const safeguards = [...pr.safeguards].sort((a, b) => STATUS_ORDER.indexOf(a.status) - STATUS_ORDER.indexOf(b.status));
  const repo = view.deliverables.realRepo;

  return (
    <div className="space-y-4">
      <SourceNote real={Boolean(repo)}>
        {repo
          ? `Identificadores y hallazgos detectados con reglas sobre el diff real de ${repo.fullName}. Una salvaguarda «sin evidencia» necesita la revisión con LLM para confirmarse.`
          : "Informe del escenario de ejemplo."}
      </SourceNote>

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <div className="panel px-4 py-3">
          <div className="text-[11px] font-semibold uppercase tracking-[0.08em] text-ink-500">Clasificación</div>
          <div className="mt-2">
            <PhiBadge phi={req.phi} />
          </div>
          <div className="mt-1 text-[12px] text-ink-500">{PHI_LABELS[req.phi]}</div>
        </div>
        <Stat label="Identificadores de PHI" value={pr.detections.length} hint="los valores nunca se muestran" />
        <Stat label="Salvaguardas en riesgo" value={`${atRisk}/${pr.safeguards.length}`} hint="45 CFR 164.312" />
        <Stat label="Hallazgos graves" value={serious} hint={`${pr.findings.length} hallazgos de privacidad en total`} />
      </div>

      <section className="panel" aria-labelledby="sg-title">
        <div className="panel-title">
          <span id="sg-title">Salvaguardas técnicas · 45 CFR 164.312</span>
          <span className="normal-case tracking-normal text-ink-400">ordenadas por riesgo</span>
        </div>
        <ul className="divide-y divide-line">
          {safeguards.map((sg) => {
            const meta = SAFEGUARDS.find((x) => x.id === sg.id)!;
            const st = SAFEGUARD_STATUS[sg.status];
            return (
              <li key={sg.id} className="grid gap-2 px-4 py-3 md:grid-cols-[140px_minmax(0,1fr)]">
                <span>
                  <span className={`chip ${st.cls}`}>
                    <span aria-hidden>{st.icon}</span>
                    {st.label}
                  </span>
                </span>
                <span>
                  <span className="text-[13.5px] font-medium text-ink-900">{meta.label}</span>
                  <span className="ml-2 font-mono text-[11px] text-ink-400">{meta.cfr}</span>
                  <span className="block text-[12px] text-ink-500">{meta.question}</span>
                  <span className="mt-1 block text-[13px] leading-5 text-ink-700">{sg.evidence}</span>
                </span>
              </li>
            );
          })}
        </ul>
      </section>

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
        <section className="panel" aria-labelledby="det-title">
          <div className="panel-title">
            <span id="det-title">Identificadores detectados</span>
            <span className="normal-case tracking-normal text-ink-400">Safe Harbor · 164.514(b)(2)</span>
          </div>
          {pr.detections.length ? (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[520px] text-left text-[12.5px]">
                <thead className="bg-sunken text-[11px] uppercase tracking-[0.06em] text-ink-500">
                  <tr>
                    <th scope="col" className="px-4 py-1.5 font-semibold">Tipo</th>
                    <th scope="col" className="px-4 py-1.5 font-semibold">Dónde</th>
                    <th scope="col" className="px-4 py-1.5 font-semibold">Archivo</th>
                    <th scope="col" className="px-4 py-1.5 font-semibold">Valor</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {pr.detections.map((x, i) => (
                    <tr key={`${x.file}-${x.line}-${i}`}>
                      <td className="px-4 py-2 text-ink-900">{IDENTIFIER_LABELS[x.identifier]}</td>
                      <td className="px-4 py-2">
                        <span className="chip chip-neutral">{WHERE_LABELS[x.where]}</span>
                      </td>
                      <td className="px-4 py-2 font-mono text-[11.5px]">
                        {x.url ? (
                          <a href={x.url} target="_blank" rel="noreferrer" className="text-accent hover:underline">
                            {x.file}
                            {x.line ? `:${x.line}` : ""} ↗
                          </a>
                        ) : (
                          <span className="text-ink-700">
                            {x.file}
                            {x.line ? `:${x.line}` : ""}
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-2 text-ink-500">
                        <span aria-hidden>🔒</span> oculto
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="px-4 py-6 text-center text-[13px] text-ink-500">No se detectaron identificadores de PHI en el cambio.</p>
          )}
          <p className="border-t border-line px-4 py-2 text-[11.5px] leading-5 text-ink-500">
            El agente informa tipo, archivo y línea. El valor no se guarda, no se envía al modelo y no aparece en la traza ni en el VTR.
          </p>
        </section>

        <section className="panel" aria-labelledby="mn-title">
          <div className="panel-title">
            <span id="mn-title">Mínimo necesario</span>
          </div>
          <p className="px-4 py-3 text-[13.5px] leading-6 text-ink-700">{pr.minimumNecessary}</p>
          <p className="border-t border-line px-4 py-2 text-[11.5px] leading-5 text-ink-500">
            HIPAA exige usar y mostrar solo la PHI imprescindible para cada finalidad (45 CFR 164.502(b)).
          </p>
        </section>
      </div>

      <section className="panel">
        <div className="panel-title">
          <span>Hallazgos de privacidad</span>
          <span className="font-mono normal-case tracking-normal text-ink-400">{pr.findings.length}</span>
        </div>
        <FindingList findings={sortFindings(pr.findings)} empty="Sin hallazgos de privacidad." />
      </section>
    </div>
  );
}
