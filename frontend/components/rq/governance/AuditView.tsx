"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { AUDIT_LABELS, can, missingPermissionText, verifyChain } from "@/lib/rq/governance";
import { USERS } from "@/lib/rq/mockData";
import { useRq } from "@/lib/rq/store";
import type { AuditAction } from "@/lib/rq/types";
import { Avatar, EmptyState, fmtDate } from "../ui";

const ACTION_CLASS: Partial<Record<AuditAction, string>> = {
  cambio_aprobado: "border-ok/30 bg-ok-soft text-ok",
  cambio_rechazado: "border-danger/30 bg-danger-soft text-danger",
  cambio_solicitado: "border-warn/30 bg-warn-soft text-warn",
  dictamen_firmado: "border-violet/30 bg-violet-soft text-violet",
  clasificacion_phi: "border-teal/30 bg-teal-soft text-teal",
};

export default function AuditView() {
  const { audit, currentUserId } = useRq();
  const user = USERS.find((u) => u.id === currentUserId);
  const [action, setAction] = useState<AuditAction | "todas">("todas");
  const [actor, setActor] = useState<string | "todos">("todos");

  const chain = useMemo(() => verifyChain(audit), [audit]);
  const rows = useMemo(
    () => [...audit].reverse().filter((e) => (action === "todas" || e.action === action) && (actor === "todos" || e.actor === actor)),
    [audit, action, actor],
  );

  if (!can(user, "ver_auditoria")) {
    return <EmptyState title="Sin acceso a la auditoría">{missingPermissionText("ver_auditoria")} Cambia de usuario arriba a la derecha para consultarla.</EmptyState>;
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-3">
        <p className="flex-1 text-[13px] leading-5 text-ink-500">
          Registro de solo escritura: cada entrada encadena el hash de la anterior, así que no se puede modificar ni borrar sin
          romper la cadena. En el backend se firmaría con SHA-256 y se exportaría al SIEM.
        </p>
        <span className={`chip ${chain.ok ? "border-ok/30 bg-ok-soft text-ok" : "border-danger/30 bg-danger-soft text-danger"}`}>
          <span aria-hidden>{chain.ok ? "✓" : "✕"}</span>
          {chain.ok ? `cadena íntegra · ${audit.length} entradas` : `cadena rota en la entrada ${chain.brokenAt}`}
        </span>
      </div>

      <div className="panel">
        <div className="flex flex-wrap items-center gap-3 border-b border-line px-4 py-2">
          <label className="flex items-center gap-1.5 text-[12px] text-ink-500">
            Acción
            <select value={action} onChange={(e) => setAction(e.target.value as AuditAction | "todas")} className="rounded-md border border-line bg-surface px-2 py-1 text-[12px] text-ink-900">
              <option value="todas">todas</option>
              {(Object.keys(AUDIT_LABELS) as AuditAction[]).map((a) => (
                <option key={a} value={a}>
                  {AUDIT_LABELS[a]}
                </option>
              ))}
            </select>
          </label>
          <label className="flex items-center gap-1.5 text-[12px] text-ink-500">
            Actor
            <select value={actor} onChange={(e) => setActor(e.target.value)} className="rounded-md border border-line bg-surface px-2 py-1 text-[12px] text-ink-900">
              <option value="todos">todos</option>
              {USERS.map((u) => (
                <option key={u.id} value={u.id}>
                  {u.name}
                </option>
              ))}
            </select>
          </label>
          <span className="ml-auto text-[12px] text-ink-400">{rows.length} entradas</span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[760px] text-left text-[12.5px]">
            <thead className="bg-sunken text-[11px] uppercase tracking-[0.06em] text-ink-500">
              <tr>
                <th scope="col" className="px-4 py-1.5 font-semibold">#</th>
                <th scope="col" className="px-4 py-1.5 font-semibold">Fecha</th>
                <th scope="col" className="px-4 py-1.5 font-semibold">Actor</th>
                <th scope="col" className="px-4 py-1.5 font-semibold">Acción</th>
                <th scope="col" className="px-4 py-1.5 font-semibold">Objeto</th>
                <th scope="col" className="px-4 py-1.5 font-semibold">Detalle</th>
                <th scope="col" className="px-4 py-1.5 font-semibold">Hash</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {rows.map((e) => {
                const u = USERS.find((x) => x.id === e.actor);
                const isReq = e.target.startsWith("REQ-");
                return (
                  <tr key={e.seq}>
                    <td className="px-4 py-2 font-mono text-ink-400">{e.seq}</td>
                    <td className="px-4 py-2 whitespace-nowrap text-ink-700">{fmtDate(e.at)}</td>
                    <td className="px-4 py-2">
                      <span className="flex items-center gap-1.5">
                        {u && <Avatar user={u} size={18} />}
                        <span className="text-ink-900">{u?.name ?? e.actor}</span>
                      </span>
                    </td>
                    <td className="px-4 py-2">
                      <span className={`chip ${ACTION_CLASS[e.action] ?? "chip-neutral"}`}>{AUDIT_LABELS[e.action]}</span>
                    </td>
                    <td className="px-4 py-2 font-mono text-[11.5px]">
                      {isReq ? (
                        <Link href={`/requerimiento?id=${e.target}`} className="text-accent hover:underline">
                          {e.target}
                        </Link>
                      ) : e.target.startsWith("CR-") ? (
                        <Link href={`/gobierno?cr=${e.target}`} className="text-accent hover:underline">
                          {e.target}
                        </Link>
                      ) : (
                        <span className="text-ink-700">{e.target}</span>
                      )}
                    </td>
                    <td className="px-4 py-2 text-ink-700">{e.detail}</td>
                    <td className="px-4 py-2 font-mono text-[11px] text-ink-400" title={`hash ${e.hash} · anterior ${e.prevHash}`}>
                      {e.hash.slice(0, 8)}…
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        {!rows.length && <p className="px-4 py-8 text-center text-[13px] text-ink-500">No hay entradas con estos filtros.</p>}
      </div>
    </div>
  );
}
