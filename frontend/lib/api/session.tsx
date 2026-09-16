"use client";

// Aquí no se guarda ningún testigo: la sesión vive en una cookie `HttpOnly` que este código no
// puede leer. En memoria solo queda quién eres y qué puedes hacer, para pintar la interfaz.
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { ApiError, api } from "./client";
import type { SessionInfo, User } from "./types";

export type Permission =
  | "crear_requerimiento"
  | "ejecutar"
  | "solicitar_cambio_agente"
  | "aprobar_cambio_agente"
  | "firmar_dictamen"
  | "ver_auditoria"
  | "gestionar_secretos"
  | "gestionar_usuarios";

interface SessionState {
  user: User | null;
  /** `true` mientras se comprueba con el servidor si hay sesión. */
  loading: boolean;
  /** Por qué se cerró la última sesión: `inactividad`, `duracion_maxima`, `cerrada`. */
  expiredReason: string;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
  can: (permission: Permission) => boolean;
}

const Context = createContext<SessionState | null>(null);

export function SessionProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [expiredReason, setExpiredReason] = useState("");

  const refresh = useCallback(async () => {
    try {
      const info: SessionInfo = await api.auth.me();
      setUser(info.authenticated ? (info.user ?? null) : null);
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  // Al caducar se vuelve al login con el motivo, en vez de dejar la aplicación dando 401.
  useEffect(() => {
    function onExpired(event: Event) {
      const reason = (event as CustomEvent<string>).detail || "cerrada";
      setExpiredReason(reason);
      setUser(null);
    }
    window.addEventListener("orq:sesion-caducada", onExpired);
    return () => window.removeEventListener("orq:sesion-caducada", onExpired);
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const info = await api.auth.login({ email, password });
    setExpiredReason("");
    setUser(info.user ?? null);
  }, []);

  const logout = useCallback(async () => {
    try {
      await api.auth.logout();
    } catch {
      // Falle lo que falle, en el cliente la sesión se acaba igual.
    }
    setExpiredReason("");
    setUser(null);
  }, []);

  const value = useMemo<SessionState>(
    () => ({
      user,
      loading,
      expiredReason,
      login,
      logout,
      refresh,
      can: (permission) => Boolean(user?.permissions?.includes(permission)),
    }),
    [user, loading, expiredReason, login, logout, refresh],
  );

  return <Context.Provider value={value}>{children}</Context.Provider>;
}

export function useSession(): SessionState {
  const value = useContext(Context);
  if (!value) throw new Error("useSession fuera de <SessionProvider>");
  return value;
}

/** ¿El error es «no has entrado»? Sirve para no pintar un error rojo cuando toca el login. */
export function isUnauthorized(error: unknown): boolean {
  return error instanceof ApiError && error.status === 401;
}
