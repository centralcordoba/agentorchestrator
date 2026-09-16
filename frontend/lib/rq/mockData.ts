import type { AgentId, AgentProfile, AppUser, Attachment, AuditEntry, ChangeRequest, Requirement } from "./types";
import { AGENT_ORDER, defaultProfiles } from "./agents";
import { appendAudit, evaluateChange, snapshot } from "./governance";

export const USERS: AppUser[] = [
  { id: "u-emanuel", name: "Emanuel", role: "Desarrollador", initials: "EM", mfa: true },
  { id: "u-lucia", name: "Lucía Fernández", role: "QA", initials: "LF", mfa: true },
  { id: "u-martin", name: "Martín Rojas", role: "Líder técnico", initials: "MR", mfa: true },
  { id: "u-carla", name: "Carla Méndez", role: "Analista funcional", initials: "CM", mfa: false },
  { id: "u-diego", name: "Diego Salas", role: "Desarrollador", initials: "DS", mfa: false },
  { id: "u-valentina", name: "Valentina Ortiz", role: "Arquitecta", initials: "VO", mfa: true },
];

export function userName(id: string): string {
  return USERS.find((u) => u.id === id)?.name ?? id;
}

function att(id: string, kind: Attachment["kind"], name: string, detail: string, addedBy: string, addedAt: string): Attachment {
  return { id, kind, name, detail, addedBy, addedAt };
}

const allOn = (except: string[] = []) =>
  AGENT_ORDER.filter((a) => a !== "orchestrator" && a !== "verdict").map((a) => ({
    agentId: a,
    suggested: !except.includes(a),
    enabled: !except.includes(a),
    reason: "",
  }));

export function seedRequirements(): Requirement[] {
  const profiles = defaultProfiles();
  const snapshot = Object.fromEntries(
    AGENT_ORDER.map((a) => [a, { provider: profiles[a].provider, model: profiles[a].model, promptVersion: 1 }]),
  ) as Requirement["runs"][number]["profiles"];

  return [
    {
      id: "REQ-1042",
      title: "Conciliación automática de copagos con tarjeta",
      description:
        "Crear un proceso diario que concilie los copagos de pacientes cobrados con tarjeta contra el fichero del adquirente, registre las discrepancias en base de datos y permita consultarlas desde un endpoint para el área de facturación.",
      acceptanceCriteria: [
        "El proceso se ejecuta todos los días a las 06:00 y procesa el fichero del día anterior.",
        "Cada pago sin correspondencia o con importe distinto queda registrado como discrepancia.",
        "Facturación puede listar las discrepancias filtrando por fecha y centro médico.",
      ],
      owner: "u-emanuel",
      createdAt: "2026-09-10T10:12:00.000Z",
      scenario: "pagos",
      phi: "si",
      phiSetBy: "u-carla",
      attachments: [
        att("a1", "repo", "https://git.empresa.local/pagos/core-pagos.git", "feature/REQ-1042-conciliacion", "u-emanuel", "2026-09-10T10:15:00.000Z"),
        att("a2", "vtr_template", "VTR_modelo.docx", "9 secciones · 48 KB", "u-carla", "2026-09-10T10:20:00.000Z"),
        att("a3", "kiuwan_csv", "kiuwan_REQ-1042.csv", "37 filas · 9 KB", "u-lucia", "2026-09-11T08:02:00.000Z"),
        att("a4", "sql", "V2026_09_10__tabla_discrepancias.sql", "4 sentencias · 2 KB", "u-emanuel", "2026-09-10T10:16:00.000Z"),
      ],
      plan: {
        suggestedAt: "2026-09-11T08:05:00.000Z",
        items: allOn(["uiux"]).map((i) => ({
          ...i,
          reason:
            i.agentId === "uiux"
              ? "El requerimiento no menciona pantallas y no hay cambios de frontend en el repositorio."
              : "Sugerido por el orquestador.",
        })),
      },
      runs: [
        {
          id: "run-1042-a",
          requirementId: "REQ-1042",
          startedBy: "u-emanuel",
          startedAt: Date.parse("2026-09-11T08:07:00.000Z"),
          speed: "rapido",
          enabledAgents: ["orchestrator", "code", "tests", "kiuwan", "sql", "privacy", "vtr", "verdict"],
          profiles: snapshot,
        },
      ],
      profileOverrides: {},
    },
    {
      id: "REQ-1057",
      title: "Nuevo formulario de alta de pacientes en el portal web",
      description:
        "Rediseñar la pantalla de alta de pacientes del portal web como un formulario de tres pasos con validaciones, guardado de borrador y carga del documento de identidad y la tarjeta del seguro médico.",
      acceptanceCriteria: [
        "El formulario se divide en tres pasos y no permite avanzar con datos inválidos.",
        "El DNI y el email se validan antes de enviar.",
        "Se puede adjuntar un documento de identidad de hasta 5 MB.",
        "El borrador se conserva si el usuario recarga la página.",
      ],
      owner: "u-diego",
      createdAt: "2026-09-13T15:40:00.000Z",
      scenario: "portal",
      phi: "si",
      phiSetBy: "u-diego",
      attachments: [
        att("b1", "repo", "https://git.empresa.local/canales/portal-pacientes.git", "feature/REQ-1057-alta-3-pasos", "u-diego", "2026-09-13T15:42:00.000Z"),
        att("b2", "vtr_template", "VTR_modelo.docx", "9 secciones · 48 KB", "u-carla", "2026-09-13T15:50:00.000Z"),
        att("b3", "kiuwan_csv", "kiuwan_REQ-1057.csv", "12 filas · 3 KB", "u-lucia", "2026-09-14T09:10:00.000Z"),
      ],
      plan: null,
      runs: [],
      profileOverrides: {},
    },
    {
      id: "REQ-1061",
      title: "Reporte mensual de prestaciones por centro médico",
      description:
        "Generar un reporte mensual con las prestaciones facturadas por cada centro médico a partir de la tabla de operaciones, exportable a Excel para el área de gestión.",
      acceptanceCriteria: [
        "El reporte agrupa las prestaciones por centro médico y mes.",
        "Se puede exportar a Excel desde el backoffice.",
      ],
      owner: "u-martin",
      createdAt: "2026-09-15T08:30:00.000Z",
      scenario: "pagos",
      phi: "desconocido",
      attachments: [
        att("c1", "repo", "https://git.empresa.local/pagos/backoffice.git", "feature/REQ-1061-comisiones", "u-martin", "2026-09-15T08:31:00.000Z"),
      ],
      plan: null,
      runs: [],
      profileOverrides: {},
    },
  ];
}

