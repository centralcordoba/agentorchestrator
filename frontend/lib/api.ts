import type { AppConfig, RunCreated, RunEvent, RunSummary } from "./types";

/**
 * URL base del backend.
 * - Si NEXT_PUBLIC_API_URL está definida (dev / Docker), se usa tal cual.
 * - Si está vacía (build estático servido por FastAPI), se usa el mismo origen que la página.
 */
export function getApiUrl(): string {
  const configured = (process.env.NEXT_PUBLIC_API_URL || "").replace(/\/$/, "");
  if (configured) return configured;
  if (typeof window !== "undefined") return window.location.origin;
  return "";
}

export class ApiError extends Error {
  status: number;
  detail: unknown;
  constructor(status: number, detail: unknown) {
    super(typeof detail === "string" ? detail : `Error HTTP ${status}`);
    this.status = status;
    this.detail = detail;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${getApiUrl()}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
    cache: "no-store",
  });
  if (!res.ok) {
    let detail: unknown = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? body;
    } catch {
      /* sin cuerpo JSON */
    }
    throw new ApiError(res.status, detail);
  }
  return (await res.json()) as T;
}

export const api = {
  config: () => request<AppConfig>("/api/config"),
  createRun: (symbols: string[]) =>
    request<RunCreated>("/api/runs", { method: "POST", body: JSON.stringify({ symbols }) }),
  getRun: (runId: string) => request<RunSummary>(`/api/runs/${runId}`),
  getEvents: (runId: string, after = 0) => request<RunEvent[]>(`/api/runs/${runId}/events?after=${after}`),
};
