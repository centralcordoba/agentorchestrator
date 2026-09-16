"use client";

import { ApiError, NetworkError, errorMessage } from "@/lib/api/client";
import { EmptyState } from "./ui";

/** Esqueleto de carga. Ocupa sitio para que el contenido no salte al llegar. */
export function Loading({ rows = 3, label = "Cargando…" }: { rows?: number; label?: string }) {
  return (
    <div className="panel p-4" role="status" aria-live="polite" aria-busy="true">
      <span className="sr-only">{label}</span>
      <div className="space-y-3">
        {Array.from({ length: rows }).map((_, index) => (
          <div key={index} className="flex items-center gap-3">
            <div className="h-8 w-8 animate-pulse rounded-full bg-sunken" />
            <div className="flex-1 space-y-2">
              <div className="h-3 w-1/3 animate-pulse rounded bg-sunken" />
              <div className="h-3 w-2/3 animate-pulse rounded bg-sunken" />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

/**
 * Error con el motivo y un botón para reintentar.
 *
 * Distingue el servicio caído de un error del servicio: no se arreglan igual.
 */
export function ErrorState({
  error,
  onRetry,
  title,
}: {
  error: unknown;
  onRetry?: () => void;
  title?: string;
}) {
  const offline = error instanceof NetworkError;
  const code = error instanceof ApiError ? error.code : undefined;
  const reasons = error instanceof ApiError ? error.reasons : [];

  return (
    <div className="panel border-danger/30 bg-danger-soft p-4" role="alert">
      <div className="flex items-start gap-3">
        <span aria-hidden className="text-[18px] leading-none text-danger">
          ⚠
        </span>
        <div className="flex-1">
          <p className="text-[13px] font-medium text-ink-900">
            {title ?? (offline ? "El servicio no responde" : "No se pudo completar la operación")}
          </p>
          <p className="mt-1 text-[13px] text-ink-600">{errorMessage(error)}</p>
          {reasons.length > 0 && (
            <ul className="mt-2 list-disc space-y-1 pl-5 text-[12px] text-ink-600">
              {reasons.map((reason) => (
                <li key={reason}>{reason}</li>
              ))}
            </ul>
          )}
          {offline && (
            <p className="mt-2 text-[12px] text-ink-500">
              Levanta el backend con <code>uvicorn orq.main:app --port 8001</code> dentro de{" "}
              <code>backend/</code>.
            </p>
          )}
          {code && <p className="mt-2 text-[11px] uppercase tracking-wide text-ink-400">{code}</p>}
        </div>
        {onRetry && (
          <button className="btn-ghost shrink-0" onClick={onRetry}>
            Reintentar
          </button>
        )}
      </div>
    </div>
  );
}

/** Indicador discreto de refresco: hay datos en pantalla y se están actualizando. */
export function Refreshing({ active }: { active: boolean }) {
  if (!active) return null;
  return (
    <span className="chip chip-neutral" aria-live="polite">
      Actualizando…
    </span>
  );
}

/**
 * Elige qué pintar según el estado del recurso.
 *
 * Con datos en pantalla, un error posterior no los borra: se avisa arriba y se sigue viendo lo
 * último bueno.
 */
export function AsyncState<T>({
  resource,
  empty,
  children,
}: {
  resource: { data: T | undefined; error: unknown; loading: boolean; reload: () => void };
  empty?: { title: string; description?: React.ReactNode };
  children: (data: T) => React.ReactNode;
}) {
  if (resource.loading) return <Loading />;
  if (resource.data === undefined) {
    return <ErrorState error={resource.error} onRetry={() => resource.reload()} />;
  }

  const isEmpty = Array.isArray(resource.data) && resource.data.length === 0;
  return (
    <div className="space-y-3">
      {resource.error !== null && (
        <ErrorState
          error={resource.error}
          onRetry={() => resource.reload()}
          title="No se pudo actualizar; se muestra lo último recibido"
        />
      )}
      {isEmpty && empty ? (
        <EmptyState title={empty.title}>{empty.description}</EmptyState>
      ) : (
        children(resource.data)
      )}
    </div>
  );
}

/**
 * Aviso de origen simulado.
 *
 * Aparece cuando la ejecución corrió con el proveedor `mock`: los informes tienen contenido para
 * poder enseñar el flujo, pero detrás no hay ningún análisis. La regla del proyecto es no
 * presentar datos inventados como reales, y esto es lo que la hace visible.
 */
export function SimulatedNotice({ provider }: { provider: string | undefined }) {
  if (provider !== "mock") return null;
  return (
    <p className="panel border-warn/30 bg-warn-soft px-4 py-2 text-[12.5px] text-ink-700">
      <span aria-hidden>⚠ </span>
      Ejecución con el <strong>proveedor simulado</strong>: los informes son de ejemplo, no un
      análisis del código. Sirven para ver el flujo; con un proveedor real cambian.
    </p>
  );
}
