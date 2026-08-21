import { getApiUrl } from "./api";
import type { RunEvent } from "./types";

export type SocketStatus = "connecting" | "open" | "closed" | "error";

export interface RunSocket {
  close: () => void;
}

function wsUrl(runId: string): string {
  const base = getApiUrl().replace(/^http/, "ws"); // http→ws, https→wss
  return `${base}/ws/runs/${runId}`;
}

/**
 * Abre el WebSocket de una ejecución. El servidor reenvía primero el historial
 * completo (replay) y después los eventos nuevos. El consumidor debe deduplicar
 * por `seq` (ver `mergeEvents`).
 */
export function connectRunSocket(
  runId: string,
  onEvent: (event: RunEvent) => void,
  onStatus: (status: SocketStatus) => void,
): RunSocket {
  let ws: WebSocket | null = null;
  let closedByUser = false;
  let attempt = 0;
  let openedAt = 0;
  let pingTimer: ReturnType<typeof setInterval> | null = null;

  // Los eventos que llegan en ráfaga justo tras abrir la conexión son historial (replay):
  // no se marcan como "recientes" para no animar todo el grafo de golpe.
  const REPLAY_WINDOW_MS = 400;

  const open = () => {
    onStatus("connecting");
    ws = new WebSocket(wsUrl(runId));

    ws.onopen = () => {
      attempt = 0;
      openedAt = Date.now();
      onStatus("open");
      pingTimer = setInterval(() => ws?.readyState === WebSocket.OPEN && ws.send("ping"), 20000);
    };
    ws.onmessage = (ev) => {
      try {
        const event = JSON.parse(ev.data) as RunEvent;
        const now = Date.now();
        if (now - openedAt > REPLAY_WINDOW_MS) event.receivedAt = now;
        onEvent(event);
      } catch {
        /* mensaje no JSON: ignorar */
      }
    };
    ws.onerror = () => onStatus("error");
    ws.onclose = () => {
      if (pingTimer) clearInterval(pingTimer);
      onStatus("closed");
      if (!closedByUser && attempt < 6) {
        attempt += 1;
        setTimeout(open, Math.min(8000, 500 * 2 ** attempt));
      }
    };
  };

  open();
  return {
    close: () => {
      closedByUser = true;
      if (pingTimer) clearInterval(pingTimer);
      ws?.close();
    },
  };
}

/** Inserta un evento manteniendo orden por `seq` y sin duplicados. */
export function mergeEvents(current: RunEvent[], incoming: RunEvent): RunEvent[] {
  const last = current[current.length - 1];
  if (!last || incoming.seq > last.seq) return [...current, incoming];
  if (current.some((e) => e.seq === incoming.seq)) return current;
  return [...current, incoming].sort((a, b) => a.seq - b.seq);
}
