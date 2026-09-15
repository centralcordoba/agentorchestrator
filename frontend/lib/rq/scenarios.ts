// Entregables simulados por escenario. En el prototipo sin backend, cada requerimiento
// apunta a un escenario y los agentes "producen" estos resultados durante la ejecución.
import { languageSummary } from "./github";
import type { AgentId, ChangeMapEntry, Deliverables, Finding, Requirement, ScenarioId, Severity, Verdict, VerdictReport } from "./types";

type ScenarioDeliverables = Omit<Deliverables, "verdict" | "realRepo">;
type BaseDeliverables = Omit<Deliverables, "verdict">;

const PAGOS: ScenarioDeliverables = {
  code: {
    stack: "Java 21 · Spring Boot 3 · Oracle 19c",
    summary:
      "Se añade un job programado que concilia los pagos con tarjeta contra el fichero diario del adquirente. El cambio introduce un servicio de conciliación, un repositorio con consultas nativas y un endpoint de consulta de discrepancias.",
    changeMap: [
      { file: "src/main/java/com/banco/pagos/conciliacion/ConciliacionService.java", change: "nuevo", added: 214, removed: 0, symbols: ["ConciliacionService.conciliarDia", "ConciliacionService.marcarDiscrepancia"], criteria: [0, 1] },
      { file: "src/main/java/com/banco/pagos/conciliacion/ConciliacionJob.java", change: "nuevo", added: 48, removed: 0, symbols: ["ConciliacionJob.run"], criteria: [0] },
      { file: "src/main/java/com/banco/pagos/conciliacion/ReporteRepository.java", change: "nuevo", added: 96, removed: 0, symbols: ["ReporteRepository.buscarDiscrepancias"], criteria: [2] },
      { file: "src/main/java/com/banco/pagos/api/DiscrepanciaController.java", change: "modificado", added: 37, removed: 6, symbols: ["DiscrepanciaController.listar"], criteria: [2] },
      { file: "src/main/resources/application.yml", change: "modificado", added: 4, removed: 0, symbols: ["conciliacion.cron"], criteria: [0] },
      { file: "db/migrations/V2026_09_10__tabla_discrepancias.sql", change: "nuevo", added: 41, removed: 0, symbols: ["PAG_DISCREPANCIA"], criteria: [1] },
    ],
    findings: [
      { id: "C1", severity: "alta", source: "code", title: "Comparación de importes con double", file: "ConciliacionService.java", line: 118, detail: "Los importes se comparan con `double`, lo que produce discrepancias falsas por redondeo (p. ej. 10.10 vs 10.1000001).", suggestion: "Usar BigDecimal con compareTo y escala 2." },
      { id: "C2", severity: "media", source: "code", title: "El job no es idempotente", file: "ConciliacionJob.java", line: 31, detail: "Si el job se relanza el mismo día, se insertan discrepancias duplicadas.", suggestion: "Registrar la fecha conciliada y comprobarla antes de procesar." },
      { id: "C3", severity: "baja", source: "code", title: "Excepción genérica silenciada", file: "ConciliacionService.java", line: 164, detail: "`catch (Exception e)` solo registra el mensaje y continúa, sin traza ni métrica." },
      { id: "C4", severity: "info", source: "code", title: "Criterio 3 cubierto parcialmente", file: "DiscrepanciaController.java", line: 22, detail: "El endpoint lista discrepancias pero no permite filtrar por fecha como pide el criterio." },
    ],
  },
  tests: {
    framework: "JUnit 5 · Mockito",
    command: "mvn -q test -Dtest=Conciliacion*GeneratedTest",
    coverage: 71,
    tests: [
      { name: "concilia_pago_con_importe_identico", file: "ConciliacionServiceGeneratedTest.java", kind: "unitario", criterion: 0, status: "paso", durationMs: 42, code: `@Test\nvoid concilia_pago_con_importe_identico() {\n  var pago = pago("TX-1", "10.10");\n  var linea = linea("TX-1", "10.10");\n  var r = service.conciliarDia(List.of(pago), List.of(linea));\n  assertThat(r.discrepancias()).isEmpty();\n}` },
      { name: "detecta_pago_ausente_en_fichero", file: "ConciliacionServiceGeneratedTest.java", kind: "unitario", criterion: 1, status: "paso", durationMs: 38, code: `@Test\nvoid detecta_pago_ausente_en_fichero() {\n  var r = service.conciliarDia(List.of(pago("TX-2", "5.00")), List.of());\n  assertThat(r.discrepancias()).extracting("tipo").containsExactly(AUSENTE_EN_ADQUIRENTE);\n}` },
      { name: "no_marca_discrepancia_por_redondeo", file: "ConciliacionServiceGeneratedTest.java", kind: "unitario", criterion: 1, status: "fallo", durationMs: 51, failureReason: "Esperado: sin discrepancias · Obtenido: 1 discrepancia IMPORTE_DISTINTO (10.1 vs 10.10). Confirma el hallazgo C1: la comparación con double es un bug del código, no de la prueba.", code: `@Test\nvoid no_marca_discrepancia_por_redondeo() {\n  var r = service.conciliarDia(List.of(pago("TX-3", "10.1")), List.of(linea("TX-3", "10.10")));\n  assertThat(r.discrepancias()).isEmpty();\n}` },
      { name: "job_relanzado_no_duplica", file: "ConciliacionJobGeneratedTest.java", kind: "integracion", criterion: 0, status: "fallo", durationMs: 612, failureReason: "Tras ejecutar el job dos veces para 2026-09-10 hay 4 filas en PAG_DISCREPANCIA (esperadas 2). Confirma el hallazgo C2.", code: `@Test\nvoid job_relanzado_no_duplica() {\n  job.run(LocalDate.of(2026, 9, 10));\n  job.run(LocalDate.of(2026, 9, 10));\n  assertThat(repo.count()).isEqualTo(2);\n}` },
      { name: "endpoint_lista_discrepancias", file: "DiscrepanciaControllerGeneratedTest.java", kind: "integracion", criterion: 2, status: "paso", durationMs: 284, code: `@Test\nvoid endpoint_lista_discrepancias() throws Exception {\n  mvc.perform(get("/api/discrepancias"))\n     .andExpect(status().isOk())\n     .andExpect(jsonPath("$.length()").value(2));\n}` },
    ],
    findings: [
      { id: "T1", severity: "alta", source: "tests", title: "Prueba de redondeo falla (confirma C1)", file: "ConciliacionServiceGeneratedTest.java", detail: "no_marca_discrepancia_por_redondeo falla por la comparación con double." },
      { id: "T2", severity: "media", source: "tests", title: "Job no idempotente (confirma C2)", file: "ConciliacionJobGeneratedTest.java", detail: "job_relanzado_no_duplica inserta filas duplicadas." },
    ],
  },
  kiuwan: {
    fileName: "kiuwan_REQ-1042.csv",
    rows: 37,
    defects: [
      { ruleId: "OPT.JAVA.SEC_JAVA.SqlInjectionRule", rule: "Inyección SQL", severity: "critica", category: "Seguridad", file: "ReporteRepository.java", line: 58, falsePositive: false, note: "Confirmado por Código: el filtro `comercio` se concatena en la consulta nativa." },
      { ruleId: "OPT.JAVA.SEC_JAVA.HardcodedPassword", rule: "Credencial en código", severity: "alta", category: "Seguridad", file: "application-test.yml", line: 12, falsePositive: true, note: "Falso positivo: perfil de pruebas con base H2 en memoria, no se despliega." },
      { ruleId: "OPT.JAVA.RGP.AvoidCatchingGenericException", rule: "Captura de excepción genérica", severity: "media", category: "Fiabilidad", file: "ConciliacionService.java", line: 164, falsePositive: false, note: "Coincide con el hallazgo C3 de Código." },
      { ruleId: "OPT.JAVA.EFICIENCIA.StringConcatInLoop", rule: "Concatenación de String en bucle", severity: "baja", category: "Eficiencia", file: "ConciliacionService.java", line: 141, falsePositive: false, note: "Usar StringBuilder." },
      { ruleId: "OPT.JAVA.MANT.MethodTooLong", rule: "Método demasiado largo", severity: "baja", category: "Mantenibilidad", file: "ConciliacionService.java", line: 88, falsePositive: false, note: "conciliarDia tiene 96 líneas." },
      { ruleId: "OPT.JAVA.DOC.MissingJavadoc", rule: "Falta Javadoc en API pública", severity: "info", category: "Documentación", file: "DiscrepanciaController.java", line: 18, falsePositive: false, note: "" },
    ],
    findings: [
      { id: "K1", severity: "critica", source: "kiuwan", title: "Inyección SQL confirmada", file: "ReporteRepository.java", line: 58, detail: "Kiuwan la reporta y el agente de Código confirma que el parámetro `comercio` se concatena.", suggestion: "Usar parámetros enlazados (:comercio)." },
      { id: "K2", severity: "baja", source: "kiuwan", title: "31 defectos menores de mantenibilidad", detail: "Agrupados: métodos largos, concatenación en bucle, Javadoc ausente." },
    ],
  },
  sql: {
    engine: "Oracle 19c",
    scripts: [
      { file: "db/migrations/V2026_09_10__tabla_discrepancias.sql", statements: 4, kind: "migración DDL" },
      { file: "ReporteRepository.java (consultas nativas)", statements: 2, kind: "consultas embebidas" },
    ],
    findings: [
      { id: "S1", severity: "alta", source: "sql", title: "Consulta sin índice en FECHA_OPERACION", file: "ReporteRepository.java", line: 61, detail: "El filtro por fecha hará full scan sobre PAG_DISCREPANCIA (volumen estimado 2M filas/año).", suggestion: "CREATE INDEX IX_DISC_FECHA ON PAG_DISCREPANCIA(FECHA_OPERACION)." },
      { id: "S2", severity: "media", source: "sql", title: "Migración sin script de rollback", file: "V2026_09_10__tabla_discrepancias.sql", detail: "No existe el script U2026_09_10 para revertir la tabla." },
      { id: "S3", severity: "critica", source: "sql", title: "Concatenación en consulta nativa", file: "ReporteRepository.java", line: 58, detail: "Mismo problema que K1 (se deduplica en el dictamen)." },
    ],
  },
  uiux: {
    baseUrl: "http://localhost:8080",
    scenarios: [],
    findings: [],
  },
  vtr: {
    templateName: "VTR_modelo.docx",
    outputName: "VTR_REQ-1042.docx",
    sections: [
      { title: "1. Identificación del requerimiento", status: "completa", sources: ["orchestrator"], content: "REQ-1042 · Conciliación automática de pagos con tarjeta. Rama feature/REQ-1042-conciliacion." },
      { title: "2. Descripción funcional del cambio", status: "completa", sources: ["code"], content: "Job diario que concilia pagos con el fichero del adquirente, persiste discrepancias en PAG_DISCREPANCIA y las expone vía GET /api/discrepancias." },
      { title: "3. Componentes afectados", status: "completa", sources: ["code"], content: "4 clases Java (3 nuevas, 1 modificada), 1 fichero de configuración y 1 migración de base de datos." },
      { title: "4. Cambios en base de datos", status: "completa", sources: ["sql", "code"], content: "Nueva tabla PAG_DISCREPANCIA. Pendiente: índice sobre FECHA_OPERACION y script de rollback." },
      { title: "5. Pruebas realizadas", status: "completa", sources: ["tests"], content: "5 pruebas generadas (3 unitarias, 2 de integración): 3 pasan, 2 fallan. Cobertura del cambio: 71 %." },
      { title: "6. Análisis estático (Kiuwan)", status: "completa", sources: ["kiuwan"], content: "37 defectos: 1 crítico confirmado (inyección SQL), 1 falso positivo, 35 menores." },
      { title: "7. Pruebas de interfaz", status: "vacia", sources: [], content: "No aplica: el requerimiento no modifica pantallas." },
      { title: "8. Riesgos y observaciones", status: "parcial", sources: ["code", "sql"], content: "Riesgo de discrepancias falsas por redondeo y de duplicados si se relanza el job. Falta validar con el área de operaciones." },
      { title: "9. Aprobaciones", status: "vacia", sources: [], content: "Se completa manualmente tras la revisión." },
    ],
  },
};

