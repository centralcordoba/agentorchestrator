"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import AgentPanel from "@/components/rq/AgentPanel";
import { CodeTab, KiuwanTab, SqlTab, UiuxTab, VerdictTab, VtrTab } from "@/components/rq/tabs/DeliverableTabs";
import ExecutionTab from "@/components/rq/tabs/ExecutionTab";
import PlanTab from "@/components/rq/tabs/PlanTab";
import RequirementTab from "@/components/rq/tabs/RequirementTab";
import { EmptyState, StatusDot, Tabs, VerdictBadge } from "@/components/rq/ui";
import { REQ_STATUS_LABELS, requirementStatus, runView } from "@/lib/rq/derive";
import { useNow, useRq } from "@/lib/rq/store";
import type { AgentId } from "@/lib/rq/types";

type TabId = "requerimiento" | "plan" | "ejecucion" | "codigo" | "kiuwan" | "sql" | "uiux" | "vtr" | "dictamen";
const TAB_IDS: TabId[] = ["requerimiento", "plan", "ejecucion", "codigo", "kiuwan", "sql", "uiux", "vtr", "dictamen"];

export default function RequirementPage() {
  return (
    <Suspense fallback={null}>
      <RequirementDetail />
    </Suspense>
  );
}

function RequirementDetail() {
  const params = useSearchParams();
  const router = useRouter();
  const { requirements, ready, setLocation } = useRq();
  const id = params.get("id") ?? "";
  const req = requirements.find((r) => r.id === id);
  const initialTab = (TAB_IDS as string[]).includes(params.get("tab") ?? "") ? (params.get("tab") as TabId) : "requerimiento";
  const [tab, setTabState] = useState<TabId>(initialTab);
  const [runId, setRunId] = useState<string | null>(null);
  const [panel, setPanel] = useState<{ agent: AgentId; tab?: "actividad" | "configuracion" } | null>(null);

  const setTab = useCallback(
    (t: TabId) => {
      setTabState(t);
      const url = new URL(window.location.href);
      url.searchParams.set("tab", t);
      window.history.replaceState(null, "", url.toString());
    },
    [],
  );

  useEffect(() => setLocation({ page: "requerimiento", requirementId: id, tab }), [id, tab, setLocation]);

  const run = req ? (runId ? req.runs.find((r) => r.id === runId) : undefined) ?? req.runs[req.runs.length - 1] : undefined;
  const now = useNow(true, 120);
  const view = useMemo(() => (req && run ? runView(req, run, now) : null), [req, run, now]);

  if (!ready) return null;
  if (!req) {
    return (
      <EmptyState title="Requerimiento no encontrado">
        <Link href="/" className="underline">
          Volver a la lista
        </Link>
      </EmptyState>
    );
  }

  const status = requirementStatus(req, now);
  const running = view?.state === "en_curso";
  const enabled = (a: AgentId) => (view ? view.run.enabledAgents.includes(a) : req.plan?.items.find((i) => i.agentId === a)?.enabled ?? true);
  const dot = (a: AgentId) => {
    if (!view || !view.run.enabledAgents.includes(a)) return undefined;
    return <StatusDot status={view.completed.includes(a) ? "completado" : running ? "trabajando" : "pendiente"} />;
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <Link href="/" className="text-[12px] text-ink-500 hover:text-ink-900">
            ← Requerimientos
          </Link>
          <div className="mt-1 flex flex-wrap items-center gap-2">
            <span className="font-mono text-[13px] text-accent">{req.id}</span>
            <span className="chip chip-neutral">{REQ_STATUS_LABELS[status]}</span>
            {view?.verdict && <VerdictBadge verdict={view.verdict} />}
          </div>
          <h1 className="font-serif text-[24px] leading-tight text-ink-900">{req.title}</h1>
        </div>
        <button className="btn-ghost" onClick={() => router.push("/agentes")}>
          configuración global de agentes
        </button>
      </div>

      <Tabs<TabId>
        value={tab}
        onChange={setTab}
        tabs={[
          { id: "requerimiento", label: "Requerimiento", badge: <span className="chip chip-neutral">{req.attachments.length}</span> },
          { id: "plan", label: "Plan de agentes" },
          { id: "ejecucion", label: "Ejecución", badge: running ? <StatusDot status="trabajando" /> : undefined },
          { id: "codigo", label: "Código y Tests", badge: dot("code"), hidden: !enabled("code") && !enabled("tests") },
          { id: "kiuwan", label: "Kiuwan", badge: dot("kiuwan"), hidden: !enabled("kiuwan") },
          { id: "sql", label: "SQL", badge: dot("sql"), hidden: !enabled("sql") },
          { id: "uiux", label: "UI/UX", badge: dot("uiux"), hidden: !enabled("uiux") },
          { id: "vtr", label: "VTR", badge: dot("vtr"), hidden: !enabled("vtr") },
          { id: "dictamen", label: "Dictamen", badge: dot("verdict") },
        ]}
      />

      <div>
        {tab === "requerimiento" && <RequirementTab req={req} readOnly={running} />}
        {tab === "plan" && <PlanTab req={req} running={running} onStarted={() => { setRunId(null); setTab("ejecucion"); }} onConfigure={(a) => setPanel({ agent: a, tab: "configuracion" })} />}
        {tab === "ejecucion" && (
          <ExecutionTab
            req={req}
            view={view}
            now={now}
            selectedAgent={panel?.agent ?? null}
            onSelectAgent={(a) => setPanel({ agent: a })}
            onSelectRun={setRunId}
            onGoToPlan={() => setTab("plan")}
          />
        )}
        {tab === "codigo" && <CodeTab req={req} view={view} />}
        {tab === "kiuwan" && <KiuwanTab view={view} />}
        {tab === "sql" && <SqlTab view={view} />}
        {tab === "uiux" && <UiuxTab view={view} />}
        {tab === "vtr" && <VtrTab view={view} />}
        {tab === "dictamen" && <VerdictTab view={view} />}
      </div>

      {panel && (
        <AgentPanel
          req={req}
          view={view}
          agentId={panel.agent}
          initialTab={panel.tab}
          onClose={() => setPanel(null)}
          onOpenDeliverable={(t) => {
            setPanel(null);
            setTab(t as TabId);
          }}
        />
      )}
    </div>
  );
}
