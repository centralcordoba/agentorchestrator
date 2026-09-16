"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import {
  AsyncState,
  ErrorState,
  Loading,
  Refreshing,
  SimulatedNotice,
} from "@/components/rq/AsyncState";
import { PhiBadge } from "@/components/rq/PhiControl";
import { AgentBoard, ConnectionBadge, LiveTrace } from "@/components/rq/LiveRun";
import { FlowGraph } from "@/components/rq/FlowGraph";
import {
  CodePanel,
  KiuwanPanel,
  PrivacyPanel,
  SqlPanel,
  TestsPanel,
  UiuxPanel,
  VerdictPanel,
  VtrPanel,
} from "@/components/rq/detail/DeliverablePanels";
import PlanPanel from "@/components/rq/detail/PlanPanel";
import RequirementPanel from "@/components/rq/detail/RequirementPanel";
import { Tabs, VerdictBadge, fmtDate, fmtTokens, fmtUsd } from "@/components/rq/ui";
import { api } from "@/lib/api/client";
import type { PlanView, Requirement, RunDetail, RunPage } from "@/lib/api/types";
import { invalidate, useResource } from "@/lib/api/useResource";
import { useRunStream } from "@/lib/api/useRunStream";
import type { PhiClassification } from "@/lib/rq/types";

type TabId =
  | "requerimiento"
  | "plan"
  | "ejecucion"
  | "codigo"
  | "tests"
  | "kiuwan"
  | "sql"
  | "uiux"
  | "privacidad"
  | "vtr"
  | "dictamen";

const TABS: { id: TabId; label: string }[] = [
  { id: "requerimiento", label: "Requerimiento" },
  { id: "plan", label: "Plan" },
  { id: "ejecucion", label: "Ejecución" },
  { id: "codigo", label: "Código" },
  { id: "tests", label: "Tests" },
  { id: "kiuwan", label: "Kiuwan" },
  { id: "sql", label: "SQL" },
  { id: "uiux", label: "UI/UX" },
  { id: "privacidad", label: "Privacidad" },
  { id: "vtr", label: "VTR" },
  { id: "dictamen", label: "Dictamen" },
];

const TAB_IDS = TABS.map((t) => t.id);

export default function RequirementPage() {
  return (
    <Suspense fallback={<Loading rows={4} />}>
      <RequirementDetail />
    </Suspense>
  );
}