const PORTAL: ScenarioDeliverables = {
  code: {
    stack: "Next.js 14 · React 18 · API .NET 8",
    summary:
      "Se sustituye el formulario de alta de clientes por uno de tres pasos con validación en cliente y servidor, guardado de borrador y carga de documento de identidad.",
    changeMap: [
      { file: "web/app/clientes/alta/page.tsx", change: "modificado", added: 162, removed: 88, symbols: ["AltaClientePage"], criteria: [0] },
      { file: "web/components/alta/StepDatosPersonales.tsx", change: "nuevo", added: 124, removed: 0, symbols: ["StepDatosPersonales"], criteria: [0, 1] },
      { file: "web/components/alta/StepDocumento.tsx", change: "nuevo", added: 98, removed: 0, symbols: ["StepDocumento"], criteria: [2] },
      { file: "web/lib/validators/cliente.ts", change: "nuevo", added: 57, removed: 0, symbols: ["validarDni", "validarEmail"], criteria: [1] },
      { file: "api/Controllers/ClientesController.cs", change: "modificado", added: 41, removed: 12, symbols: ["ClientesController.CrearBorrador"], criteria: [3] },
    ],
    findings: [
      { id: "C1", severity: "media", source: "code", title: "Validación de DNI solo en cliente", file: "ClientesController.cs", line: 54, detail: "El endpoint acepta DNI con letra de control incorrecta si se llama directamente.", suggestion: "Replicar validarDni en el servidor." },
      { id: "C2", severity: "baja", source: "code", title: "Borrador guardado en localStorage con datos personales", file: "page.tsx", line: 73, detail: "El borrador incluye DNI y teléfono en claro en el navegador." },
      { id: "C3", severity: "info", source: "code", title: "Componentes sin pruebas previas", detail: "Los tres pasos nuevos no tenían pruebas en el repositorio." },
    ],
  },
  tests: {
    framework: "Vitest · Testing Library",
    command: "npx vitest run --dir web/__generated__",
    coverage: 83,
    tests: [
      { name: "validarDni acepta DNI con letra correcta", file: "cliente.generated.test.ts", kind: "unitario", criterion: 1, status: "paso", durationMs: 6, code: `it("validarDni acepta DNI con letra correcta", () => {\n  expect(validarDni("12345678Z")).toBe(true);\n});` },
      { name: "validarDni rechaza letra incorrecta", file: "cliente.generated.test.ts", kind: "unitario", criterion: 1, status: "paso", durationMs: 4, code: `it("validarDni rechaza letra incorrecta", () => {\n  expect(validarDni("12345678A")).toBe(false);\n});` },
      { name: "no avanza de paso con email inválido", file: "StepDatosPersonales.generated.test.tsx", kind: "unitario", criterion: 0, status: "paso", durationMs: 88, code: `it("no avanza de paso con email inválido", async () => {\n  render(<StepDatosPersonales onNext={next} />);\n  await user.type(screen.getByLabelText(/email/i), "no-es-email");\n  await user.click(screen.getByRole("button", { name: /siguiente/i }));\n  expect(next).not.toHaveBeenCalled();\n});` },
      { name: "rechaza documento mayor de 5 MB", file: "StepDocumento.generated.test.tsx", kind: "unitario", criterion: 2, status: "paso", durationMs: 71, code: `it("rechaza documento mayor de 5 MB", async () => {\n  render(<StepDocumento />);\n  await user.upload(screen.getByLabelText(/documento/i), bigFile(6));\n  expect(screen.getByRole("alert")).toHaveTextContent(/5 MB/);\n});` },
    ],
    findings: [],
  },
  kiuwan: {
    fileName: "kiuwan_REQ-1057.csv",
    rows: 12,
    defects: [
      { ruleId: "OPT.JAVASCRIPT.SEC.LocalStorageSensitiveData", rule: "Datos sensibles en almacenamiento local", severity: "media", category: "Seguridad", file: "page.tsx", line: 73, falsePositive: false, note: "Coincide con C2 de Código." },
      { ruleId: "OPT.CSHARP.RGP.AvoidEmptyCatch", rule: "Bloque catch vacío", severity: "media", category: "Fiabilidad", file: "ClientesController.cs", line: 88, falsePositive: false, note: "" },
      { ruleId: "OPT.JAVASCRIPT.MANT.ComplexFunction", rule: "Complejidad ciclomática alta", severity: "baja", category: "Mantenibilidad", file: "StepDatosPersonales.tsx", line: 40, falsePositive: false, note: "" },
      { ruleId: "OPT.JAVASCRIPT.SEC.XSS", rule: "Posible XSS", severity: "alta", category: "Seguridad", file: "StepDocumento.tsx", line: 61, falsePositive: true, note: "Falso positivo: React escapa el nombre del archivo; no se usa dangerouslySetInnerHTML." },
    ],
    findings: [
      { id: "K1", severity: "media", source: "kiuwan", title: "Datos personales en localStorage", file: "page.tsx", line: 73, detail: "Kiuwan lo marca como seguridad media; se deduplica con C2." },
      { id: "K2", severity: "media", source: "kiuwan", title: "Catch vacío en ClientesController", file: "ClientesController.cs", line: 88, detail: "Los errores al guardar borrador se pierden sin log." },
    ],
  },
  sql: { engine: "SQL Server 2022", scripts: [], findings: [] },
  uiux: {
    baseUrl: "http://localhost:3000",
    scenarios: [
      { name: "Alta completa en 3 pasos", browser: "chromium", status: "paso", durationMs: 8420, a11yIssues: 0, steps: ["Abrir /clientes/alta", "Rellenar datos personales", "Subir documento de 1,2 MB", "Confirmar y ver pantalla de éxito"] },
      { name: "Recuperar borrador tras recargar", browser: "chromium", status: "paso", durationMs: 5110, a11yIssues: 0, steps: ["Rellenar paso 1", "Recargar página", "Comprobar que los datos siguen"] },
      { name: "Navegación solo con teclado", browser: "firefox", status: "fallo", durationMs: 6930, a11yIssues: 2, failureReason: "El botón 'Subir documento' no recibe foco con Tab (div con onClick sin role ni tabIndex).", steps: ["Tab hasta el paso 2", "Intentar abrir selector de archivo con Enter"] },
      { name: "Vista móvil 390px", browser: "webkit", status: "paso", durationMs: 4380, a11yIssues: 1, steps: ["Viewport 390×844", "Recorrer los 3 pasos", "Captura de cada paso"] },
    ],
    findings: [
      { id: "U1", severity: "alta", source: "uiux", title: "Subida de documento inaccesible por teclado", file: "StepDocumento.tsx", line: 44, detail: "Incumple WCAG 2.1.1 (Teclado). Bloquea a usuarios sin ratón.", suggestion: "Usar <button> o <label htmlFor> asociado al input file." },
      { id: "U2", severity: "baja", source: "uiux", title: "Contraste insuficiente en texto de ayuda", file: "StepDatosPersonales.tsx", line: 97, detail: "Ratio 3,1:1 sobre fondo blanco (mínimo 4,5:1)." },
    ],
  },
  vtr: {
    templateName: "VTR_modelo.docx",
    outputName: "VTR_REQ-1057.docx",
    sections: [
      { title: "1. Identificación del requerimiento", status: "completa", sources: ["orchestrator"], content: "REQ-1057 · Nuevo formulario de alta de clientes en portal web." },
      { title: "2. Descripción funcional del cambio", status: "completa", sources: ["code"], content: "Formulario de alta en tres pasos con validación, guardado de borrador y carga de documento." },
      { title: "3. Componentes afectados", status: "completa", sources: ["code"], content: "3 componentes React (2 nuevos), 1 módulo de validación y 1 controlador .NET." },
      { title: "4. Cambios en base de datos", status: "vacia", sources: [], content: "No aplica." },
      { title: "5. Pruebas realizadas", status: "completa", sources: ["tests"], content: "4 pruebas unitarias generadas, todas pasan. Cobertura del cambio: 83 %." },
      { title: "6. Análisis estático (Kiuwan)", status: "completa", sources: ["kiuwan"], content: "12 defectos: 0 críticos, 1 falso positivo (XSS), 2 medios relevantes." },
      { title: "7. Pruebas de interfaz", status: "completa", sources: ["uiux"], content: "4 escenarios Playwright en chromium, firefox y webkit: 3 pasan, 1 falla (navegación por teclado)." },
      { title: "8. Riesgos y observaciones", status: "parcial", sources: ["code", "uiux"], content: "Accesibilidad por teclado en la subida de documento y validación de DNI solo en cliente." },
      { title: "9. Aprobaciones", status: "vacia", sources: [], content: "Se completa manualmente tras la revisión." },
    ],
  },
};

