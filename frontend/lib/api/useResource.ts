"use client";

// Lectura de la API con caché: se pinta lo que hay y se revalida por detrás, y un error
// nunca borra lo que ya se estaba mostrando.
import { useCallback, useEffect, useRef, useState } from "react";

type Entry = { data: unknown; at: number };

const cache = new Map<string, Entry>();
const listeners = new Map<string, Set<() => void>>();
const inFlight = new Map<string, Promise<unknown>>();

function notify(key: string): void {
  listeners.get(key)?.forEach((listener) => listener());
}

/** Escribe en la caché y avisa a todo el que esté mostrando esa clave. */
export function setCached<T>(key: string, data: T): void {
  cache.set(key, { data, at: Date.now() });
  notify(key);
}

export function getCached<T>(key: string): T | undefined {
  return cache.get(key)?.data as T | undefined;
}

/** Olvida una clave (o todas las que empiecen por un prefijo) y fuerza su recarga. */
export function invalidate(prefix: string): void {
  for (const key of Array.from(cache.keys())) {
    if (key === prefix || key.startsWith(prefix)) {
      cache.delete(key);
      notify(key);
    }
  }
}

export interface Resource<T> {
  data: T | undefined;
  error: unknown;
  /** Primera carga: todavía no hay nada que pintar. */
  loading: boolean;
  /** Hay datos y se están refrescando por detrás. */
  refreshing: boolean;
  reload: () => Promise<void>;
}

export interface Options {
  /** Milisegundos entre refrescos automáticos. 0 = sin refresco. */
  refreshMs?: number;
  /** `false` deja la petición sin lanzar (p. ej. falta el identificador). */
  enabled?: boolean;
}

/**
 * Lee un recurso de la API. `key` identifica el dato en la caché; `fetcher` lo pide.
 */
export function useResource<T>(
  key: string | null,
  fetcher: () => Promise<T>,
  options: Options = {},
): Resource<T> {
  const { refreshMs = 0, enabled = true } = options;
  const active = enabled && key !== null;

  const [data, setData] = useState<T | undefined>(() =>
    key ? getCached<T>(key) : undefined,
  );
  const [error, setError] = useState<unknown>(null);
  const [refreshing, setRefreshing] = useState(false);
  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;

  const load = useCallback(
    async (force: boolean) => {
      if (!key || !active) return;
      const pending = inFlight.get(key);
      if (pending && !force) {
        try {
          setData((await pending) as T);
          setError(null);
        } catch (cause) {
          setError(cause);
        }
        return;
      }

      setRefreshing(true);
      const promise = fetcherRef.current();
      inFlight.set(key, promise);
      try {
        const result = await promise;
        cache.set(key, { data: result, at: Date.now() });
        setData(result);
        setError(null);
        notify(key);
      } catch (cause) {
        // El dato viejo sigue en pantalla: un fallo de red no vacía la vista.
        setError(cause);
      } finally {
        inFlight.delete(key);
        setRefreshing(false);
      }
    },
    [key, active],
  );

  useEffect(() => {
    if (!key) return;
    const listener = () => {
      const next = getCached<T>(key);
      // Invalidar no deja la pantalla en blanco: se sigue viendo lo último bueno.
      if (next !== undefined) setData(next);
    };
    const set = listeners.get(key) ?? new Set();
    set.add(listener);
    listeners.set(key, set);
    return () => {
      set.delete(listener);
      if (!set.size) listeners.delete(key);
    };
  }, [key]);

  useEffect(() => {
    if (!active) return;
    void load(false);
  }, [active, load]);

  useEffect(() => {
    if (!active || !refreshMs) return;
    const timer = setInterval(() => void load(true), refreshMs);
    return () => clearInterval(timer);
  }, [active, refreshMs, load]);

  return {
    data,
    error,
    loading: active && data === undefined && error === null,
    refreshing,
    reload: () => load(true),
  };
}
