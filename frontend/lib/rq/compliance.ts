// Panel de cumplimiento: indicadores y alertas derivados del estado real del prototipo
// (clasificación PHI, hallazgos de privacidad, proveedores sin BAA, firmas, cambios y MFA).
import { AGENTS, AGENT_ORDER, ALL_AGENTS, PROVIDER_BAA, PROVIDER_LABELS } from "./agents";
import { latestRun, runView } from "./derive";
import { AGENT_CARDS } from "./governance";
import { USERS } from "./mockData";
import { handlesPhi } from "./privacy";
import type { AgentId, AgentProfile, ChangeRequest, PhiClassification, ProviderId, Requirement, SafeguardCheck, SafeguardId, Severity } from "./types";

export interface ComplianceAlert {
  id: string;
  severity: Extract<Severity, "critica" | "alta" | "media" | "baja">;
  title: string;
  detail: string;
  href?: string;
  action?: string;
}

export interface PhiRequirementRow {
  id: string;
  title: string;
  phi: PhiClassification;
  privacyRan: boolean;
  criticals: number;
  highs: number;
  redactions: number;
  signed: boolean;
  verdictPending: boolean;
}

export interface SafeguardRollup {
  id: SafeguardId;
  riesgo: number;
  sin_evidencia: number;
  cumple: number;
  no_aplica: number;
  total: number;
}

export interface ProviderRow {
  provider: ProviderId;
  baa: boolean | null;
  agents: AgentId[];
  phiAgents: AgentId[];
}

const SEV_RANK: Record<ComplianceAlert["severity"], number> = { critica: 0, alta: 1, media: 2, baja: 3 };

