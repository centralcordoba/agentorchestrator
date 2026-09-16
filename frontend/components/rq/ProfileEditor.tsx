"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { AGENTS, MODEL_CATALOG, PROVIDER_BAA, PROVIDER_LABELS, modelInfo } from "@/lib/rq/agents";
import { AGENT_CARDS, can, missingPermissionText } from "@/lib/rq/governance";
import { USERS } from "@/lib/rq/mockData";
import { handlesPhi } from "@/lib/rq/privacy";
import { useRq } from "@/lib/rq/store";
import type { AgentId, AgentProfile, ProviderId } from "@/lib/rq/types";
import { fmtDate } from "./ui";

interface Props {
  agentId: AgentId;
  requirementId?: string;
  runningSnapshotVersion?: number;
  compact?: boolean;
}

type Scope = "requerimiento" | "global";

export default function ProfileEditor(props: Props) {
  const [scope, setScope] = useState<Scope>(props.requirementId ? "requerimiento" : "global");
  const effectiveScope: Scope = props.requirementId ? scope : "global";
  // El editor se remonta al cambiar de agente o de alcance para cargar el borrador correcto.
  return (
    <div className="space-y-4">
      {props.requirementId && (
        <div className="flex flex-wrap items-center gap-1.5 text-[12px]">
          <span className="text-ink-500">Guardar cambios en:</span>
          {(["requerimiento", "global"] as Scope[]).map((s) => (
            <button key={s} onClick={() => setScope(s)} className={`pill ${scope === s ? "pill-active" : "pill-idle"}`}>
              {s === "requerimiento" ? `solo ${props.requirementId}` : "predeterminado (todos)"}
            </button>
          ))}
        </div>
      )}
      <Editor key={`${props.agentId}-${effectiveScope}`} {...props} scope={effectiveScope} />
    </div>
  );
}

