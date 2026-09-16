"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { USERS } from "@/lib/rq/mockData";
import { useRq } from "@/lib/rq/store";
import { Avatar } from "./ui";

const NAV = [
  { href: "/", label: "Requerimientos", match: (p: string) => p === "/" || p.startsWith("/requerimiento") },
  { href: "/agentes", label: "Agentes", match: (p: string) => p.startsWith("/agentes") },
  { href: "/gobierno", label: "Gobierno", match: (p: string) => p.startsWith("/gobierno") },
  { href: "/monitor", label: "Monitor", match: (p: string) => p.startsWith("/monitor") },
];

export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname() ?? "/";
  const { currentUserId, setCurrentUser, resetDemo, ready, changeRequests } = useRq();
  const pendingChanges = changeRequests.filter((c) => c.status === "pendiente").length;
  const user = USERS.find((u) => u.id === currentUserId) ?? USERS[0];

  if (pathname.startsWith("/demo-bolsa")) return <>{children}</>;

  return (
    <div className="flex min-h-screen flex-col">
      <header className="sticky top-0 z-30 border-b border-line bg-surface/95 backdrop-blur">
        <div className="mx-auto flex max-w-[1440px] flex-wrap items-center gap-x-6 gap-y-2 px-4 py-2.5 sm:px-6">
          <Link href="/" className="flex items-center gap-2">
            <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-accent font-mono text-[12px] font-bold text-white">RQ</span>
            <span className="leading-tight">
              <span className="block text-[13.5px] font-semibold text-ink-900">Revisión de requerimientos</span>
              <span className="block text-[10.5px] uppercase tracking-[0.1em] text-ink-400">orquestador multiagente · prototipo</span>
            </span>
          </Link>
          <nav className="flex items-center gap-1">
            {NAV.map((n) => {
              const active = n.match(pathname);
              return (
                <Link
                  key={n.href}
                  href={n.href}
                  className={`inline-flex items-center rounded-md px-2.5 py-1.5 text-[13px] transition ${
                    active ? "bg-sunken font-semibold text-ink-900" : "text-ink-500 hover:bg-sunken hover:text-ink-900"
                  }`}
                >
                  {n.label}
                  {n.href === "/gobierno" && pendingChanges > 0 && (
                    <span className="ml-1.5 chip border-warn/30 bg-warn-soft text-warn" title={`${pendingChanges} solicitud(es) de cambio pendientes`}>
                      {pendingChanges}
                    </span>
                  )}
                </Link>
              );
            })}
          </nav>
          <div className="ml-auto flex items-center gap-2">
            <span className="chip border-warn/30 bg-warn-soft text-warn" title="Todo se simula en el navegador; no hay backend.">
              datos simulados
            </span>
            <label className="flex items-center gap-2 rounded-lg border border-line bg-surface py-1 pl-1 pr-2">
              <Avatar user={user} size={24} />
              <span className="sr-only">Sesión como</span>
              <select
                value={currentUserId}
                onChange={(e) => setCurrentUser(e.target.value)}
                className="bg-transparent text-[12.5px] text-ink-900 outline-none"
              >
                {USERS.map((u) => (
                  <option key={u.id} value={u.id}>
                    {u.name} · {u.role}
                  </option>
                ))}
              </select>
            </label>
          </div>
        </div>
      </header>
      {/* El contenido depende del reloj y de localStorage: se pinta solo en el navegador, tras cargar el estado.
          Así el HTML estático (generado en el build) no choca con lo que ve el usuario al hidratar. */}
      <div className="mx-auto w-full max-w-[1440px] flex-1 px-4 py-5 sm:px-6">
        {ready ? children : <p className="py-16 text-center text-[13px] text-ink-400">Cargando…</p>}
      </div>
      <footer className="border-t border-line bg-surface">
        <div className="mx-auto flex max-w-[1440px] flex-wrap items-center gap-3 px-4 py-2.5 text-[11.5px] text-ink-500 sm:px-6">
          <span>Prototipo de interfaz sin backend: ejecuciones, usuarios y consumo son simulados.</span>
          <button onClick={resetDemo} className="btn-ghost">
            restablecer datos de ejemplo
          </button>
          <Link href="/demo-bolsa" className="ml-auto underline decoration-line-strong underline-offset-2 hover:text-ink-900">
            demo anterior (bolsa)
          </Link>
        </div>
      </footer>
    </div>
  );
}
