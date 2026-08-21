"use client";

import { describeEvent, formatTime } from "@/lib/trace";
import {
  AGENT_COLORS,
  AGENT_LABELS,
  AGENT_SOFT_COLORS,
  MESSAGE_TYPE_LABELS,
  type Evidence,
  type LLMExplanation,
  type RunEvent,
} from "@/lib/types";

interface Props {
  event: RunEvent | null;
  onJumpToMessage: (messageId: string) => void;
}

interface Guardrail {
  rule: string;
  before: unknown;
  after: unknown;
  reason: string;
}

interface Counterargument {
  code: string;
  text: string;
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex gap-3 text-[12.5px]">
      <span className="w-24 shrink-0 text-ink-400">{label}</span>
      <span className="min-w-0 flex-1 break-words text-ink-900">{children}</span>
    </div>
  );
}

function Section({ title, children, tone = "neutral" }: { title: string; children: React.ReactNode; tone?: "neutral" | "accent" | "violet" | "warn" }) {
  const cls = {
    neutral: "border-line bg-sunken/60",
    accent: "border-accent/20 bg-accent-soft/60",
    violet: "border-violet/20 bg-violet-soft/60",
    warn: "border-warn/30 bg-warn-soft/60",
  }[tone];
  return (
    <div className={`rounded-lg border p-3 text-[12.5px] ${cls}`}>
      <div className="mb-1.5 text-[11px] font-semibold uppercase tracking-[0.08em] text-ink-500">{title}</div>
      {children}
    </div>
  );
}

function fmt(v: unknown): string {
  if (v === null || v === undefined) return "—";
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}

function ExplanationBlock({ ex, mode }: { ex: LLMExplanation; mode?: string }) {
  return (
    <Section title="Explicación auditable" tone="accent">
      <div className="mb-1.5 flex flex-wrap items-center gap-1.5">
        <span className="chip border-accent/30 bg-surface text-accent">generada por · {ex.generated_by}</span>
        {mode && <span className={`chip ${mode === "llm" ? "border-violet/30 bg-surface text-violet" : "chip-neutral"}`}>modo · {mode}</span>}
      </div>
      <p className="leading-5 text-ink-700">{ex.summary}</p>
      {ex.facts_used?.length > 0 && (
        <p className="mt-2 font-mono text-[11px] leading-5 text-ink-500">
          <span className="text-ink-400">hechos usados:</span> {ex.facts_used.join(", ")}
        </p>
      )}
      {ex.caveats?.length > 0 && (
        <ul className="mt-1.5 list-disc space-y-0.5 pl-4 text-[12px] text-ink-500">
          {ex.caveats.map((c, i) => (
            <li key={i}>{c}</li>
          ))}
        </ul>
      )}
      {ex.validation_warnings?.length > 0 && (
        <ul className="mt-1.5 list-disc space-y-0.5 pl-4 text-[12px] text-warn">
          {ex.validation_warnings.map((c, i) => (
            <li key={i}>{c}</li>
          ))}
        </ul>
      )}
    </Section>
  );
}

