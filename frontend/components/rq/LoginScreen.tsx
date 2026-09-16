"use client";

// El error se anuncia con `role="alert"` y se enlaza con `aria-describedby`: un lector de
// pantalla lo lee sin tener que ir a buscarlo.
import { useEffect, useRef, useState } from "react";
import { errorMessage } from "@/lib/api/client";
import { useSession } from "@/lib/api/session";

const MOTIVOS: Record<string, string> = {
  inactividad: "La sesión se cerró por inactividad. Vuelve a entrar.",
  duracion_maxima: "La sesión alcanzó su duración máxima. Vuelve a entrar.",
  cuenta_desactivada: "Tu cuenta ya no está activa. Habla con el administrador.",
  cerrada: "",
};

export default function LoginScreen() {
  const { login, expiredReason } = useSession();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const primero = useRef<HTMLInputElement>(null);

  useEffect(() => {
    primero.current?.focus();
  }, []);

  async function entrar(event: React.FormEvent) {
    event.preventDefault();
    if (enviando) return;
    setEnviando(true);
    setError(null);
    try {
      await login(email.trim(), password);
    } catch (cause) {
      setError(cause);
      setPassword("");
    } finally {
      setEnviando(false);
    }
  }

  const aviso = MOTIVOS[expiredReason] ?? "";

  return (
    <main className="flex min-h-screen items-center justify-center bg-paper px-4 py-10">
      <div className="w-full max-w-[420px] space-y-5">
        <div className="flex items-center gap-2">
          <span
            aria-hidden
            className="flex h-8 w-8 items-center justify-center rounded-lg bg-accent font-mono text-[13px] font-bold text-white"
          >
            RQ
          </span>
          <span className="leading-tight">
            <span className="block text-[15px] font-semibold text-ink-900">
              Revisión de requerimientos
            </span>
            <span className="block text-[10.5px] uppercase tracking-[0.1em] text-ink-400">
              orquestador multiagente
            </span>
          </span>
        </div>

        {aviso && (
          <p className="panel border-warn/30 bg-warn-soft px-4 py-2.5 text-[13px] text-ink-700" role="status">
            {aviso}
          </p>
        )}

        <form
          className="panel space-y-4 p-5"
          onSubmit={entrar}
          aria-describedby={error !== null ? "login-error" : undefined}
        >
          <div>
            <h1 className="font-serif text-[22px] leading-tight text-ink-900">Entrar</h1>
            <p className="mt-1 text-[12.5px] leading-5 text-ink-500">
              Cada acción queda registrada con tu nombre: la auditoría y las firmas dependen de
              saber quién hizo qué.
            </p>
          </div>

          <label className="block space-y-1" htmlFor="login-email">
            <span className="block text-[12px] text-ink-500">Correo</span>
            <input
              id="login-email"
              ref={primero}
              type="email"
              name="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="username"
              required
              className="w-full rounded-lg border border-line bg-surface px-3 py-2 text-[13.5px] outline-none focus:border-accent focus:ring-2 focus:ring-accent-ring"
            />
          </label>

          <label className="block space-y-1" htmlFor="login-password">
            <span className="block text-[12px] text-ink-500">Contraseña</span>
            <input
              id="login-password"
              type="password"
              name="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
              required
              className="w-full rounded-lg border border-line bg-surface px-3 py-2 font-mono text-[13px] outline-none focus:border-accent focus:ring-2 focus:ring-accent-ring"
            />
          </label>

          {error !== null && (
            <p
              id="login-error"
              role="alert"
              className="panel border-danger/30 bg-danger-soft px-3 py-2 text-[12.5px] text-danger"
            >
              {errorMessage(error)}
            </p>
          )}

          <button className="btn-primary w-full" disabled={enviando || !email || !password}>
            {enviando ? "Comprobando…" : "Entrar"}
          </button>
        </form>

        <p className="px-1 text-[11.5px] leading-5 text-ink-400">
          ¿Sin cuenta? La crea un administrador desde Gobierno → Personas. La primera se siembra
          al arrancar el servicio con <span className="font-mono">ADMIN_EMAIL</span> y{" "}
          <span className="font-mono">ADMIN_PASSWORD</span>.
        </p>
      </div>
    </main>
  );
}
