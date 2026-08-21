"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import AgentGraph from "@/components/AgentGraph";
import AnalysisForm from "@/components/AnalysisForm";
import DecisionTable from "@/components/DecisionTable";
import DisclaimerBanner from "@/components/DisclaimerBanner";
import EventLog from "@/components/EventLog";
import MessageInspector from "@/components/MessageInspector";
import { api, ApiError } from "@/lib/api";
import { isRunFinished, resultsFromEvents, symbolsFromEvents } from "@/lib/trace";
import type { AgentName, AppConfig, RunEvent } from "@/lib/types";
import { connectRunSocket, mergeEvents, type RunSocket, type SocketStatus } from "@/lib/websocket";

const SOCKET_LABEL: Record<SocketStatus, string> = {
  connecting: "conectando…",
  open: "en vivo",
  closed: "desconectado",
  error: "error de conexión",
};

export default function Page() {
  const [config, setConfig] = useState<AppConfig | null>(null);
  const [configError, setConfigError] = useState<string | null>(null);
  const [runId, setRunId] = useState<string | null>(null);
  const [events, setEvents] = useState<RunEvent[]>([]);
  const [socketStatus, setSocketStatus] = useState<SocketStatus>("closed");
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [rejected, setRejected] = useState<Record<string, string>>({});
  const [selectedSymbol, setSelectedSymbol] = useState<string | "all">("all");
  const [selectedAgent, setSelectedAgent] = useState<AgentName | null>(null);
  const [selectedEvent, setSelectedEvent] = useState<RunEvent | null>(null);
  const socketRef = useRef<RunSocket | null>(null);

  useEffect(() => {
    api
      .config()
      .then(setConfig)
      .catch((e) => setConfigError(`No se pudo contactar con el backend (${e instanceof Error ? e.message : "error"}).`));
  }, []);

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

  const startRun = useCallback(async (symbols: string[]) => {
    setSubmitting(true);
    setFormError(null);
    setRejected({});
    try {
      const created = await api.createRun(symbols);
      attachToRun(created.run_id);
      setRejected(created.rejected);
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
  }, [attachToRun]);

  const symbols = useMemo(() => symbolsFromEvents(events), [events]);
  const results = useMemo(() => resultsFromEvents(events), [events]);
  const finished = useMemo(() => isRunFinished(events), [events]);
  const running = Boolean(runId) && !finished;

  // Cerrar el socket al terminar (la traza ya está completa en memoria).
  useEffect(() => {
    if (finished) socketRef.current?.close();
  }, [finished]);

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
      <DisclaimerBanner />

      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-ink-700 px-5 py-3">
        <div>
          <h1 className="text-lg font-semibold text-white">Orquestación multiagente · traza en tiempo real</h1>
          <p className="text-xs text-slate-400">
            Cómo un orquestador y cinco agentes se envían mensajes, trabajan en paralelo, discrepan, piden más datos y
            llegan a una decisión.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2 text-[11px]">
          {config ? (
            <>
              <span className="chip border-ink-600 text-slate-300">LLM: {config.llm_provider}</span>
              <span className="chip border-ink-600 text-slate-300">datos: {config.market_data_provider}</span>
              <span className="chip border-ink-600 text-slate-300">paralelismo: {config.max_parallel_symbols}</span>
            </>
          ) : (
            <span className="chip border-rose-500/40 text-rose-300">{configError ?? "cargando configuración…"}</span>
          )}
          {runId && (
            <>
              <span className="chip border-ink-600 font-mono text-slate-400">{runId}</span>
              <span
                className={`chip ${socketStatus === "open" ? "border-emerald-500/40 text-emerald-300" : finished ? "border-ink-600 text-slate-400" : "border-amber-500/40 text-amber-300"}`}
              >
                {finished ? `completado · ${done}/${symbols.length}` : `${SOCKET_LABEL[socketStatus]} · ${done}/${symbols.length}`}
              </span>
            </>
          )}
        </div>
      </header>

      <main className="grid flex-1 grid-cols-1 gap-4 p-4 xl:grid-cols-[320px_minmax(0,1fr)]">
        <aside className="space-y-4">
          <AnalysisForm
            busy={submitting || running}
            maxSymbols={config?.max_symbols_per_run ?? 8}
            onSubmit={startRun}
            rejected={rejected}
            error={formError}
          />
          <div className="panel p-4 text-xs leading-5 text-slate-400">
            <div className="mb-1 text-[11px] font-semibold uppercase tracking-wider text-slate-500">Qué observar</div>
            <ol className="list-decimal space-y-0.5 pl-4">
              <li>El orquestador inicia la ejecución y pide datos.</li>
              <li>Técnico y riesgo consumen la misma salida en paralelo.</li>
              <li>Riesgo pide historial ampliado a datos (línea discontinua).</li>
              <li>El escéptico puede discrepar y retar al técnico.</li>
              <li>Errores y datos faltantes terminan en NO_ANALIZABLE.</li>
              <li>La decisión agrega opiniones con reglas explícitas.</li>
            </ol>
            <p className="mt-2 text-[11px] text-slate-500">
              Filtra por símbolo en la tabla o por agente haciendo clic en un nodo. Las explicaciones del LLM se validan:
              ningún número puede aparecer sin existir en los hechos.
            </p>
          </div>
        </aside>

        <section className="flex min-h-0 min-w-0 flex-col gap-4">
          <div className="flex flex-wrap items-center gap-2 text-xs">
            <span className="text-slate-500">Símbolo:</span>
            <button
              onClick={() => setSelectedSymbol("all")}
              className={`rounded-md border px-2 py-0.5 font-mono ${selectedSymbol === "all" ? "border-sky-500 text-white" : "border-ink-600 text-slate-400"}`}
            >
              todos
            </button>
            {symbols.map((s) => (
              <button
                key={s}
                onClick={() => setSelectedSymbol(s)}
                className={`rounded-md border px-2 py-0.5 font-mono ${selectedSymbol === s ? "border-sky-500 text-white" : "border-ink-600 text-slate-400"} ${results[s] ? "" : "opacity-70"}`}
              >
                {s}
                {results[s] ? ` · ${results[s].decision}` : ""}
              </button>
            ))}
            {selectedAgent && (
              <button onClick={() => setSelectedAgent(null)} className="ml-auto rounded-md border border-ink-600 px-2 py-0.5 text-slate-300">
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

          <div className="grid min-h-[420px] grid-cols-1 gap-4 lg:grid-cols-[1.3fr_1fr]" style={{ height: 460 }}>
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

      <footer className="border-t border-ink-700 px-5 py-2 text-[11px] text-slate-500">
        Demo educativa. No constituye asesoramiento financiero ni recomendación de inversión. Sin ejecución de órdenes ni
        conexión con brókers. Las explicaciones son resúmenes estructurados; no se muestra razonamiento interno de los modelos.
      </footer>
    </div>
  );
}
