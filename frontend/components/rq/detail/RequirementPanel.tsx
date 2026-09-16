"use client";

import { useState } from "react";
import { PHI_POLICY, PhiBadge, PhiSelector } from "@/components/rq/PhiControl";
import { ErrorState } from "@/components/rq/AsyncState";
import RepoPanel from "@/components/rq/detail/RepoPanel";
import { fmtDate } from "@/components/rq/ui";
import { api } from "@/lib/api/client";
import type { AttachmentKind, Requirement } from "@/lib/api/types";
import type { PhiClassification } from "@/lib/rq/types";

const KINDS: { kind: AttachmentKind; label: string; placeholder: string }[] = [
  { kind: "vtr_template", label: "Plantilla VTR", placeholder: "plantilla-vtr.docx" },
  { kind: "kiuwan_csv", label: "CSV de Kiuwan", placeholder: "kiuwan-export.csv" },
  { kind: "sql", label: "Script SQL", placeholder: "migracion-001.sql" },
];

const KIND_LABEL: Record<string, string> = {
  ...Object.fromEntries(KINDS.map(({ kind, label }) => [kind, label])),
  repo: "Repositorio git",
};

export default function RequirementPanel({
  requirement,
  onChanged,
}: {
  requirement: Requirement;
  onChanged: () => void;
}) {
  return (
    <div className="grid gap-4 lg:grid-cols-[1.4fr_1fr]">
      <div className="space-y-4">
        <section className="panel space-y-3 p-4">
          <h2 className="panel-title">Descripción</h2>
          <p className="whitespace-pre-line text-[13px] leading-6 text-ink-700">
            {requirement.description || "Sin descripción."}
          </p>
        </section>

        <section className="panel space-y-2 p-4">
          <h2 className="panel-title">Criterios de aceptación</h2>
          {requirement.acceptanceCriteria?.length ? (
            <ol className="space-y-1.5 text-[13px] text-ink-700">
              {requirement.acceptanceCriteria.map((criterion, index) => (
                <li key={criterion} className="flex gap-2">
                  <span className="font-mono text-[11.5px] text-ink-400">{index + 1}.</span>
                  <span>{criterion}</span>
                </li>
              ))}
            </ol>
          ) : (
            <p className="text-[13px] text-ink-400">
              Sin criterios. Los agentes los usan para comprobar el cambio: conviene añadirlos.
            </p>
          )}
        </section>

        <RepoPanel requirement={requirement} onChanged={onChanged} />

        <AttachmentsSection requirement={requirement} onChanged={onChanged} />
      </div>

      <div className="space-y-4">
        <section className="panel space-y-2 p-4 text-[13px]">
          <h2 className="panel-title">Ficha</h2>
          <Row label="Código" value={<span className="font-mono text-accent">{requirement.id}</span>} />
          <Row label="Responsable" value={requirement.owner} />
          <Row label="Creado" value={fmtDate(requirement.createdAt)} />
          <Row label="Clasificación" value={<PhiBadge phi={requirement.phi as PhiClassification} />} />
          {requirement.phiSetBy && <Row label="Clasificado por" value={requirement.phiSetBy} />}
        </section>

        <PhiSection requirement={requirement} onChanged={onChanged} />
      </div>
    </div>
  );
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <p className="flex items-baseline justify-between gap-3">
      <span className="text-ink-500">{label}</span>
      <span className="text-right text-ink-900">{value}</span>
    </p>
  );
}

