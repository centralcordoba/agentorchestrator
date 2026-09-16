"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { AgentBoard, ConnectionBadge, LiveTrace } from "@/components/rq/LiveRun";
import { FlowGraph } from "@/components/rq/FlowGraph";
import { ErrorState, SimulatedNotice } from "@/components/rq/AsyncState";
import { VerdictBadge, fmtDate, fmtTokens, fmtUsd } from "@/components/rq/ui";
import { api, errorMessage } from "@/lib/api/client";
import type { RunDetail } from "@/lib/api/types";
import { useResource } from "@/lib/api/useResource";
import { useRunStream } from "@/lib/api/useRunStream";

export default function RunPage() {
  return (
    <Suspense fallback={null}>
      <LiveRunView />
    </Suspense>
  );
}

function LiveRunView() {
  const params = useSearchParams();
  const router = useRouter();
  const runId = params.get("run") ?? "";
  const stream = useRunStream(runId || null);
  const [cancelling, setCancelling] = useState(false);
  const [cancelError, setCancelError] = useState<unknown>(null);

  // Al terminar se piden los entregables: el canal trae la traza, no los informes.
  const finished = stream.status === "terminada";
  const detail = useResource<RunDetail>(
    finished ? `run:${runId}` : null,
    () => api.runs.get(runId),
    { enabled: finished },
  );

  useEffect(() => {
    if (!runId) router.replace("/");
  }, [runId, router]);

  if (!runId) return null;

  const run = stream.run;
  const verdict = detail.data?.deliverables?.verdict ?? null;
  const usage = run?.usage;
  const enCurso = run?.status === "en_curso" && stream.status !== "terminada";

  async function cancel() {
    if (cancelling) return;
    setCancelling(true);
    setCancelError(null);
    try {
      await api.runs.cancel(runId, "usuario");
    } catch (error) {
      setCancelError(error);
    } finally {
      setCancelling(false);
    }
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-[12px] text-ink-500">
            <Link href="/" className="hover:text-accent">
              Requerimientos
            </Link>
            {run && (
              <>
                {" · "}
                <Link
                  href={`/requerimiento?id=${run.requirementId}`}
                  className="font-mono text-accent hover:underline"
                >
                  {run.requirementId}
                </Link>
              </>
            )}
          </p>
          <h1 className="font-serif text-[26px] leading-tight text-ink-900">
            Ejecución <span className="font-mono text-[20px] text-accent">{runId}</span>
          </h1>
          {run && (
            <p className="mt-1 text-[13px] text-ink-500">
              lanzada por {run.startedBy} · {fmtDate(run.startedAt)}
            </p>
          )}
        </div>
        <div className="flex items-center gap-2">
          <ConnectionBadge stream={stream} />
          {enCurso && (
            <button className="btn-ghost" onClick={cancel} disabled={cancelling}>
              {cancelling ? "Cancelando…" : "Cancelar ejecución"}
            </button>
          )}
        </div>
      </div>

      {stream.status === "error" && (
        <ErrorState
          error={new Error(stream.error ?? "No se pudo abrir el canal en vivo.")}
          title="Sin canal en vivo"
        />
      )}
      {cancelError !== null && (
        <ErrorState error={cancelError} title="No se pudo cancelar la ejecución" />
      )}

      {run && (
        <div className="grid gap-3 sm:grid-cols-3">
          <div className="panel px-4 py-3">
            <p className="text-[11px] uppercase tracking-[0.06em] text-ink-500">Estado</p>
            <p className="mt-1 text-[15px] text-ink-900">
              {stream.finalStatus ?? run.status}
            </p>
          </div>
          <div className="panel px-4 py-3">
            <p className="text-[11px] uppercase tracking-[0.06em] text-ink-500">Consumo</p>
            <p className="mt-1 text-[15px] text-ink-900">
              {fmtTokens((usage?.tokensIn ?? 0) + (usage?.tokensOut ?? 0))} tokens ·{" "}
              {fmtUsd(usage?.costUsd ?? 0)}
            </p>
          </div>
          <div className="panel px-4 py-3">
            <p className="text-[11px] uppercase tracking-[0.06em] text-ink-500">Dictamen</p>
            <p className="mt-1">
              {verdict ? (
                <VerdictBadge verdict={verdict.verdict as never} />
              ) : (
                <span className="text-[13px] text-ink-400">
                  {finished ? "sin dictamen" : "en curso…"}
                </span>
              )}
            </p>
          </div>
        </div>
      )}

      <SimulatedNotice provider={Object.values(run?.profiles ?? {})[0]?.provider} />

      <section className="space-y-2">
        <h2 className="panel-title">Flujo</h2>
        <FlowGraph stream={stream} />
      </section>

      <section className="space-y-2">
        <h2 className="panel-title">Agentes</h2>
        <AgentBoard stream={stream} />
      </section>

      <section className="space-y-2">
        <h2 className="panel-title">
          Traza <span className="text-[12px] font-normal text-ink-400">({stream.events.length} eventos)</span>
        </h2>
        <LiveTrace stream={stream} />
      </section>

      {finished && verdict && (
        <section className="space-y-2">
          <h2 className="panel-title">Dictamen</h2>
          <div className="panel space-y-2 px-4 py-3 text-[13px]">
            <p className="text-ink-900">{verdict.rationale}</p>
            {(verdict.guardrails ?? []).length > 0 && (
              <ul className="list-disc space-y-1 pl-5 text-[12px] text-accent">
                {(verdict.guardrails ?? []).map((guardrail) => (
                  <li key={guardrail}>{guardrail}</li>
                ))}
              </ul>
            )}
            {detail.error !== null && (
              <p className="text-[12px] text-ink-500">{errorMessage(detail.error)}</p>
            )}
          </div>
        </section>
      )}
    </div>
  );
}
