"use client";

import { useEffect } from "react";
import type { RunView } from "@/lib/rq/derive";
import type { Requirement } from "@/lib/rq/types";
import ChatThread from "./ChatThread";

/** Panel lateral del asistente dentro de un requerimiento: no es modal, se puede seguir navegando. */
export default function ChatPanel({
  req,
  view,
  tab,
  onNavigate,
  onClose,
}: {
  req: Requirement;
  view: RunView | null;
  tab?: string;
  onNavigate: (tab: string) => void;
  onClose: () => void;
}) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <aside
      className="fixed bottom-0 right-0 top-[57px] z-30 flex w-full max-w-[460px] flex-col border-l border-line bg-surface shadow-pop"
      aria-label="Asistente de revisión"
    >
      <header className="flex items-start gap-2 border-b border-line px-4 py-3">
        <div className="min-w-0 flex-1">
          <h2 className="text-[15px] font-semibold text-ink-900">Asistente de revisión</h2>
          <p className="text-[12px] leading-5 text-ink-500">Responde con los datos de esta ejecución y cita la evidencia.</p>
        </div>
        <button onClick={onClose} className="btn-ghost" aria-label="Cerrar asistente">
          ✕
        </button>
      </header>
      <ChatThread req={req} view={view} tab={tab} onNavigate={onNavigate} />
    </aside>
  );
}
