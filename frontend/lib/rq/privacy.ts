// Agente de Privacidad HIPAA: catálogo de salvaguardas, detección de PHI en el diff y señales para clasificar
// el requerimiento. Las reglas son deterministas y nunca guardan ni muestran el valor detectado.
import { addedLines } from "./diff";
import type { Finding, PhiClassification, PhiDetection, PhiIdentifier, PrivacyReport, RepoInfo, Requirement, SafeguardCheck, SafeguardId, Severity } from "./types";

export const SAFEGUARDS: { id: SafeguardId; label: string; cfr: string; question: string }[] = [
  { id: "acceso", label: "Control de acceso", cfr: "164.312(a)", question: "¿Solo acceden a la PHI los usuarios y procesos autorizados, con cifrado en reposo?" },
  { id: "auditoria", label: "Controles de auditoría", cfr: "164.312(b)", question: "¿Queda registro de quién consulta o modifica PHI?" },
  { id: "integridad", label: "Integridad", cfr: "164.312(c)", question: "¿Se protege la PHI frente a alteraciones o borrados indebidos?" },
  { id: "autenticacion", label: "Autenticación", cfr: "164.312(d)", question: "¿Se verifica la identidad de quien accede a la PHI?" },
  { id: "transmision", label: "Seguridad en la transmisión", cfr: "164.312(e)", question: "¿La PHI viaja cifrada y por canales seguros?" },
];

export const SAFEGUARD_LABEL: Record<SafeguardId, string> = Object.fromEntries(SAFEGUARDS.map((s) => [s.id, `${s.label} · ${s.cfr}`])) as Record<SafeguardId, string>;

export const IDENTIFIER_LABELS: Record<PhiIdentifier, string> = {
  nombre: "Nombre",
  fecha: "Fecha de nacimiento",
  telefono: "Teléfono",
  email: "Email",
  ssn: "SSN",
  historia_clinica: "N.º de historia clínica",
  afiliado: "N.º de afiliado / póliza",
  direccion: "Dirección",
  documento: "Documento de identidad",
  dato_paciente: "Dato de paciente",
};

export const WHERE_LABELS: Record<PhiDetection["where"], string> = {
  datos_prueba: "datos de prueba",
  log: "logs",
  sql: "SQL",
  codigo: "código",
  url: "URL",
  almacenamiento_local: "almacenamiento del navegador",
};

export const PHI_LABELS: Record<PhiClassification, string> = { si: "Sí, puede tocar PHI", no: "No toca PHI", desconocido: "No se sabe" };

/** "No se sabe" se trata como "sí": ante la duda se aplica la política estricta. */
export function handlesPhi(req: Pick<Requirement, "phi">): boolean {
  return req.phi !== "no";
}

// ------------------------------------------------------------------ reglas sobre el diff

interface PrivacyRule {
  id: string;
  severity: Severity;
  safeguard: SafeguardId;
  title: string;
  detail: string;
  suggestion: string;
  test: RegExp;
  identifier?: PhiIdentifier;
  where?: PhiDetection["where"];
  /** Rebaja la severidad si el valor es un ficticio conocido (p. ej. 123-45-6789). */
  knownFake?: RegExp;
}