/** Aplica una configuración aprobada a un perfil: si cambia el prompt, crea una versión nueva. */
export function applyToProfile(prev: AgentProfile, next: Omit<AgentProfile, "agentId" | "versions" | "promptVersion">, author: string, note: string, at = new Date().toISOString()): AgentProfile {
  const promptChanged = prev.systemPrompt !== next.systemPrompt || prev.taskPrompt !== next.taskPrompt;
  const version = promptChanged ? Math.max(...prev.versions.map((v) => v.version)) + 1 : prev.promptVersion;
  return {
    ...prev,
    ...next,
    promptVersion: version,
    versions: promptChanged ? [...prev.versions, { version, savedAt: at, author, note: note || "Sin nota", systemPrompt: next.systemPrompt, taskPrompt: next.taskPrompt }] : prev.versions,
  };
}

export function seedGovernance(): { profiles: Record<AgentId, AgentProfile>; changeRequests: ChangeRequest[]; audit: AuditEntry[] } {
  const profiles = defaultProfiles();

  // CR-001 (aprobada): Código cita datos de paciente. Ya aplicada: el perfil queda en v2.
  const codeBefore = snapshot(profiles.code);
  const codeAfter = { ...codeBefore, systemPrompt: `${codeBefore.systemPrompt} Señala de forma explícita cualquier dato de paciente (PHI) que aparezca en el diff, sin repetir su valor.`, promptVersion: 2 };
  const cr1: ChangeRequest = { id: "CR-001", agentId: "code", createdBy: "u-diego", createdAt: "2026-09-12T09:10:00.000Z", justification: "Tras la auditoría interna, el revisor de código debe avisar cuando el diff contiene PHI aunque Privacidad esté desactivado.", before: codeBefore, after: codeAfter, status: "aprobada" };
  cr1.evaluation = { ...evaluateChange(cr1, "u-diego"), runAt: "2026-09-12T09:25:00.000Z" };
  cr1.review = { by: "u-martin", at: "2026-09-12T11:02:00.000Z", comment: "Sin regresiones y con mejora en el caso E1. Aprobado." };
  profiles.code = applyToProfile(profiles.code, codeAfter, "Diego Salas", "CR-001 · Señalar PHI en el diff", "2026-09-12T11:02:00.000Z");

  // CR-002 (rechazada): más temperatura en Tests.
  const testsBefore = snapshot(profiles.tests);
  const cr2: ChangeRequest = { id: "CR-002", agentId: "tests", createdBy: "u-diego", createdAt: "2026-09-13T16:40:00.000Z", justification: "Subir la temperatura para que genere casos de prueba más variados.", before: testsBefore, after: { ...testsBefore, temperature: 0.7 }, status: "rechazada" };
  cr2.evaluation = { ...evaluateChange(cr2, "u-lucia"), runAt: "2026-09-13T17:05:00.000Z" };
  cr2.review = { by: "u-valentina", at: "2026-09-14T08:30:00.000Z", comment: "Dos regresiones por resultados inestables (E3 y E6). Preferimos casos variados mediante el prompt, no con temperatura." };

  // CR-003 (pendiente): Kiuwan a un modelo más capaz, con prompt ampliado. Sin evaluar todavía.
  const kiuBefore = snapshot(profiles.kiuwan);
  const cr3: ChangeRequest = {
    id: "CR-003",
    agentId: "kiuwan",
    createdBy: "u-emanuel",
    createdAt: "2026-09-15T09:30:00.000Z",
    justification: "Priorizar mejor los defectos de seguridad que afectan a PHI: pasar a Gemini 3.5 Flash e indicar la salvaguarda HIPAA de cada defecto.",
    before: kiuBefore,
    after: { ...kiuBefore, model: "google/gemini-3.5-flash", systemPrompt: `${kiuBefore.systemPrompt} Si un defecto puede exponer PHI, indica la salvaguarda HIPAA afectada (164.312).`, promptVersion: 2 },
    status: "pendiente",
  };

  let audit: AuditEntry[] = [];
  const add = (at: string, actor: string, action: Parameters<typeof appendAudit>[2], target: string, detail: string) => {
    audit = appendAudit(audit, actor, action, target, detail, at);
  };
  add("2026-09-10T10:12:00.000Z", "u-emanuel", "requerimiento_creado", "REQ-1042", "Conciliación automática de copagos con tarjeta");
  add("2026-09-10T10:20:00.000Z", "u-carla", "clasificacion_phi", "REQ-1042", "Clasificado: Sí, puede tocar PHI");
  add("2026-09-11T08:07:00.000Z", "u-emanuel", "ejecucion_iniciada", "REQ-1042", "run-1042-a · 6 agentes especialistas");
  add("2026-09-12T09:10:00.000Z", "u-diego", "cambio_solicitado", "CR-001", "Código · prompt");
  add("2026-09-12T09:25:00.000Z", "u-diego", "cambio_evaluado", "CR-001", "0 regresiones · 1 mejora");
  add("2026-09-12T11:02:00.000Z", "u-martin", "cambio_aprobado", "CR-001", "Código pasa a prompt v2");
  add("2026-09-13T15:40:00.000Z", "u-diego", "requerimiento_creado", "REQ-1057", "Nuevo formulario de alta de pacientes en el portal web");
  add("2026-09-13T15:41:00.000Z", "u-diego", "clasificacion_phi", "REQ-1057", "Clasificado: Sí, puede tocar PHI");
  add("2026-09-13T16:40:00.000Z", "u-diego", "cambio_solicitado", "CR-002", "Tests · temperatura");
  add("2026-09-13T17:05:00.000Z", "u-lucia", "cambio_evaluado", "CR-002", "2 regresiones");
  add("2026-09-14T08:30:00.000Z", "u-valentina", "cambio_rechazado", "CR-002", "Regresiones E3 y E6");
  add("2026-09-15T08:30:00.000Z", "u-martin", "requerimiento_creado", "REQ-1061", "Reporte mensual de prestaciones por centro médico");
  add("2026-09-15T09:30:00.000Z", "u-emanuel", "cambio_solicitado", "CR-003", "Kiuwan · modelo y prompt");

  return { profiles, changeRequests: [cr1, cr2, cr3], audit };
}