const SCENARIOS: Record<ScenarioId, ScenarioDeliverables> = { pagos: PAGOS, portal: PORTAL };

const SEV_RANK: Record<Severity, number> = { critica: 0, alta: 1, media: 2, baja: 3, info: 4 };

export function sortFindings(list: Finding[]): Finding[] {
  return [...list].sort((a, b) => SEV_RANK[a.severity] - SEV_RANK[b.severity]);
}

/** Hallazgos de los agentes que llegaron a completarse, deduplicados por archivo+línea. */
// Con un repositorio real solo cuentan los agentes que trabajan sobre datos reales (Código y SQL).
const REAL_SOURCES: AgentId[] = ["code", "sql"];

export function consolidatedFindings(d: BaseDeliverables, completedAll: AgentId[]): Finding[] {
  const completed = d.realRepo ? completedAll.filter((a) => REAL_SOURCES.includes(a)) : completedAll;
  const all: Finding[] = [];
  if (completed.includes("code")) all.push(...d.code.findings);
  if (completed.includes("tests")) all.push(...d.tests.findings);
  if (completed.includes("kiuwan")) all.push(...d.kiuwan.findings);
  if (completed.includes("sql")) all.push(...d.sql.findings);
  if (completed.includes("uiux")) all.push(...d.uiux.findings);
  const seen = new Map<string, Finding>();
  for (const f of sortFindings(all)) {
    const key = f.file && f.line ? `${f.file}:${f.line}` : f.id + f.source;
    if (!seen.has(key)) seen.set(key, f);
  }
  return sortFindings([...seen.values()]);
}

