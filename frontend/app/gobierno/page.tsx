"use client";

import { useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useState } from "react";
import AgentCardsView from "@/components/rq/governance/AgentCardsView";
import AuditView from "@/components/rq/governance/AuditView";
import ChangeRequestsView from "@/components/rq/governance/ChangeRequestsView";
import { Tabs } from "@/components/rq/ui";
import { useRq } from "@/lib/rq/store";

type TabId = "cambios" | "fichas" | "auditoria";
const TAB_IDS: TabId[] = ["cambios", "fichas", "auditoria"];

export default function GovernancePage() {
  return (
    <Suspense fallback={null}>
      <Governance />
    </Suspense>
  );
}

function Governance() {
  const params = useSearchParams();
  const { changeRequests, ready, setLocation } = useRq();
  const crParam = params.get("cr");
  const initial = (TAB_IDS as string[]).includes(params.get("tab") ?? "") ? (params.get("tab") as TabId) : crParam ? "cambios" : "cambios";
  const [tab, setTabState] = useState<TabId>(initial);
  const [selectedCr, setSelectedCr] = useState<string | null>(crParam);

  const setTab = useCallback((t: TabId) => {
    setTabState(t);
    const url = new URL(window.location.href);
    url.searchParams.set("tab", t);
    window.history.replaceState(null, "", url.toString());
  }, []);

  useEffect(() => setLocation({ page: "gobierno", tab }), [tab, setLocation]);

  if (!ready) return null;
  const pending = changeRequests.filter((c) => c.status === "pendiente").length;

  return (
    <div className="space-y-4">
      <div>
        <h1 className="font-serif text-[26px] leading-tight text-ink-900">Gobierno de IA</h1>
        <p className="mt-1 max-w-3xl text-[13px] leading-5 text-ink-500">
          Los cambios de modelo o de prompt afectan a todas las revisiones, así que se tratan como cualquier cambio controlado:
          se justifican, se evalúan contra un conjunto fijo de casos y los aprueba una persona distinta de quien los propone.
          Todo queda en un registro de auditoría que no se puede alterar.
        </p>
      </div>

      <Tabs<TabId>
        value={tab}
        onChange={setTab}
        tabs={[
          { id: "cambios", label: "Solicitudes de cambio", badge: pending ? <span className="chip border-warn/30 bg-warn-soft text-warn">{pending}</span> : undefined },
          { id: "fichas", label: "Fichas de agentes" },
          { id: "auditoria", label: "Auditoría" },
        ]}
      />

      {tab === "cambios" && (
        <ChangeRequestsView
          selectedId={selectedCr}
          onSelect={(id) => {
            setSelectedCr(id);
            const url = new URL(window.location.href);
            url.searchParams.set("cr", id);
            window.history.replaceState(null, "", url.toString());
          }}
        />
      )}
      {tab === "fichas" && <AgentCardsView />}
      {tab === "auditoria" && <AuditView />}
    </div>
  );
}
