"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import AgentGraph from "@/components/AgentGraph";
import AnalysisForm from "@/components/AnalysisForm";
import CostPanel from "@/components/CostPanel";
import DecisionTable from "@/components/DecisionTable";
import EventLog from "@/components/EventLog";
import MessageInspector from "@/components/MessageInspector";
import { api, ApiError } from "@/lib/api";
import { costsFromEvents, isRunFinished, resultsFromEvents, runSettingsFromEvents, symbolsFromEvents } from "@/lib/trace";
import { AGENT_MODE_LABELS, DECISION_DOT, type AgentMode, type AgentName, type AppConfig, type RunEvent, type RunSummary } from "@/lib/types";
import { connectRunSocket, mergeEvents, type RunSocket, type SocketStatus } from "@/lib/websocket";

const SOCKET_LABEL: Record<SocketStatus, string> = {
  connecting: "conectando…",
  open: "en vivo",
  closed: "desconectado",
  error: "error de conexión",
};

const GUIDE = [
  "El orquestador inicia la ejecución y pide datos.",
  "Técnico y riesgo consumen la misma salida en paralelo.",
  "Riesgo pide historial ampliado a datos (línea discontinua).",
  "El escéptico puede discrepar y retar al técnico.",
  "Errores y datos faltantes terminan en NO_ANALIZABLE.",
  "La decisión agrega opiniones; en modo LLM las reglas actúan como guardarraíles.",
];

function runLabel(r: RunSummary): string {
  const when = new Date(r.created_at);
  const hh = String(when.getHours()).padStart(2, "0");
  const mm = String(when.getMinutes()).padStart(2, "0");
  return `${hh}:${mm} · ${r.agent_mode ?? "rules"} · ${r.symbols.join(", ")}`;
}