function buildVerdict(d: BaseDeliverables, completed: AgentId[]): VerdictReport {
  const findings = consolidatedFindings(d, completed);
  const crit = findings.filter((f) => f.severity === "critica").length;
  const high = findings.filter((f) => f.severity === "alta").length;
  const failed = completed.includes("tests") && !d.realRepo ? d.tests.tests.filter((t) => t.status === "fallo").length : 0;
  const guardrails: string[] = [];
  if (d.realRepo) guardrails.push("G0 · Repositorio real: el dictamen solo considera Código y SQL; Tests, Kiuwan y UI/UX aún son de ejemplo.");
  let verdict: Verdict = "APROBADO";
  if (crit > 0) {
    verdict = "RECHAZADO";
    guardrails.push(`G1 · ${crit} hallazgo(s) crítico(s): el dictamen no puede ser APROBADO.`);
  } else if (high > 0 || failed > 0) {
    verdict = "APROBADO_CON_OBSERVACIONES";
    if (failed > 0) guardrails.push(`G2 · ${failed} prueba(s) generada(s) fallan: como máximo APROBADO CON OBSERVACIONES.`);
  }
  const missing = ((d.realRepo ? ["code"] : ["code", "tests", "kiuwan"]) as AgentId[]).filter((a) => !completed.includes(a));
  if (missing.length) guardrails.push(`G3 · Agentes desactivados (${missing.join(", ")}): la confianza se limita a 0,6.`);
  const confidence = missing.length ? 0.6 : verdict === "APROBADO" ? 0.9 : 0.82;
  const rationale =
    verdict === "RECHAZADO"
      ? `Se rechaza por ${crit} hallazgo(s) crítico(s). Además hay ${high} de severidad alta${failed ? ` y ${failed} prueba(s) fallida(s)` : ""} que deben corregirse.`
      : verdict === "APROBADO_CON_OBSERVACIONES"
        ? `No hay hallazgos críticos, pero quedan ${high} de severidad alta${failed ? ` y ${failed} prueba(s) fallida(s)` : ""}. Puede avanzar si se corrigen antes del pase.`
        : d.realRepo
          ? "Las reglas deterministas no detectaron hallazgos críticos ni altos en el diff."
          : "No se detectaron hallazgos críticos ni altos y todas las pruebas generadas pasan.";
  return { verdict, confidence, rationale, guardrails };
}

