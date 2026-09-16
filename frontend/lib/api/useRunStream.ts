"use client";

// Traza en vivo por WebSocket. El canal manda primero lo ya ocurrido, así que abrir la pantalla
// a mitad de camino enseña la ejecución entera; al reconectar pide solo lo posterior.
import { useCallback, useEffect, useRef, useState } from "react";
import { apiUrl } from "./client";
import type { Run, TraceEvent } from "./types";

export type StreamStatus = "conectando" | "en_vivo" | "reconectando" | "terminada" | "error";

export interface RunStream {
  run: Run | undefined;
  events: TraceEvent[];
  status: StreamStatus;
  /** Último número de secuencia recibido: por ahí sigue una reconexión. */
  lastSeq: number;
  /** Estado final de la ejecución cuando el canal se cierra. */
  finalStatus: string | null;
  error: string | null;
}

/** Espera antes de reintentar, creciendo hasta 10 s. */
function backoff(attempt: number): number {
  return Math.min(1000 * 2 ** attempt, 10_000);
}

function socketUrl(runId: string, afterSeq: number): string {
  const base = apiUrl() || (typeof window !== "undefined" ? window.location.origin : "");
  const ws = base.replace(/^http/, "ws");
  return `${ws}/api/runs/${encodeURIComponent(runId)}/stream?afterSeq=${afterSeq}`;
}

export function useRunStream(runId: string | null): RunStream {
  const [run, setRun] = useState<Run | undefined>();
  const [events, setEvents] = useState<TraceEvent[]>([]);
  const [status, setStatus] = useState<StreamStatus>("conectando");
  const [finalStatus, setFinalStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const lastSeq = useRef(0);
  /** Números ya recibidos: con agentes en paralelo pueden llegar desordenados. */
  const seen = useRef(new Set<number>());
  const attempts = useRef(0);
  const socket = useRef<WebSocket | null>(null);
  const retry = useRef<ReturnType<typeof setTimeout> | null>(null);
  const closed = useRef(false);

  const connect = useCallback(() => {
    if (!runId || closed.current) return;

    const ws = new WebSocket(socketUrl(runId, lastSeq.current));
    socket.current = ws;

    ws.onopen = () => {
      attempts.current = 0;
      setStatus("en_vivo");
      setError(null);
    };

    ws.onmessage = (message) => {
      const frame = JSON.parse(message.data as string);
      switch (frame.type) {
        case "hello":
          setRun(frame.run as Run);
          break;
        case "event": {
          const event = frame.event as TraceEvent;
          if (seen.current.has(event.seq)) return; // duplicado tras reconectar
          seen.current.add(event.seq);
          // Avanza solo por números seguidos: si faltara alguno, reconectar pediría desde el
          // hueco en vez de saltárselo.
          while (seen.current.has(lastSeq.current + 1)) lastSeq.current += 1;
          setEvents((current) => [...current, event].sort((a, b) => a.seq - b.seq));
          break;
        }
        case "end":
          closed.current = true;
          setFinalStatus(String(frame.status));
          setStatus("terminada");
          break;
        default:
          break; // ping
      }
    };

    ws.onerror = () => {
      setError("Se perdió la conexión con el canal en vivo.");
    };

    ws.onclose = (event) => {
      socket.current = null;
      if (closed.current) return;
      // 4404: la ejecución no existe. No tiene sentido reintentar.
      if (event.code === 4404) {
        closed.current = true;
        setStatus("error");
        setError("La ejecución no existe.");
        return;
      }
      setStatus("reconectando");
      const wait = backoff(attempts.current++);
      retry.current = setTimeout(connect, wait);
    };
  }, [runId]);

  useEffect(() => {
    if (!runId) return;
    closed.current = false;
    lastSeq.current = 0;
    seen.current = new Set<number>();
    attempts.current = 0;
    setEvents([]);
    setRun(undefined);
    setFinalStatus(null);
    setStatus("conectando");
    connect();

    return () => {
      closed.current = true;
      if (retry.current) clearTimeout(retry.current);
      socket.current?.close();
      socket.current = null;
    };
  }, [runId, connect]);

  return { run, events, status, lastSeq: lastSeq.current, finalStatus, error };
}

/** Estado de cada agente, derivado de la traza. La UI no necesita otra fuente. */
export type LiveAgentStatus = "pendiente" | "trabajando" | "completado" | "omitido" | "fallido";

export function agentStatuses(
  events: TraceEvent[],
  enabled: string[],
): Record<string, LiveAgentStatus> {
  const statuses: Record<string, LiveAgentStatus> = {};
  for (const agent of enabled) statuses[agent] = "pendiente";
  for (const event of events) {
    const agent = event.agent;
    if (!agent) continue;
    switch (event.type) {
      case "agent_started":
        statuses[agent] = "trabajando";
        break;
      case "agent_completed":
        statuses[agent] = "completado";
        break;
      case "agent_skipped":
        statuses[agent] = "omitido";
        break;
      case "agent_failed":
        statuses[agent] = "fallido";
        break;
      default:
        break;
    }
  }
  return statuses;
}