function RequirementDetail() {
  const params = useSearchParams();
  const router = useRouter();
  const id = params.get("id") ?? "";
  const initial = (TAB_IDS as string[]).includes(params.get("tab") ?? "")
    ? (params.get("tab") as TabId)
    : "requerimiento";
  const [tab, setTabState] = useState<TabId>(initial);
  const [runId, setRunId] = useState<string | null>(null);

  const setTab = useCallback((next: TabId) => {
    setTabState(next);
    const url = new URL(window.location.href);
    url.searchParams.set("tab", next);
    window.history.replaceState(null, "", url.toString());
  }, []);

  const requirement = useResource<Requirement>(
    id ? `requirement:${id}` : null,
    () => api.requirements.get(id),
  );
  const plan = useResource<PlanView>(id ? `plan:${id}` : null, () => api.requirements.plan(id), {
    enabled: Boolean(id),
  });
  const runs = useResource<RunPage>(
    id ? `runs:${id}` : null,
    () => api.requirements.runs(id, { limit: 20 }),
    { refreshMs: 8000 },
  );

  const selected = useMemo(() => {
    const items = runs.data?.items ?? [];
    if (!items.length) return null;
    return items.find((r) => r.id === runId) ?? items[0];
  }, [runs.data, runId]);

  const stream = useRunStream(selected ? selected.id : null);

  // El canal se entera antes que la lista, así que manda él: si no, habría que esperar al
  // siguiente refresco para ver los informes de una ejecución recién acabada.
  const finished = Boolean(
    selected && (selected.status !== "en_curso" || stream.finalStatus !== null),
  );
  const detail = useResource<RunDetail>(
    selected && finished ? `run:${selected.id}` : null,
    () => api.runs.get(selected!.id),
    { enabled: Boolean(selected && finished) },
  );

  useEffect(() => {
    if (!id) router.replace("/");
  }, [id, router]);

  useEffect(() => {
    if (stream.finalStatus === null) return;
    invalidate(`runs:${id}`);
    void runs.reload();
    // `runs` cambia en cada render: solo interesa el momento en que la ejecución termina.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stream.finalStatus, id]);

  if (!id) return null;
  if (requirement.loading) return <Loading rows={4} />;
  if (!requirement.data) {
    return (
      <div className="space-y-3">
        <ErrorState error={requirement.error} onRetry={() => requirement.reload()} />
        <Link href="/" className="btn-ghost inline-block">
          Volver a la lista
        </Link>
      </div>
    );
  }

  const req = requirement.data;
  const deliverables = detail.data?.deliverables;
  const verdict = deliverables?.verdict ?? null;
  const simulated = Object.values(stream.run?.profiles ?? {})[0]?.provider;

  function refreshRequirement() {
    invalidate(`requirement:${id}`);
    void requirement.reload();
  }

  function refreshPlan() {
    invalidate(`plan:${id}`);
    void plan.reload();
  }

  return (
    <div className="space-y-4">
      <header className="space-y-2">
        <p className="text-[12px] text-ink-500">
          <Link href="/" className="hover:text-accent">
            Requerimientos
          </Link>
          {" · "}
          <span className="font-mono text-accent">{req.id}</span>
        </p>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="font-serif text-[26px] leading-tight text-ink-900">{req.title}</h1>
            <p className="mt-1 flex flex-wrap items-center gap-2 text-[12px] text-ink-500">
              <PhiBadge phi={req.phi as PhiClassification} />
              <span>responsable {req.owner}</span>
              <span>· creado {fmtDate(req.createdAt)}</span>
              {selected && (
                <span>
                  · última ejecución{" "}
                  <span className="font-mono text-accent">{selected.id}</span> ({selected.status})
                </span>
              )}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Refreshing active={runs.refreshing && !runs.loading} />
            {verdict && <VerdictBadge verdict={verdict.verdict as never} />}
          </div>
        </div>
      </header>

      <Tabs
        tabs={TABS.map((t) => ({ id: t.id, label: t.label }))}
        value={tab}
        onChange={(next) => setTab(next as TabId)}
      />

      {tab === "requerimiento" && (
        <RequirementPanel requirement={req} onChanged={refreshRequirement} />
      )}

      {tab === "plan" && (
        <>
          {plan.loading ? (
            <Loading rows={3} />
          ) : (
            <PlanPanel
              requirement={req}
              plan={plan.data}
              onPlanChanged={refreshPlan}
              onRunStarted={(newRunId) => {
                setRunId(newRunId);
                invalidate(`runs:${id}`);
                void runs.reload();
                setTab("ejecucion");
              }}
            />
          )}
        </>
      )}

      {tab === "ejecucion" && (
        <ExecutionSection
          runs={runs}
          selectedId={selected?.id ?? null}
          onSelect={setRunId}
          stream={stream}
        />
      )}

      {tab !== "requerimiento" && tab !== "plan" && tab !== "ejecucion" && (
        <div className="space-y-3">
          <SimulatedNotice provider={simulated} />
          <DeliverableSection
            tab={tab}
            detail={detail}
            selected={Boolean(selected)}
            finished={finished}
          />
        </div>
      )}
    </div>
  );
}

function ExecutionSection({
  runs,
  selectedId,
  onSelect,
  stream,
}: {
  runs: ReturnType<typeof useResource<RunPage>>;
  selectedId: string | null;
  onSelect: (id: string) => void;
  stream: ReturnType<typeof useRunStream>;
}) {
  return (
    <AsyncState
      resource={runs}
      empty={{
        title: "Este requerimiento no se ha ejecutado todavía",
        description: "Ve a la pestaña Plan, revisa los agentes y lanza la revisión.",
      }}
    >
      {(page) =>
        page.items.length === 0 ? (
          <p className="panel px-4 py-6 text-center text-[13px] text-ink-500">
            Este requerimiento no se ha ejecutado todavía.
          </p>
        ) : (
          <div className="space-y-4">
            <div className="flex flex-wrap items-center gap-2">
              <label className="text-[12px] text-ink-500" htmlFor="run-select">
                Ejecución
              </label>
              <select
                id="run-select"
                value={selectedId ?? ""}
                onChange={(e) => onSelect(e.target.value)}
                className="rounded-lg border border-line bg-surface px-2 py-1.5 font-mono text-[12px] outline-none focus:border-accent"
              >
                {page.items.map((run) => (
                  <option key={run.id} value={run.id}>
                    {run.id} · {run.status} · {fmtDate(run.startedAt)}
                  </option>
                ))}
              </select>
              <ConnectionBadge stream={stream} />
              {stream.run && (
                <span className="text-[12px] text-ink-500">
                  {fmtTokens(
                    (stream.run.usage?.tokensIn ?? 0) + (stream.run.usage?.tokensOut ?? 0),
                  )}{" "}
                  tokens · {fmtUsd(stream.run.usage?.costUsd ?? 0)}
                </span>
              )}
            </div>

            <SimulatedNotice provider={Object.values(stream.run?.profiles ?? {})[0]?.provider} />

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
                Traza{" "}
                <span className="text-[12px] font-normal text-ink-400">
                  ({stream.events.length} eventos)
                </span>
              </h2>
              <LiveTrace stream={stream} />
            </section>
          </div>
        )
      }
    </AsyncState>
  );
}

function DeliverableSection({
  tab,
  detail,
  selected,
  finished,
}: {
  tab: TabId;
  detail: ReturnType<typeof useResource<RunDetail>>;
  selected: boolean;
  finished: boolean;
}) {
  if (!selected) {
    return (
      <p className="panel px-4 py-6 text-center text-[13px] text-ink-500">
        No hay ninguna ejecución de la que mostrar entregables.
      </p>
    );
  }
  if (!finished) {
    return (
      <p className="panel px-4 py-6 text-center text-[13px] text-ink-500">
        La ejecución sigue en curso. Los informes aparecen cuando termina; mientras tanto, la
        pestaña <strong>Ejecución</strong> muestra la traza en vivo.
      </p>
    );
  }
  if (detail.loading) return <Loading rows={3} />;
  if (!detail.data) {
    return <ErrorState error={detail.error} onRetry={() => detail.reload()} />;
  }

  const deliverables = detail.data.deliverables;
  switch (tab) {
    case "codigo":
      return <CodePanel deliverables={deliverables} />;
    case "tests":
      return <TestsPanel deliverables={deliverables} />;
    case "kiuwan":
      return <KiuwanPanel deliverables={deliverables} />;
    case "sql":
      return <SqlPanel deliverables={deliverables} />;
    case "uiux":
      return <UiuxPanel deliverables={deliverables} />;
    case "privacidad":
      return <PrivacyPanel deliverables={deliverables} />;
    case "vtr":
      return <VtrPanel deliverables={deliverables} />;
    case "dictamen":
      return <VerdictPanel deliverables={deliverables} />;
    default:
      return null;
  }
}