function Editor({ agentId, requirementId, runningSnapshotVersion, compact, scope }: Props & { scope: Scope }) {
  const { profiles, requirements, saveProfile, clearOverride, changeRequests, requestChange, currentUserId } = useRq();
  const user = USERS.find((u) => u.id === currentUserId);
  const pending = changeRequests.find((c) => c.agentId === agentId && c.status === "pendiente");
  const [createdCr, setCreatedCr] = useState<string | null>(null);
  const req = requirementId ? requirements.find((r) => r.id === requirementId) : undefined;
  const override = req?.profileOverrides[agentId];
  const source: AgentProfile = scope === "requerimiento" ? override ?? profiles[agentId] : profiles[agentId];
  const def = AGENTS[agentId];

  const [draft, setDraft] = useState(() => ({
    provider: source.provider,
    model: source.model,
    temperature: source.temperature,
    maxSteps: source.maxSteps,
    systemPrompt: source.systemPrompt,
    taskPrompt: source.taskPrompt,
  }));
  const [note, setNote] = useState("");
  const [saved, setSaved] = useState(false);
  const [testing, setTesting] = useState<"idle" | "running" | "done">("idle");
  const [showVersions, setShowVersions] = useState(false);

  const dirty =
    draft.provider !== source.provider ||
    draft.model !== source.model ||
    draft.temperature !== source.temperature ||
    draft.maxSteps !== source.maxSteps ||
    draft.systemPrompt !== source.systemPrompt ||
    draft.taskPrompt !== source.taskPrompt;
  const promptDirty = draft.systemPrompt !== source.systemPrompt || draft.taskPrompt !== source.taskPrompt;
  const variables = useMemo(() => Array.from(new Set(draft.taskPrompt.match(/\{\{\w+\}\}/g) ?? [])), [draft.taskPrompt]);
  const price = modelInfo(draft.provider, draft.model);

  const isGlobal = scope === "global";
  const MIN_JUSTIFICATION = 15;
  const canRequest = can(user, "solicitar_cambio_agente");
  const justificationOk = !isGlobal || note.trim().length >= MIN_JUSTIFICATION;
  const phiNoBaa = !isGlobal && req && handlesPhi(req) && PROVIDER_BAA[draft.provider] === false && AGENT_CARDS[agentId].receivesPhi === "redactada";

  const save = () => {
    if (isGlobal) {
      const { ...after } = draft;
      setCreatedCr(requestChange(agentId, after, note.trim()));
      setNote("");
      return;
    }
    saveProfile(agentId, { agentId, ...draft }, note, requirementId);
    setNote("");
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  const input = "w-full rounded-lg border border-line bg-surface px-2.5 py-1.5 text-[13px] outline-none focus:border-accent";

  return (
    <div className="space-y-4">
      {scope === "requerimiento" && (
        <p className="rounded-lg border border-line bg-sunken/60 px-3 py-2 text-[12px] leading-5 text-ink-500">
          {override
            ? `Este requerimiento usa una configuración propia para ${def.label}.`
            : `Este requerimiento usa la configuración predeterminada. Al guardar se crea una propia solo para ${requirementId}.`}
          {override && (
            <button className="ml-2 underline underline-offset-2 hover:text-ink-900" onClick={() => clearOverride(agentId, requirementId!)}>
              volver a la predeterminada
            </button>
          )}
        </p>
      )}
      {isGlobal && (
        <div className="rounded-lg border border-line bg-sunken/60 px-3 py-2 text-[12px] leading-5 text-ink-500">
          <span className="font-semibold text-ink-700">Control de cambios. </span>
          La configuración predeterminada afecta a todos los requerimientos: los cambios se envían como solicitud, se evalúan contra el
          conjunto de regresión y los aprueba otra persona.
        </div>
      )}
      {isGlobal && pending && !createdCr && (
        <p role="status" className="flex flex-wrap items-center gap-2 rounded-lg border border-warn/30 bg-warn-soft px-3 py-2 text-[12px] leading-5 text-warn">
          <span>
            Hay una solicitud pendiente para este agente ({pending.id}, de {USERS.find((u) => u.id === pending.createdBy)?.name}). Resuélvela antes de proponer otra.
          </span>
          <Link href={`/gobierno?cr=${pending.id}`} className="ml-auto font-semibold underline underline-offset-2">
            ver solicitud →
          </Link>
        </p>
      )}
      {createdCr && (
        <p role="status" className="flex flex-wrap items-center gap-2 rounded-lg border border-ok/30 bg-ok-soft px-3 py-2 text-[12px] leading-5 text-ok">
          <span>Solicitud {createdCr} creada. La configuración actual no cambia hasta que se apruebe.</span>
          <Link href={`/gobierno?cr=${createdCr}`} className="ml-auto font-semibold underline underline-offset-2">
            ver solicitud →
          </Link>
        </p>
      )}
      {runningSnapshotVersion !== undefined && (
        <p className="rounded-lg border border-info/30 bg-info-soft px-3 py-2 text-[12px] leading-5 text-info">
          La ejecución en curso usa prompt v{runningSnapshotVersion}. Los cambios se aplican a partir de la próxima ejecución.
        </p>
      )}

      <div className={`grid gap-3 ${compact ? "grid-cols-2" : "grid-cols-2 md:grid-cols-4"}`}>
        <label className="block">
          <span className="text-[11.5px] font-semibold text-ink-700">Proveedor</span>
          <select
            className={`${input} mt-1`}
            value={draft.provider}
            onChange={(e) => {
              const provider = e.target.value as ProviderId;
              setDraft((d) => ({ ...d, provider, model: MODEL_CATALOG[provider][0].id }));
            }}
          >
            {(Object.keys(MODEL_CATALOG) as ProviderId[]).map((p) => (
              <option key={p} value={p}>
                {PROVIDER_LABELS[p]}
                {PROVIDER_BAA[p] === true ? " · con BAA" : PROVIDER_BAA[p] === false ? " · sin BAA" : ""}
              </option>
            ))}
          </select>
        </label>
        <label className="block">
          <span className="text-[11.5px] font-semibold text-ink-700">Modelo</span>
          <select className={`${input} mt-1`} value={draft.model} onChange={(e) => setDraft((d) => ({ ...d, model: e.target.value }))}>
            {MODEL_CATALOG[draft.provider].map((m) => (
              <option key={m.id} value={m.id}>
                {m.label}
              </option>
            ))}
          </select>
        </label>
        <label className="block">
          <span className="text-[11.5px] font-semibold text-ink-700">Temperatura · {draft.temperature.toFixed(1)}</span>
          <input
            type="range"
            min={0}
            max={1}
            step={0.1}
            value={draft.temperature}
            onChange={(e) => setDraft((d) => ({ ...d, temperature: Number(e.target.value) }))}
            className="mt-2.5 w-full accent-[#C2562E]"
          />
        </label>
        <label className="block">
          <span className="text-[11.5px] font-semibold text-ink-700">Pasos máximos</span>
          <input type="number" min={1} max={30} className={`${input} mt-1`} value={draft.maxSteps} onChange={(e) => setDraft((d) => ({ ...d, maxSteps: Math.max(1, Math.min(30, Number(e.target.value) || 1)) }))} />
        </label>
      </div>
      <p className="-mt-2 font-mono text-[11px] text-ink-400">
        {draft.model} · ${price.inPerM}/M entrada · ${price.outPerM}/M salida
      </p>

      <label className="block">
        <span className="flex items-center justify-between text-[11.5px] font-semibold text-ink-700">
          <span>Prompt de sistema (rol y reglas)</span>
          <span className="font-mono font-normal text-ink-400">v{source.promptVersion}{promptDirty ? " · modificado" : ""}</span>
        </span>
        <textarea rows={compact ? 6 : 5} className={`${input} mt-1 font-mono text-[12px] leading-5`} value={draft.systemPrompt} onChange={(e) => setDraft((d) => ({ ...d, systemPrompt: e.target.value }))} />
      </label>
      <label className="block">
        <span className="text-[11.5px] font-semibold text-ink-700">Plantilla de tarea</span>
        <textarea rows={3} className={`${input} mt-1 font-mono text-[12px] leading-5`} value={draft.taskPrompt} onChange={(e) => setDraft((d) => ({ ...d, taskPrompt: e.target.value }))} />
        <span className="mt-1 flex flex-wrap gap-1">
          {variables.map((v) => (
            <span key={v} className="chip chip-neutral">
              {v}
            </span>
          ))}
        </span>
      </label>

      <div className="rounded-lg border border-line bg-sunken/60">
        <div className="flex items-center justify-between border-b border-line px-3 py-1.5 text-[11.5px] font-semibold text-ink-700">
          <span>🔒 Contrato de salida y herramientas</span>
          <span className="font-normal text-ink-400">no editable</span>
        </div>
        <div className="grid gap-3 p-3 md:grid-cols-[1fr_auto]">
          <pre className="overflow-x-auto font-mono text-[11px] leading-4 text-ink-700">{def.outputContract}</pre>
          <div className="flex flex-wrap content-start gap-1 md:max-w-[180px]">
            {def.tools.map((t) => (
              <span key={t} className="chip chip-neutral">
                {t}
              </span>
            ))}
          </div>
        </div>
        <p className="border-t border-line px-3 py-1.5 text-[11.5px] leading-5 text-ink-500">
          El esquema JSON y las reglas de validación no se editan desde aquí: si cambian, dejan de funcionar el consolidador y los guardarraíles.
        </p>
      </div>

      {phiNoBaa && (
        <p role="alert" className="rounded-lg border border-warn/30 bg-warn-soft px-3 py-2 text-[12px] leading-5 text-warn">
          {req!.id} tiene PHI y {PROVIDER_LABELS[draft.provider]} no tiene BAA: el agente solo recibirá contexto redactado. El ajuste queda
          registrado en la auditoría y aparecerá como alerta en Cumplimiento.
        </p>
      )}
      <div className="flex flex-wrap items-center gap-2">
        <label className="min-w-[200px] flex-1">
          <span className="sr-only">{isGlobal ? "Justificación del cambio" : "Nota"}</span>
          <input
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder={isGlobal ? `Justificación del cambio (obligatoria, mín. ${MIN_JUSTIFICATION} caracteres)` : promptDirty ? "Nota de la versión (qué cambiaste y por qué)" : "Nota (opcional)"}
            className={input}
          />
        </label>
        <button className="btn-ghost py-1.5 text-[12px]" disabled={testing === "running"} onClick={() => {
          setTesting("running");
          setTimeout(() => setTesting("done"), 1600);
        }}>
          {testing === "running" ? "probando…" : "Probar agente"}
        </button>
        <button
          className="btn-primary py-1.5"
          disabled={!dirty || !justificationOk || (isGlobal && (!canRequest || Boolean(pending)))}
          onClick={save}
          title={isGlobal && !canRequest ? missingPermissionText("solicitar_cambio_agente") : undefined}
        >
          {isGlobal ? "Solicitar aprobación" : saved ? "Guardado ✓" : promptDirty ? `Guardar como v${Math.max(...source.versions.map((v) => v.version)) + 1}` : "Guardar ajuste"}
        </button>
      </div>
      {isGlobal && dirty && !canRequest && <p className="text-[12px] text-warn">{missingPermissionText("solicitar_cambio_agente")}</p>}
      {testing === "done" && (
        <div className="rounded-lg border border-ok/30 bg-ok-soft px-3 py-2 text-[12px] leading-5 text-ok">
          Prueba simulada con la última ejecución: salida JSON válida, 3 pasos, {Math.round(1800 + draft.systemPrompt.length * 1.3)} tokens de entrada. Todas las citas existen en los datos.
        </div>
      )}

      <div>
        <button className="text-[12px] text-ink-500 underline decoration-line-strong underline-offset-2 hover:text-ink-900" onClick={() => setShowVersions((v) => !v)}>
          {showVersions ? "ocultar" : "ver"} historial de versiones ({source.versions.length})
        </button>
        {showVersions && (
          <ul className="mt-2 divide-y divide-line rounded-lg border border-line">
            {[...source.versions].reverse().map((v) => (
              <li key={v.version} className="flex flex-wrap items-center gap-2 px-3 py-2 text-[12px]">
                <span className="chip chip-neutral">v{v.version}</span>
                <span className="text-ink-700">{v.note}</span>
                <span className="text-ink-400">
                  {v.author} · {fmtDate(v.savedAt)}
                </span>
                {v.version === source.promptVersion ? (
                  <span className="ml-auto chip border-ok/30 bg-ok-soft text-ok">actual</span>
                ) : (
                  <button className="btn-ghost ml-auto" onClick={() => setDraft((d) => ({ ...d, systemPrompt: v.systemPrompt, taskPrompt: v.taskPrompt }))}>
                    cargar en el editor
                  </button>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
