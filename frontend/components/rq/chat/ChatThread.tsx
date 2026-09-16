"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { AGENTS, PROVIDER_BAA, PROVIDER_LABELS, modelLabel } from "@/lib/rq/agents";
import { answerQuestion, contextSize, estimateUsage, suggestionsFor } from "@/lib/rq/chat";
import type { RunView } from "@/lib/rq/derive";
import { USERS } from "@/lib/rq/mockData";
import { IDENTIFIER_LABELS, handlesPhi, scanTypedText } from "@/lib/rq/privacy";
import { consolidatedFindings } from "@/lib/rq/scenarios";
import { useRq } from "@/lib/rq/store";
import type { AgentId, ChatMessage, Requirement } from "@/lib/rq/types";
import { Avatar, fmtUsd } from "../ui";

interface Props {
  req: Requirement;
  view: RunView | null;
  /** Si viene, la conversación se limita a ese agente (panel del agente). */
  agentScope?: AgentId;
  /** Pestaña abierta: solo se usa para sugerir preguntas relevantes. */
  tab?: string;
  onNavigate?: (tab: string) => void;
  compact?: boolean;
}

export default function ChatThread({ req, view, agentScope, tab, onNavigate, compact }: Props) {
  const { chats, askChat, clearChat, currentUserId, effectiveProfile } = useRq();
  const [draft, setDraft] = useState("");
  const [thinking, setThinking] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);
  const profile = effectiveProfile("chat", req.id);
  const all = chats[req.id] ?? [];
  const messages = useMemo(() => (agentScope ? all.filter((m) => m.agentScope === agentScope) : all), [all, agentScope]);
  const suggestions = suggestionsFor({ req, view, agentId: agentScope }, tab);
  const typedPhi = scanTypedText(draft);
  const blocked = typedPhi.length > 0;

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end" });
  }, [messages.length, thinking]);

  const send = (question: string) => {
    const text = question.trim();
    if (!text || blocked || thinking) return;
    setDraft("");
    setThinking(true);
    // Pequeña espera para que se vea el estado "consultando"; en el backend será streaming real.
    setTimeout(() => {
      const ctx = { req, view, agentId: agentScope };
      const answer = answerQuestion(text, ctx);
      const usage = estimateUsage(text, answer, profile, contextSize(ctx));
      const detections = view?.completed.includes("privacy") ? view.deliverables.privacy.detections : [];
      const redactedTypes = handlesPhi(req) && detections.length ? Array.from(new Set(detections.map((x) => IDENTIFIER_LABELS[x.identifier]))) : undefined;
      askChat({ requirementId: req.id, question: text, agentScope, answer, usage, redactedTypes });
      setThinking(false);
    }, 650);
  };

  const cost = messages.reduce((s, m) => s + (m.costUsd ?? 0), 0);
  const chips = contextChips(req, view, agentScope);

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex flex-wrap items-center gap-1.5 border-b border-line bg-sunken/60 px-4 py-2">
        <span className="text-[11px] font-semibold uppercase tracking-[0.08em] text-ink-500">Contexto</span>
        {chips.map((c) => (
          <span key={c} className="chip chip-neutral">
            {c}
          </span>
        ))}
      </div>

      <div className="min-h-0 flex-1 space-y-3 overflow-y-auto px-4 py-3">
        {messages.length === 0 && !thinking && (
          <div className="space-y-3 py-2">
            <p className="text-[13px] leading-5 text-ink-700">
              {agentScope
                ? `Pregúntame por lo que hizo ${AGENTS[agentScope].label} en esta ejecución. Respondo solo con lo que consta en la traza y en su resultado.`
                : "Pregúntame sobre esta revisión: el dictamen, los hallazgos, la privacidad, las pruebas o el coste. Respondo con los datos de la ejecución y cito la evidencia."}
            </p>
            <p className="rounded-lg border border-line bg-sunken/60 px-3 py-2 text-[12px] leading-5 text-ink-500">
              Solo lectura: puedo llevarte a la pantalla donde se hace algo, pero no firmo dictámenes ni apruebo cambios de agentes.
            </p>
          </div>
        )}

        {messages.map((m) => (
          <Message key={m.id} m={m} onNavigate={onNavigate} />
        ))}

        {thinking && (
          <p className="flex items-center gap-2 text-[12.5px] text-ink-500">
            <span className="flex gap-1" aria-hidden>
              <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-ink-300" />
              <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-ink-300 [animation-delay:120ms]" />
              <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-ink-300 [animation-delay:240ms]" />
            </span>
            Consultando los datos de la ejecución…
          </p>
        )}
        <div ref={endRef} />
      </div>

      {suggestions.length > 0 && (
        <div className="flex flex-wrap gap-1.5 border-t border-line px-4 py-2">
          {suggestions.map((s) => (
            <button key={s} onClick={() => send(s)} disabled={thinking} className="pill pill-idle disabled:opacity-50">
              {s}
            </button>
          ))}
        </div>
      )}

      <div className="space-y-2 border-t border-line px-4 py-3">
        {blocked && (
          <p role="alert" className="rounded-lg border border-danger/30 bg-danger-soft px-3 py-2 text-[12px] leading-5 text-danger">
            <span className="font-semibold">No envíes datos de paciente. </span>
            Parece que el texto incluye: {typedPhi.map((t) => IDENTIFIER_LABELS[t]).join(", ")}. Quítalo y describe el caso sin el valor:
            el asistente ya tiene acceso a los hallazgos con su archivo y línea.
          </p>
        )}
        <div className="flex items-end gap-2">
          <label className="min-w-0 flex-1">
            <span className="sr-only">Pregunta al asistente</span>
            <textarea
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  send(draft);
                }
              }}
              rows={compact ? 2 : 2}
              placeholder="Escribe tu pregunta (Enter para enviar, Mayús+Enter para salto de línea)"
              aria-invalid={blocked}
              className={`w-full resize-none rounded-lg border bg-surface px-3 py-2 text-[13px] outline-none ${blocked ? "border-danger focus:border-danger" : "border-line focus:border-accent"}`}
            />
          </label>
          <button className="btn-primary py-2" disabled={!draft.trim() || blocked || thinking} onClick={() => send(draft)}>
            Preguntar
          </button>
        </div>
        <p className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-ink-400">
          <span>
            {modelLabel(profile.provider, profile.model)} · {PROVIDER_LABELS[profile.provider]}
            {PROVIDER_BAA[profile.provider] === true ? " · con BAA" : PROVIDER_BAA[profile.provider] === false ? " · sin BAA" : ""}
          </span>
          {cost > 0 && <span>conversación: {fmtUsd(cost)}</span>}
          <span>cada consulta queda en la auditoría</span>
          {messages.length > 0 && !agentScope && (
            <button onClick={() => clearChat(req.id)} className="ml-auto underline underline-offset-2 hover:text-ink-700">
              borrar conversación
            </button>
          )}
        </p>
      </div>
    </div>
  );
}