export default function MessageInspector({ event, onJumpToMessage }: Props) {
  if (!event) {
    return (
      <div className="panel flex h-full flex-col overflow-hidden">
        <div className="panel-title">
          <span>Inspector de mensajes</span>
        </div>
        <div className="flex flex-1 flex-col items-center justify-center gap-1 p-6 text-center">
          <p className="text-[13px] text-ink-700">Nada seleccionado</p>
          <p className="max-w-xs text-[12px] leading-5 text-ink-400">
            Elige un evento de la traza, una arista del grafo o una fila de la tabla para ver el mensaje completo.
          </p>
        </div>
      </div>
    );
  }

  const m = event.message;
  const payload = (m?.payload ?? event.data) as Record<string, unknown>;
  const explanation = payload.explanation as LLMExplanation | undefined;
  const evidence = (payload.evidence as Evidence[] | undefined) ?? [];
  const guardrails = (payload.guardrails as Guardrail[] | undefined) ?? [];
  const counterarguments = (payload.counterarguments as Counterargument[] | undefined) ?? [];
  const ruleReference = (payload.rule_reference as Record<string, unknown> | undefined) ?? {};
  const mode = typeof payload.mode === "string" ? payload.mode : undefined;
  const { explanation: _e, evidence: _v, guardrails: _g, rule_reference: _r, ...rest } = payload;
  void _e;
  void _v;
  void _g;
  void _r;

  const isToolEvent = event.type === "tool_called";
  const isGuardrailEvent = event.type === "guardrail_applied";

  return (
    <div className="panel flex h-full min-h-0 flex-col overflow-hidden">
      <div className="panel-title">
        <span>Inspector · evento #{event.seq}</span>
        <span className="font-mono normal-case tracking-normal text-ink-400">{formatTime(event.timestamp)}</span>
      </div>
      <div className="min-h-0 flex-1 space-y-3 overflow-y-auto p-4">
        <Row label="tipo de evento">
          <span className="font-mono">{event.type}</span>
        </Row>
        {event.symbol && (
          <Row label="símbolo">
            <span className="font-mono font-semibold">{event.symbol}</span>
          </Row>
        )}
        <Row label="resumen">{describeEvent(event)}</Row>

        {m && (
          <div className="rounded-lg border border-line bg-sunken/60 p-3">
            <div className="mb-2 flex flex-wrap items-center gap-2 text-[12px]">
              <span className="chip border-transparent font-sans font-medium" style={{ background: AGENT_SOFT_COLORS[m.sender], color: AGENT_COLORS[m.sender] }}>
                {AGENT_LABELS[m.sender]}
              </span>
              <span className="text-ink-400">→</span>
              <span className="chip border-transparent font-sans font-medium" style={{ background: AGENT_SOFT_COLORS[m.recipient], color: AGENT_COLORS[m.recipient] }}>
                {AGENT_LABELS[m.recipient]}
              </span>
              <span className="chip chip-neutral">{MESSAGE_TYPE_LABELS[m.type]}</span>
            </div>
            <Row label="id">
              <span className="font-mono text-ink-500">{m.id}</span>
            </Row>
            {m.in_reply_to && (
              <Row label="responde a">
                <button onClick={() => onJumpToMessage(m.in_reply_to!)} className="font-mono text-accent underline-offset-2 hover:underline">
                  {m.in_reply_to}
                </button>
              </Row>
            )}
          </div>
        )}

        {isToolEvent && (
          <Section title="Llamada a herramienta" tone="violet">
            <Row label="herramienta">
              <span className="font-mono">{fmt(event.data.tool)}</span>
            </Row>
            <Row label="argumentos">
              <span className="font-mono text-[11.5px]">{fmt(event.data.arguments)}</span>
            </Row>
            <div className="mt-1.5 text-[11px] text-ink-400">resultado (código determinista → hechos disponibles para el modelo)</div>
            <pre className="mt-1 max-h-48 overflow-auto rounded-md border border-line bg-surface p-2 font-mono text-[11px] leading-5 text-ink-700">
              {JSON.stringify(event.data.result, null, 2)}
            </pre>
          </Section>
        )}

        {isGuardrailEvent && (
          <Section title="Guardarraíl aplicado" tone="warn">
            <p className="font-medium text-ink-900">{fmt(event.data.rule)}</p>
            <p className="mt-1 text-ink-700">{fmt(event.data.reason)}</p>
            <p className="mt-1 font-mono text-[11.5px] text-ink-500">
              antes: {fmt(event.data.before)} → después: {fmt(event.data.after)}
            </p>
          </Section>
        )}

        {explanation && <ExplanationBlock ex={explanation} mode={mode} />}

        {evidence.length > 0 && (
          <Section title="Evidencia citada por el agente" tone="violet">
            <ul className="space-y-1">
              {evidence.map((e, i) => (
                <li key={i} className="flex gap-2">
                  <span className="shrink-0 font-mono text-[11.5px] text-violet">{e.fact}</span>
                  <span className="text-ink-700">{e.observation}</span>
                </li>
              ))}
            </ul>
          </Section>
        )}

        {counterarguments.length > 0 && (
          <Section title="Objeciones" tone="warn">
            <ul className="space-y-1">
              {counterarguments.map((c, i) => (
                <li key={i} className="flex gap-2">
                  <span className="shrink-0 font-mono text-[11.5px] text-warn">{c.code}</span>
                  <span className="text-ink-700">{c.text}</span>
                </li>
              ))}
            </ul>
          </Section>
        )}

        {guardrails.length > 0 && (
          <Section title="Guardarraíles aplicados" tone="warn">
            <ul className="space-y-1.5">
              {guardrails.map((g, i) => (
                <li key={i}>
                  <p className="font-medium text-ink-900">{g.rule}</p>
                  <p className="text-ink-700">{g.reason}</p>
                  <p className="font-mono text-[11px] text-ink-500">
                    {fmt(g.before)} → {fmt(g.after)}
                  </p>
                </li>
              ))}
            </ul>
          </Section>
        )}

        {Object.keys(ruleReference).length > 0 && (
          <Section title="Qué habrían dicho las reglas">
            <p className="font-mono text-[11.5px] text-ink-700">
              {Object.entries(ruleReference)
                .map(([k, v]) => `${k} = ${fmt(v)}`)
                .join(" · ")}
            </p>
          </Section>
        )}

        <div>
          <div className="mb-1.5 text-[11px] font-semibold uppercase tracking-[0.08em] text-ink-500">
            {m ? "payload del mensaje" : "datos del evento"}
          </div>
          <pre className="max-h-[420px] overflow-auto rounded-lg border border-line bg-sunken p-3 font-mono text-[11px] leading-5 text-ink-700">
            {JSON.stringify(rest, null, 2)}
          </pre>
        </div>
      </div>
    </div>
  );
}