/** Sustituye Código, SQL y las secciones del VTR que dependen del código por datos del diff real. */
function withRealRepo(base: ScenarioDeliverables, req: Requirement): BaseDeliverables {
  const repo = req.attachments.find((a) => a.kind === "repo")?.repo ?? null;
  if (!repo) return { ...base, realRepo: null };
  const added = repo.files.reduce((s, f) => s + f.additions, 0);
  const removed = repo.files.reduce((s, f) => s + f.deletions, 0);
  const changeMap: ChangeMapEntry[] = repo.files.map((f) => ({
    file: f.path,
    change: f.status === "added" ? "nuevo" : f.status === "removed" ? "eliminado" : "modificado",
    added: f.additions,
    removed: f.deletions,
    symbols: [],
    criteria: [],
  }));
  const sqlFiles = repo.files.filter((f) => /\.sql$/i.test(f.path) && f.status !== "removed");
  const codeFindings = repo.findings.filter((f) => f.source === "code");
  const sqlFindings = repo.findings.filter((f) => f.source === "sql");
  const stack = languageSummary(repo.languages);
  const summary = `${repo.fullName} · ${repo.rangeLabel}: ${repo.aheadBy} commit(s), ${repo.files.length} archivo(s) cambiados (+${added} −${removed}). Hallazgos obtenidos con reglas deterministas sobre las líneas añadidas; la revisión semántica llegará con el LLM en el backend.`;
  const vtrSections = base.vtr.sections.map((s) => {
    if (s.title.startsWith("2.")) return { ...s, content: `Cambios de ${repo.rangeLabel} en ${repo.fullName}. Commits: ${repo.commits.slice(0, 3).map((c) => `«${c.message}»`).join(", ")}${repo.commits.length > 3 ? "…" : ""}.` };
    if (s.title.startsWith("3.")) return { ...s, content: `${repo.files.length} archivos (${repo.files.filter((f) => f.status === "added").length} nuevos, ${repo.files.filter((f) => f.status === "removed").length} eliminados). Lenguajes del repositorio: ${stack}.` };
    if (s.title.startsWith("4.")) return sqlFiles.length ? { ...s, status: "completa" as const, sources: ["sql", "code"] as AgentId[], content: `Scripts SQL en el cambio: ${sqlFiles.map((f) => f.path).join(", ")}.` } : { ...s, status: "vacia" as const, sources: [], content: "No hay scripts SQL en el cambio." };
    return s;
  });
  return {
    ...base,
    realRepo: repo,
    code: { stack, summary, changeMap, findings: codeFindings },
    sql: { engine: "detectado por extensión", scripts: sqlFiles.map((f) => ({ file: f.path, statements: 0, kind: "script" })), findings: sqlFindings },
    vtr: { ...base.vtr, outputName: `VTR_${req.id}.docx`, sections: vtrSections },
  };
}

export function deliverablesFor(req: Requirement, completed: AgentId[]): Deliverables {
  const base = withRealRepo(SCENARIOS[req.scenario], req);
  return { ...base, verdict: buildVerdict(base, completed) };
}

export const SEVERITY_LABELS: Record<Severity, string> = {
  critica: "Crítica",
  alta: "Alta",
  media: "Media",
  baja: "Baja",
  info: "Info",
};

export const VERDICT_LABELS: Record<Verdict, string> = {
  APROBADO: "Aprobado",
  APROBADO_CON_OBSERVACIONES: "Aprobado con observaciones",
  RECHAZADO: "Rechazado",
};