function contextChips(req: Requirement, view: RunView | null, agentScope?: AgentId): string[] {
  const chips = [req.id];
  if (agentScope) chips.push(`solo ${AGENTS[agentScope].label}`);
  if (!view) return [...chips, "sin ejecuciones"];
  const idx = req.runs.findIndex((r) => r.id === view.run.id) + 1;
  chips.push(`ejecución #${idx}`);
  chips.push(`${consolidatedFindings(view.deliverables, view.completed).length} hallazgos`);
  chips.push(`${view.events.length} eventos`);
  if (view.deliverables.realRepo) chips.push(`diff de ${view.deliverables.realRepo.files.length} archivos`);
  if (handlesPhi(req)) chips.push("PHI redactada");
  return chips;
}

function Message({ m, onNavigate }: { m: ChatMessage; onNavigate?: (tab: string) => void }) {
  const author = USERS.find((u) => u.id === m.author);
  if (m.role === "user") {
    return (
      <div className="flex items-start justify-end gap-2">
        <p className="max-w-[85%] rounded-lg rounded-br-sm bg-sunken px-3 py-2 text-[13px] leading-5 text-ink-900">{m.text}</p>
        {author && <Avatar user={author} size={22} />}
      </div>
    );
  }
  return (
    <div className="max-w-[92%] space-y-2">
      <div className={`rounded-lg rounded-bl-sm border px-3 py-2 ${m.fallback ? "border-warn/30 bg-warn-soft/50" : "border-line bg-surface"}`}>
        {m.text.split("\n").map((line, i) =>
          line.trim() === "" ? (
            <span key={i} className="block h-1.5" />
          ) : (
            <p key={i} className="text-[13px] leading-5 text-ink-900">
              {renderBold(line)}
            </p>
          ),
        )}
      </div>
      {(m.citations?.length || m.actions?.length || m.redactedTypes?.length) && (
        <div className="flex flex-wrap items-center gap-1.5">
          {m.citations?.map((c, i) =>
            c.url ? (
              <a key={i} href={c.url} target="_blank" rel="noreferrer" className="chip border-line bg-surface text-ink-700 hover:border-accent hover:text-accent">
                ↗ {c.label}
              </a>
            ) : c.tab && onNavigate ? (
              <button key={i} onClick={() => onNavigate(c.tab!)} className="chip border-line bg-surface text-ink-700 hover:border-accent hover:text-accent">
                ↳ {c.label}
              </button>
            ) : (
              <span key={i} className="chip chip-neutral">
                {c.label}
              </span>
            ),
          )}
          {m.actions?.map((a, i) =>
            a.href ? (
              <Link key={i} href={a.href} className="btn-ghost">
                {a.label} →
              </Link>
            ) : (
              <button key={i} className="btn-ghost" onClick={() => a.tab && onNavigate?.(a.tab)}>
                {a.label} →
              </button>
            ),
          )}
          {m.redactedTypes?.length ? (
            <span className="chip border-teal/30 bg-teal-soft text-teal" title="La pasarela DLP sustituyó los valores por marcadores antes de enviar el contexto">
              ⛨ {m.redactedTypes.length} tipo(s) de PHI redactados
            </span>
          ) : null}
        </div>
      )}
    </div>
  );
}

/** Solo soporta **negrita**: las respuestas del prototipo no usan más formato. */
function renderBold(line: string) {
  return line.split(/(\*\*[^*]+\*\*)/g).map((part, i) =>
    part.startsWith("**") && part.endsWith("**") ? (
      <strong key={i} className="font-semibold">
        {part.slice(2, -2)}
      </strong>
    ) : (
      <span key={i}>{part}</span>
    ),
  );
}