function AttachmentsSection({
  requirement,
  onChanged,
}: {
  requirement: Requirement;
  onChanged: () => void;
}) {
  const [kind, setKind] = useState<AttachmentKind>("vtr_template");
  const [name, setName] = useState("");
  const [detail, setDetail] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<unknown>(null);

  const attachments = (requirement.attachments ?? []).filter((a) => a.kind !== "repo");
  const current = KINDS.find((k) => k.kind === kind);

  async function add(event: React.FormEvent) {
    event.preventDefault();
    if (!name.trim() || saving) return;
    setSaving(true);
    setError(null);
    try {
      await api.requirements.addAttachment(requirement.id, {
        kind,
        name: name.trim(),
        detail: detail.trim(),
      });
      setName("");
      setDetail("");
      onChanged();
    } catch (cause) {
      setError(cause);
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="panel space-y-3 p-4">
      <h2 className="panel-title">Adjuntos</h2>
      {attachments.length ? (
        <ul className="divide-y divide-line text-[13px]">
          {attachments.map((attachment) => (
            <li key={attachment.id} className="flex items-baseline justify-between gap-3 py-2">
              <span>
                <span className="chip chip-neutral mr-2">
                  {KIND_LABEL[attachment.kind] ?? attachment.kind}
                </span>
                <span className="text-ink-900">{attachment.name}</span>
                {attachment.detail && (
                  <span className="ml-2 text-[12px] text-ink-500">{attachment.detail}</span>
                )}
              </span>
              <span className="shrink-0 text-[11.5px] text-ink-400">
                {fmtDate(attachment.addedAt)}
              </span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-[13px] text-ink-400">
          Sin adjuntos. Sin plantilla VTR el plan sale bloqueado.
        </p>
      )}

      <form className="grid gap-2 border-t border-line pt-3 sm:grid-cols-[auto_1fr_1fr_auto]" onSubmit={add}>
        <select
          value={kind}
          onChange={(e) => setKind(e.target.value as AttachmentKind)}
          className="rounded-lg border border-line bg-surface px-2 py-2 text-[13px] outline-none focus:border-accent"
        >
          {KINDS.map((option) => (
            <option key={option.kind} value={option.kind}>
              {option.label}
            </option>
          ))}
        </select>
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder={current?.placeholder}
          className="rounded-lg border border-line bg-surface px-3 py-2 text-[13px] outline-none focus:border-accent"
        />
        <input
          value={detail}
          onChange={(e) => setDetail(e.target.value)}
          placeholder="detalle (rama, tamaño…)"
          className="rounded-lg border border-line bg-surface px-3 py-2 text-[13px] outline-none focus:border-accent"
        />
        <button className="btn-ghost" type="submit" disabled={!name.trim() || saving}>
          {saving ? "Añadiendo…" : "Añadir"}
        </button>
      </form>
      <p className="text-[11.5px] text-ink-400">
        De momento se guarda el tipo y el nombre. La subida del archivo, con su cifrado y su
        retención, llega con ORQ-19.
      </p>
      {error !== null && <ErrorState error={error} title="No se pudo añadir el adjunto" />}
    </section>
  );
}

function PhiSection({
  requirement,
  onChanged,
}: {
  requirement: Requirement;
  onChanged: () => void;
}) {
  const [value, setValue] = useState<PhiClassification>(requirement.phi as PhiClassification);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const changed = value !== requirement.phi;

  async function save() {
    if (!changed || saving) return;
    setSaving(true);
    setError(null);
    try {
      await api.requirements.classifyPhi(requirement.id, { phi: value });
      onChanged();
    } catch (cause) {
      setError(cause);
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="panel space-y-3 p-4">
      <h2 className="panel-title">Información de salud protegida</h2>
      <PhiSelector value={value} onChange={setValue} disabled={saving} compact />
      {value !== "no" && (
        <ul className="space-y-0.5 rounded-lg border border-teal/20 bg-teal-soft/50 px-3 py-2 text-[12px] leading-5 text-teal">
          {PHI_POLICY.map((policy) => (
            <li key={policy}>• {policy}</li>
          ))}
        </ul>
      )}
      {error !== null && <ErrorState error={error} title="No se pudo guardar la clasificación" />}
      <div className="flex justify-end">
        <button className="btn-primary" onClick={save} disabled={!changed || saving}>
          {saving ? "Guardando…" : "Guardar clasificación"}
        </button>
      </div>
    </section>
  );
}
