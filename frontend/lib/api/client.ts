// Cliente de la API. Los errores llegan con forma fija (`code`, `message`, `detail`), así que
// la UI decide por `code` sin leer el texto.
import type {
  AgentCatalog,
  AgentProfile,
  ApiErrorBody,
  AuditPage,
  AuditVerification,
  AuthCatalog,
  ClassifyPhiBody,
  ConnectRepoBody,
  CreateUserBody,
  LoginBody,
  CreateRequirementBody,
  Deliverables,
  NewAttachment,
  Health,
  ModelCatalog,
  PlanView,
  Requirement,
  RequirementPage,
  Run,
  RunDetail,
  RunPage,
  SaveSecretBody,
  Secret,
  SecretPage,
  SessionInfo,
  StartRunBody,
  TraceEvent,
  UpdatePlanBody,
  UpdateUserBody,
  User,
  UserPage,
} from "./types";

/**
 * URL base del backend del orquestador.
 * - `NEXT_PUBLIC_ORQ_API_URL` si está definida (dev: http://localhost:8001).
 * - Si está vacía, el mismo origen que la página (un solo proceso sirviendo API y estáticos).
 */
export function apiUrl(): string {
  const configured = (process.env.NEXT_PUBLIC_ORQ_API_URL || "").replace(/\/$/, "");
  if (configured) return configured;
  if (typeof window !== "undefined") return window.location.origin;
  return "";
}

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly detail?: Record<string, unknown>;

  constructor(status: number, body: Partial<ApiErrorBody> | null, fallback: string) {
    super(body?.message || fallback);
    this.name = "ApiError";
    this.status = status;
    this.code = body?.code || `Http${status}`;
    this.detail = (body?.detail as Record<string, unknown> | undefined) ?? undefined;
  }

  /** Motivos por los que un plan está bloqueado, si el error es ese. */
  get reasons(): string[] {
    const reasons = this.detail?.reasons;
    return Array.isArray(reasons) ? reasons.map(String) : [];
  }
}

/** El servicio no responde (apagado, puerto equivocado, sin red). */
export class NetworkError extends Error {
  constructor(cause: unknown) {
    super("No se pudo contactar con el servicio del orquestador.");
    this.name = "NetworkError";
    this.cause = cause;
  }
}

type Query = Record<string, string | number | boolean | undefined | null>;

function withQuery(path: string, query?: Query): string {
  if (!query) return path;
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined && value !== null && value !== "") params.set(key, String(value));
  }
  const suffix = params.toString();
  return suffix ? `${path}?${suffix}` : path;
}

async function request<T>(
  path: string,
  init?: RequestInit & { query?: Query },
): Promise<T> {
  const { query, ...rest } = init ?? {};
  let response: Response;
  try {
    response = await fetch(`${apiUrl()}/api${withQuery(path, query)}`, {
      ...rest,
      headers: { "Content-Type": "application/json", ...(rest.headers || {}) },
      cache: "no-store",
      // La cookie de sesión es HttpOnly: se manda siempre y decide el servidor.
      credentials: "include",
    });
  } catch (cause) {
    throw new NetworkError(cause);
  }

  if (!response.ok) {
    // La aplicación lo escucha para volver al login diciendo por qué caducó.
    const caducada = response.headers.get("X-Sesion-Caducada");
    if (caducada && typeof window !== "undefined") {
      window.dispatchEvent(new CustomEvent("orq:sesion-caducada", { detail: caducada }));
    }
    let body: Partial<ApiErrorBody> | null = null;
    try {
      body = (await response.json()) as Partial<ApiErrorBody>;
    } catch {
      /* respuesta sin cuerpo JSON */
    }
    throw new ApiError(response.status, body, `Error HTTP ${response.status}`);
  }

  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

function post<T>(path: string, body?: unknown, query?: Query): Promise<T> {
  return request<T>(path, {
    method: "POST",
    body: body === undefined ? undefined : JSON.stringify(body),
    query,
  });
}

function put<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, { method: "PUT", body: JSON.stringify(body) });
}