export function buildCompliance(requirements: Requirement[], profiles: Record<AgentId, AgentProfile>, changeRequests: ChangeRequest[], now: number) {
  const alerts: ComplianceAlert[] = [];
  const rows: PhiRequirementRow[] = [];
  const rollup: Record<SafeguardId, SafeguardRollup> = Object.fromEntries(
    (["acceso", "auditoria", "integridad", "autenticacion", "transmision"] as SafeguardId[]).map((id) => [id, { id, riesgo: 0, sin_evidencia: 0, cumple: 0, no_aplica: 0, total: 0 }]),
  ) as Record<SafeguardId, SafeguardRollup>;

  let redactionsToday = 0;
  let unsigned = 0;

  for (const req of requirements) {
    const run = latestRun(req);
    const view = run ? runView(req, run, now) : null;
    const privacyRan = Boolean(view?.completed.includes("privacy"));
    const pr = view?.deliverables.privacy;
    const criticals = privacyRan && pr ? pr.findings.filter((f) => f.severity === "critica").length : 0;
    const highs = privacyRan && pr ? pr.findings.filter((f) => f.severity === "alta").length : 0;
    const redactions = view ? view.events.filter((e) => e.type === "phi_redacted").length * (pr?.detections.length ?? 0) : 0;
    const verdictDone = Boolean(view?.completed.includes("verdict"));
    const signed = Boolean(run?.signoff);
    if (verdictDone && !signed) unsigned += 1;
    if (run && new Date(run.startedAt).toDateString() === new Date(now).toDateString()) redactionsToday += redactions;

    if (handlesPhi(req)) {
      rows.push({ id: req.id, title: req.title, phi: req.phi, privacyRan, criticals, highs, redactions, signed, verdictPending: verdictDone && !signed });
    }
    if (privacyRan && pr) {
      for (const s of pr.safeguards as SafeguardCheck[]) {
        rollup[s.id][s.status] += 1;
        rollup[s.id].total += 1;
      }
    }

    // --- alertas por requerimiento
    if (criticals > 0) {
      alerts.push({
        id: `phi-crit-${req.id}`,
        severity: "critica",
        title: `${req.id}: ${criticals} exposición(es) crítica(s) de PHI`,
        detail: "Privacidad detectó datos de paciente accesibles. Corregir y evaluar si corresponde notificar al responsable de privacidad.",
        href: `/requerimiento?id=${req.id}&tab=privacidad`,
        action: "ver hallazgos",
      });
    }
    if (handlesPhi(req) && view && view.state !== "en_curso" && !privacyRan && view.completed.length > 0) {
      alerts.push({
        id: `phi-sin-revision-${req.id}`,
        severity: "alta",
        title: `${req.id} maneja PHI y se ejecutó sin el agente de Privacidad`,
        detail: "El dictamen quedó limitado por la regla G5. Vuelve a ejecutar con Privacidad activo.",
        href: `/requerimiento?id=${req.id}&tab=plan`,
        action: "revisar plan",
      });
    }
    if (req.phi === "desconocido") {
      alerts.push({
        id: `phi-sin-clasificar-${req.id}`,
        severity: "baja",
        title: `${req.id} sin clasificar`,
        detail: "Se le aplica la política de PHI por defecto. Confírmalo con el área funcional para ajustar los controles.",
        href: `/requerimiento?id=${req.id}`,
        action: "clasificar",
      });
    }
    // ajustes locales con proveedor sin BAA en requerimientos con PHI
    for (const id of AGENT_ORDER) {
      const ov = req.profileOverrides[id];
      if (ov && handlesPhi(req) && PROVIDER_BAA[ov.provider] === false && AGENT_CARDS[id].receivesPhi === "redactada") {
        alerts.push({
          id: `baa-local-${req.id}-${id}`,
          severity: "alta",
          title: `${req.id}: ${AGENTS[id].label} ajustado a un proveedor sin BAA`,
          detail: `${PROVIDER_LABELS[ov.provider]} no tiene acuerdo BAA y este requerimiento maneja PHI.`,
          href: `/requerimiento?id=${req.id}&tab=plan`,
          action: "revisar ajuste",
        });
      }
    }
  }

  // --- proveedores y BAA
  const providers: ProviderRow[] = (Object.keys(PROVIDER_BAA) as ProviderId[])
    .map((provider) => {
      const agents = ALL_AGENTS.filter((a) => profiles[a].provider === provider);
      return { provider, baa: PROVIDER_BAA[provider], agents, phiAgents: agents.filter((a) => AGENT_CARDS[a].receivesPhi === "redactada") };
    })
    .filter((p) => p.agents.length > 0);

  const noBaaPhi = providers.filter((p) => p.baa === false && p.phiAgents.length > 0);
  for (const p of noBaaPhi) {
    alerts.push({
      id: `baa-${p.provider}`,
      severity: "alta",
      title: `${p.phiAgents.length} agente(s) con contexto de PHI usan ${PROVIDER_LABELS[p.provider]}, sin BAA`,
      detail: `${p.phiAgents.map((a) => AGENTS[a].label).join(", ")}. Reciben texto redactado, pero la política exige un proveedor con BAA.`,
      href: "/gobierno?tab=fichas",
      action: "ver fichas",
    });
  }

  // --- firmas, cambios y MFA
  if (unsigned > 0) {
    alerts.push({
      id: "sin-firma",
      severity: "media",
      title: `${unsigned} dictamen(es) sin firmar`,
      detail: "Un dictamen sin firma humana no sirve como evidencia para el pase a producción.",
      href: "/",
      action: "ver requerimientos",
    });
  }
  const pendingChanges = changeRequests.filter((c) => c.status === "pendiente");
  if (pendingChanges.length) {
    alerts.push({
      id: "cambios-pendientes",
      severity: "media",
      title: `${pendingChanges.length} solicitud(es) de cambio de agentes pendientes`,
      detail: `${pendingChanges.map((c) => c.id).join(", ")}. Mientras tanto siguen activas las versiones aprobadas.`,
      href: "/gobierno",
      action: "revisar",
    });
  }
  const noMfa = USERS.filter((u) => !u.mfa);
  if (noMfa.length) {
    alerts.push({
      id: "sin-mfa",
      severity: "media",
      title: `${noMfa.length} usuario(s) sin MFA`,
      detail: `${noMfa.map((u) => u.name).join(", ")}. La actualización de la regla de seguridad exige MFA para acceder a sistemas con ePHI.`,
    });
  }

  alerts.sort((a, b) => SEV_RANK[a.severity] - SEV_RANK[b.severity]);

  return {
    alerts,
    rows,
    providers,
    safeguards: Object.values(rollup).filter((r) => r.total > 0),
    kpis: {
      phiRequirements: requirements.filter((r) => handlesPhi(r)).length,
      totalRequirements: requirements.length,
      redactionsToday,
      unsigned,
      pendingChanges: pendingChanges.length,
      noMfa: noMfa.length,
      noBaaAgents: noBaaPhi.reduce((s, p) => s + p.phiAgents.length, 0),
    },
  };
}