export default function Page() {
  const [config, setConfig] = useState<AppConfig | null>(null);
  const [configError, setConfigError] = useState<string | null>(null);
  const [runId, setRunId] = useState<string | null>(null);
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [events, setEvents] = useState<RunEvent[]>([]);
  const [socketStatus, setSocketStatus] = useState<SocketStatus>("closed");
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [rejected, setRejected] = useState<Record<string, string>>({});
  const [selectedSymbol, setSelectedSymbol] = useState<string | "all">("all");
  const [selectedAgent, setSelectedAgent] = useState<AgentName | null>(null);
  const [selectedEvent, setSelectedEvent] = useState<RunEvent | null>(null);
  const socketRef = useRef<RunSocket | null>(null);

  const refreshRuns = useCallback(() => {
    api
      .listRuns()
      .then((list) => setRuns(list.slice(0, 30)))
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    api
      .config()
      .then(setConfig)
      .catch((e) => setConfigError(`No se pudo contactar con el backend (${e instanceof Error ? e.message : "error"}).`));
    refreshRuns();
  }, [refreshRuns]);

  useEffect(() => () => socketRef.current?.close(), []);

  const attachToRun = useCallback((id: string) => {
    socketRef.current?.close();
    setEvents([]);
    setSelectedEvent(null);
    setSelectedSymbol("all");
    setSelectedAgent(null);
    setRunId(id);
    socketRef.current = connectRunSocket(id, (event) => setEvents((prev) => mergeEvents(prev, event)), setSocketStatus);
    if (typeof window !== "undefined") {
      const url = new URL(window.location.href);
      url.searchParams.set("run", id);
      window.history.replaceState(null, "", url.toString());
    }
  }, []);

  // Reabrir una ejecución existente desde la URL (?run=run_xxx): el WS reenvía todo el historial.
  useEffect(() => {
    const id = new URLSearchParams(window.location.search).get("run");
    if (id) attachToRun(id);
  }, [attachToRun]);

  const startRun = useCallback(
    async (symbols: string[], messageDelayMs: number, agentMode: AgentMode) => {
      setSubmitting(true);
      setFormError(null);
      setRejected({});
      try {
        const created = await api.createRun(symbols, messageDelayMs, agentMode);
        attachToRun(created.run_id);
        setRejected(created.rejected);
        refreshRuns();
      } catch (e) {
        if (e instanceof ApiError && typeof e.detail === "object" && e.detail) {
          const d = e.detail as { message?: string; rejected?: Record<string, string> };
          setFormError(d.message ?? e.message);
          setRejected(d.rejected ?? {});
        } else {
          setFormError(e instanceof Error ? e.message : "Error desconocido");
        }
      } finally {
        setSubmitting(false);
      }
    },
    [attachToRun, refreshRuns],
  );

  const symbols = useMemo(() => symbolsFromEvents(events), [events]);
  const results = useMemo(() => resultsFromEvents(events), [events]);
  const finished = useMemo(() => isRunFinished(events), [events]);
  const { messageDelayMs, agentMode } = useMemo(() => runSettingsFromEvents(events), [events]);
  const costs = useMemo(() => costsFromEvents(events), [events]);
  const running = Boolean(runId) && !finished;

  // Cerrar el socket al terminar (la traza ya está completa en memoria) y refrescar el historial.
  useEffect(() => {
    if (finished) {
      socketRef.current?.close();
      refreshRuns();
    }
  }, [finished, refreshRuns]);

  const jumpToMessage = useCallback(
    (messageId: string) => {
      const ev = events.find((e) => e.message?.id === messageId);
      if (ev) setSelectedEvent(ev);
    },
    [events],
  );

  const done = Object.keys(results).length;

  return (
    <div className="flex min-h-screen flex-col">
      <header className="border-b border-line bg-surface">
        <div className="mx-auto flex max-w-[1680px] flex-wrap items-end justify-between gap-4 px-6 py-5">
          <div>
            <p className="mb-1 text-[11px] font-semibold uppercase tracking-[0.12em] text-accent">Demo educativa</p>
            <h1 className="font-serif text-[26px] font-medium leading-tight tracking-tight text-ink-900">
              Orquestación multiagente, vista como una traza
            </h1>
            <p className="mt-1 max-w-2xl text-[13px] text-ink-500">
              Cómo un orquestador y cinco agentes se envían mensajes, trabajan en paralelo, discrepan, piden más datos
              y llegan a una decisión.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {config ? (
              <>
                <span className="chip chip-neutral">LLM · {config.llm_provider}</span>
                <span className="chip chip-neutral">datos · {config.market_data_provider}</span>
                <span className="chip chip-neutral">paralelismo · {config.max_parallel_symbols}</span>
              </>
            ) : (
              <span className="chip border-danger/30 bg-danger-soft text-danger">{configError ?? "cargando configuración…"}</span>
            )}
            {runs.length > 0 && (
              <select
                aria-label="Ejecuciones anteriores"
                value={runId ?? ""}
                onChange={(e) => e.target.value && attachToRun(e.target.value)}
                className="max-w-[260px] rounded-md border border-line bg-surface px-2 py-0.5 font-mono text-[11px] text-ink-700 outline-none focus:border-accent"
              >
                <option value="">ejecuciones anteriores…</option>
                {runs.map((r) => (
                  <option key={r.run_id} value={r.run_id}>
                    {runLabel(r)}
                  </option>
                ))}
              </select>
            )}
            {runId && (
              <>
                <span className="chip chip-neutral text-ink-500">{runId}</span>
                {agentMode && (
                  <span className={`chip ${agentMode === "llm" ? "border-violet/30 bg-violet-soft text-violet" : "chip-neutral"}`} title={AGENT_MODE_LABELS[agentMode].hint}>
                    agentes · {AGENT_MODE_LABELS[agentMode].label}
                  </span>
                )}
                {messageDelayMs !== null && <span className="chip chip-neutral">ritmo · {messageDelayMs} ms/msg</span>}
                <span
                  className={`chip ${
                    running && socketStatus === "open"
                      ? "border-ok/30 bg-ok-soft text-ok"
                      : finished
                        ? "border-line bg-sunken text-ink-700"
                        : "border-warn/30 bg-warn-soft text-warn"
                  }`}
                >
                  {running && socketStatus === "open" && (
                    <span className="relative flex h-1.5 w-1.5">
                      <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-ok opacity-60" />
                      <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-ok" />
                    </span>
                  )}
                  {finished ? `completado · ${done}/${symbols.length}` : `${SOCKET_LABEL[socketStatus]} · ${done}/${symbols.length}`}
                </span>
              </>
            )}
          </div>
        </div>
      </header>

      <main className="mx-auto grid w-full max-w-[1680px] flex-1 grid-cols-1 gap-5 px-6 py-5 xl:grid-cols-[300px_minmax(0,1fr)]">
        <aside className="space-y-4">
          <AnalysisForm
            busy={submitting || running}
            maxSymbols={config?.max_symbols_per_run ?? 8}
            defaultDelayMs={config?.message_delay_ms ?? 800}
            defaultMode={config?.agent_mode ?? "rules"}
            llmSupportsTools={config?.llm_supports_tools ?? true}
            onSubmit={startRun}
            rejected={rejected}
            error={formError}
          />
          {runId && <CostPanel costs={costs} running={running} providerName={config?.llm_provider} />}
          <div className="panel p-4">
            <div className="mb-2 text-[11px] font-semibold uppercase tracking-[0.08em] text-ink-500">Qué observar</div>
            <ol className="space-y-1.5">
              {GUIDE.map((text, i) => (
                <li key={i} className="flex gap-2.5 text-[12.5px] leading-5 text-ink-700">
                  <span className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-accent-soft font-mono text-[10px] font-semibold text-accent">
                    {i + 1}
                  </span>
                  <span>{text}</span>
                </li>
              ))}
            </ol>
            <p className="mt-3 border-t border-line pt-3 text-[11.5px] leading-5 text-ink-500">
              Filtra por símbolo arriba o por agente haciendo clic en un nodo. En modo LLM, cada agente consulta
              herramientas (eventos <span className="font-mono">tool_called</span>) y las reglas corrigen salidas dudosas
              (<span className="font-mono">guardrail_applied</span>). Ningún número puede aparecer sin existir en los hechos.
            </p>
          </div>
        </aside>

        <section className="flex min-h-0 min-w-0 flex-col gap-4">
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="mr-1 text-[11px] font-semibold uppercase tracking-[0.08em] text-ink-500">Símbolo</span>
            <button onClick={() => setSelectedSymbol("all")} className={`pill ${selectedSymbol === "all" ? "pill-active" : "pill-idle"}`}>
              todos
            </button>
            {symbols.map((s) => {
              const r = results[s];
              const active = selectedSymbol === s;
              return (
                <button key={s} onClick={() => setSelectedSymbol(s)} className={`pill ${active ? "pill-active" : "pill-idle"}`}>
                  <span
                    className="inline-block h-1.5 w-1.5 rounded-full"
                    style={{ background: r ? DECISION_DOT[r.decision] : "#D5D1C5" }}
                  />
                  {s}
                  {r && <span className={active ? "text-white/70" : "text-ink-400"}>{r.decision}</span>}
                </button>
              );
            })}
            {selectedAgent && (
              <button onClick={() => setSelectedAgent(null)} className="btn-ghost ml-auto">
                quitar filtro de agente ×
              </button>
            )}
          </div>

          <AgentGraph
            events={events}
            symbol={selectedSymbol}
            running={running}
            selectedAgent={selectedAgent}
            onSelectAgent={setSelectedAgent}
            onSelectEvent={setSelectedEvent}
          />

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-[1.3fr_1fr]" style={{ height: 460 }}>
            <EventLog
              events={events}
              symbol={selectedSymbol}
              agent={selectedAgent}
              selectedSeq={selectedEvent?.seq ?? null}
              onSelect={setSelectedEvent}
            />
            <MessageInspector event={selectedEvent} onJumpToMessage={jumpToMessage} />
          </div>

          <DecisionTable
            symbols={symbols}
            results={results}
            events={events}
            selectedSymbol={selectedSymbol}
            onSelectSymbol={setSelectedSymbol}
            onInspect={setSelectedEvent}
          />
        </section>
      </main>

      <footer className="border-t border-line bg-surface">
        <p className="mx-auto max-w-[1680px] px-6 py-3 text-[11.5px] leading-5 text-ink-500">
          Demo educativa. No constituye asesoramiento financiero ni recomendación de inversión. Sin ejecución de órdenes ni
          conexión con brókers. Las explicaciones son resúmenes estructurados; no se muestra razonamiento interno de los modelos.
        </p>
      </footer>
    </div>
  );
}