export const api = {
  health: () => request<Health>("/health"),

  auth: {
    me: () => request<SessionInfo>("/auth/me"),
    login: (body: LoginBody) => post<SessionInfo>("/auth/login", body),
    logout: () => request<void>("/auth/logout", { method: "POST" }),
    changePassword: (body: { current: string; new: string }) =>
      put<void>("/auth/password", body),
    catalog: () => request<AuthCatalog>("/auth/catalog"),
  },

  users: {
    list: () => request<UserPage>("/users"),
    create: (body: CreateUserBody) => post<User>("/users", body),
    update: (id: string, body: UpdateUserBody) =>
      put<User>(`/users/${encodeURIComponent(id)}`, body),
  },

  requirements: {
    list: (params?: { limit?: number; offset?: number }) =>
      request<RequirementPage>("/requirements", { query: params }),
    get: (id: string) => request<Requirement>(`/requirements/${encodeURIComponent(id)}`),
    create: (body: CreateRequirementBody) => post<Requirement>("/requirements", body),
    plan: (id: string) => request<PlanView>(`/requirements/${encodeURIComponent(id)}/plan`),
    suggestPlan: (id: string, options?: { assisted?: boolean }) =>
      post<PlanView>(`/requirements/${encodeURIComponent(id)}/plan`, undefined, {
        assisted: options?.assisted,
      }),
    updatePlan: (id: string, body: UpdatePlanBody) =>
      put<PlanView>(`/requirements/${encodeURIComponent(id)}/plan`, body),
    addAttachment: (id: string, body: NewAttachment) =>
      post<Requirement>(`/requirements/${encodeURIComponent(id)}/attachments`, body),
    connectRepo: (id: string, body: ConnectRepoBody) =>
      post<Requirement>(`/requirements/${encodeURIComponent(id)}/repo`, body),
    classifyPhi: (id: string, body: ClassifyPhiBody) =>
      put<Requirement>(`/requirements/${encodeURIComponent(id)}/phi`, body),
    runs: (id: string, params?: { limit?: number; offset?: number }) =>
      request<RunPage>(`/requirements/${encodeURIComponent(id)}/runs`, { query: params }),
    startRun: (id: string, body: StartRunBody) =>
      post<Run>(`/requirements/${encodeURIComponent(id)}/runs`, body),
  },

  runs: {
    get: (id: string, options?: { events?: boolean }) =>
      request<RunDetail>(`/runs/${encodeURIComponent(id)}`, {
        query: { events: options?.events },
      }),
    events: (id: string, afterSeq = 0) =>
      request<TraceEvent[]>(`/runs/${encodeURIComponent(id)}/events`, {
        query: { afterSeq },
      }),
    deliverables: (id: string) =>
      request<Deliverables>(`/runs/${encodeURIComponent(id)}/deliverables`),
    cancel: (id: string, by: string) =>
      post<Run>(`/runs/${encodeURIComponent(id)}/cancel`, undefined, { by }),
  },

  catalog: {
    agents: () => request<AgentCatalog>("/catalog/agents"),
    models: () => request<ModelCatalog>("/catalog/models"),
    profiles: (requirementId?: string) =>
      request<Record<string, AgentProfile>>("/catalog/profiles", {
        query: { requirementId },
      }),
  },

  audit: {
    list: (params?: { target?: string; limit?: number; offset?: number }) =>
      request<AuditPage>("/audit", { query: params }),
    verify: () => request<AuditVerification>("/audit/verify"),
  },

  // No hay método que lea un valor: no es un olvido, ese endpoint no existe.
  secrets: {
    list: (params?: { scope?: string }) =>
      request<SecretPage>("/secrets", { query: params }),
    save: (body: SaveSecretBody) => post<Secret>("/secrets", body),
    revoke: (id: string, by: string) =>
      request<Secret>(`/secrets/${encodeURIComponent(id)}`, {
        method: "DELETE",
        query: { by },
      }),
  },
};

/** Mensaje para la UI a partir de cualquier error del cliente. */
export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.reasons.length) return `${error.message} ${error.reasons.join(" · ")}`;
    return error.message;
  }
  if (error instanceof NetworkError) {
    return "No se pudo contactar con el servicio. Comprueba que el backend está levantado.";
  }
  return error instanceof Error ? error.message : "Error inesperado.";
}