const RULES: PrivacyRule[] = [
  { id: "PHI-SSN", severity: "critica", safeguard: "acceso", identifier: "ssn", title: "Posible SSN en el código o en datos de prueba", detail: "Aparece un valor con formato de número de la seguridad social.", suggestion: "Sustituir por datos sintéticos generados (p. ej. Synthea) y purgar el historial si era real.", test: /\b\d{3}-\d{2}-\d{4}\b/, knownFake: /\b(000-00-0000|123-45-6789|999-99-9999)\b/ },
  { id: "PHI-MRN", severity: "critica", safeguard: "acceso", identifier: "historia_clinica", title: "Número de historia clínica literal", detail: "Se asigna un identificador de historia clínica con valor fijo.", suggestion: "Usar identificadores sintéticos o tokenizados.", test: /\b(mrn|medical_?record(_?(number|no|id))?|historia_?clinica|nhc)\b["']?\s*[:=]\s*["']?[A-Z]*\d{5,}/i },
  { id: "PHI-DOB", severity: "alta", safeguard: "acceso", identifier: "fecha", title: "Fecha de nacimiento literal", detail: "Se asigna una fecha de nacimiento concreta.", suggestion: "Generar fechas sintéticas o desplazadas.", test: /\b(dob|birth_?date|date_?of_?birth|fecha_?nac\w*)\b["']?\s*[:=]\s*["']?\d{4}-\d{2}-\d{2}/i },
  { id: "PHI-MEMBER", severity: "alta", safeguard: "acceso", identifier: "afiliado", title: "Número de afiliado o póliza literal", detail: "Se asigna un identificador de seguro médico con valor fijo.", suggestion: "Usar identificadores sintéticos.", test: /\b(member_?id|policy_?(number|no)|insurance_?id|afiliado)\b["']?\s*[:=]\s*["']?[A-Z0-9-]{6,}/i },
  { id: "PHI-LOG", severity: "alta", safeguard: "acceso", where: "log", title: "Datos de paciente escritos en logs", detail: "Una traza incluye variables con datos de paciente; los logs suelen copiarse a sistemas sin controles de PHI.", suggestion: "Registrar solo identificadores tokenizados y enmascarar el resto.", test: /\b(log(ger)?|console|System\.out|print)\b[\w.]*\s*\(.*\b(patient|paciente|ssn|dob|diagnos\w*|mrn|member_?id|afiliado)\b/i },
  { id: "PHI-URL", severity: "alta", safeguard: "transmision", where: "url", title: "PHI en parámetros de URL", detail: "Los parámetros de consulta quedan en logs de servidores, proxies e historial del navegador.", suggestion: "Enviar esos datos en el cuerpo de una petición POST sobre TLS.", test: /[?&](ssn|dob|mrn|patient_?id|member_?id|dni|diagnosis)=/i },
  { id: "PHI-LOCALSTORAGE", severity: "alta", safeguard: "acceso", where: "almacenamiento_local", title: "Datos de paciente guardados en el navegador", detail: "localStorage y sessionStorage no están cifrados y los lee cualquier script de la página.", suggestion: "Guardar el borrador en el servidor o cifrarlo con una clave de sesión.", test: /(localStorage|sessionStorage)\.setItem\(.*\b(patient|paciente|dni|ssn|dob|phone|telefono|afiliado)\b/i },
  { id: "TLS-OFF", severity: "alta", safeguard: "transmision", title: "Verificación TLS desactivada", detail: "La conexión acepta certificados no válidos: permite interceptar la PHI en tránsito.", suggestion: "Eliminar la opción y confiar en los certificados de la organización.", test: /(verify\s*=\s*False|rejectUnauthorized\s*:\s*false|InsecureSkipVerify\s*:\s*true|NODE_TLS_REJECT_UNAUTHORIZED)/ },
  { id: "HTTP-PLAIN", severity: "media", safeguard: "transmision", title: "Llamada a un servicio por HTTP sin cifrar", detail: "La URL usa http:// fuera de localhost.", suggestion: "Usar https://.", test: /["'`]http:\/\/(?!localhost|127\.0\.0\.1|0\.0\.0\.0|example\.)[\w.-]+/i },
];

const TEST_PATH = /(^|\/)(test|tests|__tests__|spec|fixtures?)\/|[._-](test|spec)\.[a-z]+$/i;
const PHI_PATH = /(fhir|hl7|patient|paciente|encounter|observation|diagnos|ehr|emr|clinic|medical|health|claim|member|afiliad)/i;

function whereFor(path: string, rule: PrivacyRule): PhiDetection["where"] {
  if (rule.where) return rule.where;
  if (/\.sql$/i.test(path)) return "sql";
  return TEST_PATH.test(path) ? "datos_prueba" : "codigo";
}

export function analyzePrivacy(
  files: { filename: string; status: string; patch?: string }[],
  blob: (path: string, line?: number) => string,
): { findings: Finding[]; detections: PhiDetection[]; signals: string[] } {
  const findings: Finding[] = [];
  const detections: PhiDetection[] = [];
  let seq = 0;
  for (const f of files) {
    if (f.status === "removed" || !f.patch) continue;
    const lines = addedLines(f.patch);
    for (const rule of RULES) {
      const hits = lines.filter((l) => rule.test.test(l.text));
      if (!hits.length) continue;
      const first = hits[0];
      const fake = rule.knownFake && hits.every((h) => rule.knownFake!.test(h.text));
      const where = whereFor(f.filename, rule);
      findings.push({
        id: `P${++seq}`,
        source: "privacy",
        severity: fake ? "baja" : rule.severity,
        safeguard: rule.safeguard,
        title: fake ? `${rule.title} (valor ficticio conocido)` : rule.title,
        detail: `${rule.detail}${hits.length > 1 ? ` ${hits.length} líneas en este archivo.` : ""} El valor no se muestra.`,
        suggestion: rule.suggestion,
        file: f.filename,
        line: first.line,
        url: blob(f.filename, first.line),
      });
      if (rule.identifier || rule.where) {
        for (const h of hits.slice(0, 5)) {
          detections.push({
            identifier: rule.identifier ?? "dato_paciente",
            file: f.filename,
            line: h.line,
            where,
            masked: `${IDENTIFIER_LABELS[rule.identifier ?? "dato_paciente"]} en ${WHERE_LABELS[where]} · valor oculto`,
            url: blob(f.filename, h.line),
          });
        }
      }
    }
  }
  const signals = Array.from(new Set(files.map((f) => f.filename).filter((p) => PHI_PATH.test(p)))).slice(0, 8);
  return { findings, detections, signals };
}

/** Informe de privacidad a partir de un repositorio real: una salvaguarda está en riesgo si hay hallazgos que la afectan. */
export function realPrivacyReport(repo: RepoInfo): PrivacyReport {
  const findings = repo.findings.filter((f) => f.source === "privacy");
  const safeguards: SafeguardCheck[] = SAFEGUARDS.map((s) => {
    const hits = findings.filter((f) => f.safeguard === s.id);
    return hits.length
      ? { id: s.id, status: "riesgo", evidence: hits.map((h) => `${h.title} (${h.file}:${h.line})`).join(" · ") }
      : { id: s.id, status: "sin_evidencia", evidence: "Las reglas no encontraron problemas, pero confirmarlo requiere la revisión con LLM." };
  });
  return {
    detections: repo.phiDetections,
    safeguards,
    minimumNecessary: repo.phiSignals.length
      ? `El diff toca rutas relacionadas con datos de salud (${repo.phiSignals.slice(0, 3).join(", ")}). Revisar que solo se lean los campos imprescindibles.`
      : "El diff no toca rutas con nombres asociados a datos de salud.",
    findings,
  };
}

/**
 * Pasarela DLP para el texto que escribe una persona (chat, comentarios).
 * Devuelve los tipos de identificador detectados; nunca el valor.
 */
const TYPED_PHI: { identifier: PhiIdentifier; test: RegExp }[] = [
  { identifier: "ssn", test: /\b\d{3}-\d{2}-\d{4}\b/ },
  { identifier: "historia_clinica", test: /\b(mrn|historia\s*cl[ií]nica|nhc|expediente)\b\s*:?\s*[A-Z]*\d{4,}/i },
  { identifier: "afiliado", test: /\b(afiliado|p[oó]liza|member\s*id|policy)\b\s*:?\s*[A-Z0-9-]{5,}/i },
  { identifier: "fecha", test: /\b(nacid[oa]|fecha\s*de\s*nacimiento|dob)\b\s*:?\s*\d{1,4}[-/]\d{1,2}[-/]\d{1,4}/i },
  { identifier: "telefono", test: /(?:\+?\d[\d\s().-]{8,}\d)/ },
  { identifier: "email", test: /[\w.+-]+@(?!ejemplo\.|example\.)[\w-]+\.[a-z]{2,}/i },
  { identifier: "documento", test: /\b\d{7,8}[A-Za-z]\b/ },
];

export function scanTypedText(text: string): PhiIdentifier[] {
  return TYPED_PHI.filter((r) => r.test.test(text)).map((r) => r.identifier);
}

// ------------------------------------------------------------------ sugerencia de clasificación

const PHI_WORDS = ["paciente", "pacientes", "historia clínica", "diagnóstico", "receta", "afiliado", "aseguradora", "copago", "laboratorio", "clínico", "clínica", "médico", "salud", "fhir", "hl7", "hipaa", "phi"];

export function suggestPhi(req: Requirement): { value: PhiClassification; reason: string } {
  const text = `${req.title} ${req.description} ${req.acceptanceCriteria.join(" ")}`.toLowerCase();
  const word = PHI_WORDS.find((w) => new RegExp(`(^|[^a-záéíóúüñ])${w}($|[^a-záéíóúüñ])`).test(text));
  const repo = req.attachments.find((a) => a.kind === "repo")?.repo;
  if (repo?.phiDetections.length) return { value: "si", reason: `El diff contiene ${repo.phiDetections.length} posible(s) identificador(es) de paciente.` };
  if (repo?.phiSignals.length) return { value: "si", reason: `El diff toca rutas de datos de salud: ${repo.phiSignals.slice(0, 2).join(", ")}.` };
  if (word) return { value: "si", reason: `El requerimiento menciona «${word}».` };
  return { value: "desconocido", reason: "No hay señales claras. Mientras no se confirme, se aplica la política de PHI." };
}
