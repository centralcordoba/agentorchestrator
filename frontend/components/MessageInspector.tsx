"use client";

import { describeEvent, formatTime } from "@/lib/trace";
import { AGENT_COLORS, AGENT_LABELS, MESSAGE_TYPE_LABELS, type LLMExplanation, type RunEvent } from "@/lib/types";

interface Props {
  event: RunEvent | null;
  onJumpToMessage: (messageId: string) => void;
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex gap-2 text-xs">
      <span className="w-24 shrink-0 text-slate-500">{label}</span>
      <span className="min-w-0 flex-1 break-words text-slate-200">{children}</span>
    </div>
  );
}

function Explanation({ ex }: { ex: LLMExplanation }) {
  return (
    <div className="rounded-lg border border-violet-500/30 bg-violet-500/5 p-3 text-xs">
      <div className="mb-1 flex items-center justify-between">
        <span className="font-semibold text-violet-200">Explicación auditable</span>
        <span className="chip border-violet-500/40 text-violet-300">generada por: {ex.generated_by}</span>
      </div>
      <p className="text-slate-200">{ex.summary}</p>
      {ex.facts_used?.length > 0 && (
        <p className="mt-2 text-slate-400">
          <span className="text-slate-500">hechos usados:</span> {ex.facts_used.join(", ")}
        </p>
      )}
      {ex.caveats?.length > 0 && (
        <ul className="mt-1 list-disc pl-4 text-slate-400">
          {ex.caveats.map((c, i) => (
            <li key={i}>{c}</li>
          ))}
        </ul>
      )}
      {ex.validation_warnings?.length > 0 && (
        <ul className="mt-1 list-disc pl-4 text-amber-300">
          {ex.validation_warnings.map((c, i) => (
            <li key={i}>{c}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default function MessageInspector({ event, onJumpToMessage }: Props) {
  if (!event) {
    return (
      <div className="panel flex h-full flex-col">
        <div className="panel-title">
          <span>Inspector de mensajes</span>
        </div>
        <p className="p-4 text-sm text-slate-500">
          Selecciona un evento de la traza, una arista del grafo o una fila de la tabla para ver el mensaje completo.
        </p>
      </div>
    );
  }

  const m = event.message;
  const payload = m?.payload ?? event.data;
  const explanation = (payload as { explanation?: LLMExplanation }).explanation;
  const { explanation: _omit, ...rest } = payload as Record<string, unknown>;
  void _omit;

  return (
    <div className="panel flex h-full min-h-0 flex-col">
      <div className="panel-title">
        <span>Inspector · evento #{event.seq}</span>
        <span className="font-mono normal-case tracking-normal text-slate-500">{formatTime(event.timestamp)}</span>
      </div>
      <div className="min-h-0 flex-1 space-y-3 overflow-y-auto p-4">
        <Row label="tipo de evento">
          <span className="font-mono">{event.type}</span>
        </Row>
        {event.symbol && (
          <Row label="símbolo">
            <span className="font-mono">{event.symbol}</span>
          </Row>
        )}
        <Row label="resumen">{describeEvent(event)}</Row>

        {m && (
          <div className="rounded-lg border border-ink-700 bg-ink-950 p-3">
            <div className="mb-2 flex flex-wrap items-center gap-2 text-xs">
              <span className="chip" style={{ borderColor: AGENT_COLORS[m.sender], color: AGENT_COLORS[m.sender] }}>
                {AGENT_LABELS[m.sender]}
              </span>
              <span className="text-slate-500">→</span>
              <span className="chip" style={{ borderColor: AGENT_COLORS[m.recipient], color: AGENT_COLORS[m.recipient] }}>
                {AGENT_LABELS[m.recipient]}
              </span>
              <span className="chip border-ink-600 text-slate-300">{MESSAGE_TYPE_LABELS[m.type]}</span>
            </div>
            <Row label="id">
              <span className="font-mono">{m.id}</span>
            </Row>
            {m.in_reply_to && (
              <Row label="responde a">
                <button onClick={() => onJumpToMessage(m.in_reply_to!)} className="font-mono text-sky-300 underline-offset-2 hover:underline">
                  {m.in_reply_to}
                </button>
              </Row>
            )}
          </div>
        )}

        {explanation && <Explanation ex={explanation} />}

        <div>
          <div className="mb-1 text-[11px] font-semibold uppercase tracking-wider text-slate-500">
            {m ? "payload del mensaje" : "datos del evento"}
          </div>
          <pre className="max-h-[420px] overflow-auto rounded-lg border border-ink-700 bg-ink-950 p-3 font-mono text-[11px] leading-5 text-slate-300">
            {JSON.stringify(rest, null, 2)}
          </pre>
        </div>
      </div>
    </div>
  );
}
