import type { AppUser, Attachment, Requirement } from "./types";
import { AGENT_ORDER, defaultProfiles } from "./agents";

export const USERS: AppUser[] = [
  { id: "u-emanuel", name: "Emanuel", role: "Desarrollador", initials: "EM" },
  { id: "u-lucia", name: "Lucía Fernández", role: "QA", initials: "LF" },
  { id: "u-martin", name: "Martín Rojas", role: "Líder técnico", initials: "MR" },
  { id: "u-carla", name: "Carla Méndez", role: "Analista funcional", initials: "CM" },
  { id: "u-diego", name: "Diego Salas", role: "Desarrollador", initials: "DS" },
  { id: "u-valentina", name: "Valentina Ortiz", role: "Arquitecta", initials: "VO" },
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
      title: "Conciliación automática de pagos con tarjeta",
      description:
        "Crear un proceso diario que concilie los pagos con tarjeta registrados en el core contra el fichero del adquirente, registre las discrepancias en base de datos y permita consultarlas desde un endpoint para el área de operaciones.",
      acceptanceCriteria: [
        "El proceso se ejecuta todos los días a las 06:00 y procesa el fichero del día anterior.",
        "Cada pago sin correspondencia o con importe distinto queda registrado como discrepancia.",
        "Operaciones puede listar las discrepancias filtrando por fecha y comercio.",
      ],
      owner: "u-emanuel",
      createdAt: "2026-09-10T10:12:00.000Z",
      scenario: "pagos",
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
          enabledAgents: ["orchestrator", "code", "tests", "kiuwan", "sql", "vtr", "verdict"],
          profiles: snapshot,
        },
      ],
      profileOverrides: {},
    },
    {
      id: "REQ-1057",
      title: "Nuevo formulario de alta de clientes en portal web",
      description:
        "Rediseñar la pantalla de alta de clientes del portal web como un formulario de tres pasos con validaciones, guardado de borrador y carga del documento de identidad.",
      acceptanceCriteria: [
        "El formulario se divide en tres pasos y no permite avanzar con datos inválidos.",
        "El DNI y el email se validan antes de enviar.",
        "Se puede adjuntar un documento de identidad de hasta 5 MB.",
        "El borrador se conserva si el usuario recarga la página.",
      ],
      owner: "u-diego",
      createdAt: "2026-09-13T15:40:00.000Z",
      scenario: "portal",
      attachments: [
        att("b1", "repo", "https://git.empresa.local/canales/portal-clientes.git", "feature/REQ-1057-alta-3-pasos", "u-diego", "2026-09-13T15:42:00.000Z"),
        att("b2", "vtr_template", "VTR_modelo.docx", "9 secciones · 48 KB", "u-carla", "2026-09-13T15:50:00.000Z"),
        att("b3", "kiuwan_csv", "kiuwan_REQ-1057.csv", "12 filas · 3 KB", "u-lucia", "2026-09-14T09:10:00.000Z"),
      ],
      plan: null,
      runs: [],
      profileOverrides: {},
    },
    {
      id: "REQ-1061",
      title: "Reporte mensual de comisiones por comercio",
      description:
        "Generar un reporte mensual con las comisiones cobradas a cada comercio a partir de la tabla de operaciones, exportable a Excel para el área comercial.",
      acceptanceCriteria: [
        "El reporte agrupa las comisiones por comercio y mes.",
        "Se puede exportar a Excel desde el backoffice.",
      ],
      owner: "u-martin",
      createdAt: "2026-09-15T08:30:00.000Z",
      scenario: "pagos",
      attachments: [
        att("c1", "repo", "https://git.empresa.local/pagos/backoffice.git", "feature/REQ-1061-comisiones", "u-martin", "2026-09-15T08:31:00.000Z"),
      ],
      plan: null,
      runs: [],
      profileOverrides: {},
    },
  ];
}
