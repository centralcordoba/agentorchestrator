// Conexión con repositorios públicos de GitHub desde el navegador (API REST sin autenticación).
// Límite de GitHub: 60 peticiones por hora por IP. Conectar un repositorio consume 3-5.
import { addedLines } from "./diff";
import { analyzePrivacy } from "./privacy";
import type { Finding, RepoFile, RepoInfo, Severity } from "./types";

const API = "https://api.github.com";

export class GitHubError extends Error {}

export function parseRepoUrl(input: string): { owner: string; name: string } | null {
  const s = input.trim().replace(/\/+$/, "").replace(/\.git$/, "");
  const m =
    s.match(/^(?:https?:\/\/)?(?:www\.)?github\.com[/:]([\w.-]+)\/([\w.-]+)(?:\/.*)?$/i) ??
    s.match(/^git@github\.com:([\w.-]+)\/([\w.-]+)$/i) ??
    s.match(/^([\w.-]+)\/([\w.-]+)$/);
  return m ? { owner: m[1], name: m[2] } : null;
}

async function gh<T>(path: string): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API}${path}`, { headers: { Accept: "application/vnd.github+json" } });
  } catch {
    throw new GitHubError("No se pudo contactar con api.github.com (¿sin conexión o bloqueado por la red?).");
  }
  if (res.ok) return (await res.json()) as T;
  if (res.status === 404) throw new GitHubError("No se encontró el repositorio, la rama o el commit. Solo se admiten repositorios públicos.");
  if ((res.status === 403 || res.status === 429) && res.headers.get("x-ratelimit-remaining") === "0") {
    const reset = Number(res.headers.get("x-ratelimit-reset")) * 1000;
    const at = reset ? new Date(reset).toLocaleTimeString("es-ES", { hour: "2-digit", minute: "2-digit" }) : "más tarde";
    throw new GitHubError(`Se alcanzó el límite de la API pública de GitHub (60 peticiones/hora). Vuelve a intentarlo a las ${at}.`);
  }
  throw new GitHubError(`GitHub respondió ${res.status}.`);
}

export interface RepoMeta {
  owner: string;
  name: string;
  fullName: string;
  htmlUrl: string;
  description: string;
  defaultBranch: string;
  stars: number;
  branches: string[];
  languages: Record<string, number>;
}

export async function fetchRepoMeta(owner: string, name: string): Promise<RepoMeta> {
  const [repo, branches, languages] = await Promise.all([
    gh<{ full_name: string; html_url: string; description: string | null; default_branch: string; stargazers_count: number; private: boolean }>(`/repos/${owner}/${name}`),
    gh<{ name: string }[]>(`/repos/${owner}/${name}/branches?per_page=100`),
    gh<Record<string, number>>(`/repos/${owner}/${name}/languages`),
  ]);
  const names = branches.map((b) => b.name);
  if (!names.includes(repo.default_branch)) names.unshift(repo.default_branch);
  return {
    owner,
    name,
    fullName: repo.full_name,
    htmlUrl: repo.html_url,
    description: repo.description ?? "",
    defaultBranch: repo.default_branch,
    stars: repo.stargazers_count,
    branches: names,
    languages,
  };
}

export type CompareMode = { kind: "base"; base: string } | { kind: "commits"; count: number };

interface CompareResponse {
  html_url: string;
  ahead_by: number;
  total_commits: number;
  commits: { sha: string; html_url: string; commit: { message: string; author: { name: string; date: string } | null } }[];
  files?: { filename: string; status: string; additions: number; deletions: number; patch?: string; blob_url: string }[];
}

export async function connectRepo(meta: RepoMeta, branch: string, mode: CompareMode): Promise<RepoInfo> {
  const { owner, name } = meta;
  let base: string;
  let rangeLabel: string;
  if (mode.kind === "base") {
    if (mode.base === branch) throw new GitHubError("La rama base y la rama del desarrollo son la misma. Elige otra base o compara los últimos commits.");
    base = mode.base;
    rangeLabel = `${mode.base}…${branch}`;
  } else {
    const commits = await gh<{ sha: string }[]>(`/repos/${owner}/${name}/commits?sha=${encodeURIComponent(branch)}&per_page=${mode.count + 1}`);
    if (commits.length < 2) throw new GitHubError("La rama no tiene commits suficientes para comparar.");
    base = commits[commits.length - 1].sha;
    rangeLabel = `últimos ${commits.length - 1} commits de ${branch}`;
  }
  const cmp = await gh<CompareResponse>(`/repos/${owner}/${name}/compare/${encodeURIComponent(base)}...${encodeURIComponent(branch)}`);
  const rawFiles = cmp.files ?? [];
  if (!rawFiles.length) throw new GitHubError("No hay diferencias entre la base y la rama elegida.");
  const headSha = cmp.commits[cmp.commits.length - 1]?.sha ?? branch;

  const files: RepoFile[] = rawFiles.map((f) => ({
    path: f.filename,
    status: f.status === "added" ? "added" : f.status === "removed" ? "removed" : f.status === "renamed" ? "renamed" : "modified",
    additions: f.additions,
    deletions: f.deletions,
    hasPatch: Boolean(f.patch),
  }));

  return {
    provider: "github",
    owner,
    name,
    fullName: meta.fullName,
    htmlUrl: meta.htmlUrl,
    description: meta.description,
    defaultBranch: meta.defaultBranch,
    branch,
    base,
    rangeLabel,
    compareUrl: cmp.html_url,
    headSha,
    aheadBy: cmp.ahead_by,
    commits: cmp.commits
      .slice(-10)
      .reverse()
      .map((c) => ({ sha: c.sha, message: c.commit.message.split("\n")[0], author: c.commit.author?.name ?? "—", date: c.commit.author?.date ?? "", url: c.html_url })),
    files,
    filesTruncated: rawFiles.length >= 300,
    languages: meta.languages,
    ...withPrivacy(rawFiles, meta.htmlUrl, headSha),
    fetchedAt: new Date().toISOString(),
  };
}

/** Hallazgos de Código/SQL más los del agente de Privacidad HIPAA (identificadores, salvaguardas y señales de PHI). */
function withPrivacy(files: NonNullable<CompareResponse["files"]>, htmlUrl: string, headSha: string) {
  const blob = (path: string, line?: number) => `${htmlUrl}/blob/${headSha}/${path}${line ? `#L${line}` : ""}`;
  const privacy = analyzePrivacy(files, blob);
  return {
    findings: [...analyzeDiff(files, htmlUrl, headSha), ...privacy.findings],
    phiDetections: privacy.detections,
    phiSignals: privacy.signals,
  };
}

// ------------------------------------------------------------------ análisis por reglas (sin LLM)
// Reglas deterministas sobre las líneas AÑADIDAS del diff. Cada hallazgo apunta a una línea real.

interface Rule {
  id: string;
  severity: Severity;
  title: string;
  detail: string;
  source: "code" | "sql";
  test: RegExp;
  only?: RegExp; // solo en archivos cuyo nombre cumple
  suggestion?: string;
}

const RULES: Rule[] = [
  { id: "SEC-SECRET", severity: "critica", source: "code", title: "Posible credencial escrita en el código", detail: "Se añade un valor literal asignado a una variable con nombre de secreto.", test: /\b(password|passwd|pwd|secret|api[_-]?key|access[_-]?token|client[_-]?secret)\b\s*[:=]\s*["'][^"'\s]{8,}["']/i, suggestion: "Mover el valor a variables de entorno o a un gestor de secretos." },
  { id: "SEC-SQLCONCAT", severity: "alta", source: "code", title: "Consulta SQL construida concatenando texto", detail: "La sentencia se arma uniendo cadenas con variables: riesgo de inyección SQL.", test: /\b(SELECT|INSERT|UPDATE|DELETE)\b[^;\n]*["'`]\s*\+\s*[\w.(]/i, suggestion: "Usar consultas parametrizadas." },
  { id: "SEC-EVAL", severity: "alta", source: "code", title: "Uso de eval", detail: "eval ejecuta código arbitrario construido en tiempo de ejecución.", test: /(^|[^.\w])eval\s*\(/, only: /\.(js|jsx|ts|tsx|py|php|rb)$/i },
  { id: "REL-EMPTYCATCH", severity: "media", source: "code", title: "Bloque catch vacío", detail: "El error se captura y se descarta sin registrarlo.", test: /catch\s*(\([^)]*\))?\s*\{\s*\}/, suggestion: "Registrar el error o propagarlo." },
  { id: "SQL-DELETE-NOWHERE", severity: "alta", source: "sql", title: "DELETE sin WHERE", detail: "Borra todas las filas de la tabla.", test: /\bDELETE\s+FROM\s+[\w."]+\s*;/i },
  { id: "SQL-DROP", severity: "media", source: "sql", title: "Sentencia DROP", detail: "Operación destructiva: comprobar que existe script de rollback.", test: /\bDROP\s+(TABLE|COLUMN|INDEX|VIEW)\b/i },
  { id: "SQL-SELECTSTAR", severity: "baja", source: "sql", title: "SELECT *", detail: "Traer todas las columnas complica el mantenimiento y puede degradar el rendimiento.", test: /\bSELECT\s+\*\s+FROM\b/i },
  { id: "DBG-LOG", severity: "baja", source: "code", title: "Traza de depuración añadida", detail: "Se añaden salidas por consola que suelen quedar olvidadas.", test: /\b(console\.log|System\.out\.println|var_dump|debugger;)/, only: /\.(js|jsx|ts|tsx|java|php|vue|svelte)$/i },
  { id: "MNT-TODO", severity: "info", source: "code", title: "TODO/FIXME añadido", detail: "Queda trabajo pendiente marcado en el código.", test: /\b(TODO|FIXME|HACK|XXX)\b/ },
];

const TEST_FILE = /(^|\/)(test|tests|__tests__|spec)\/|[._-](test|spec)\.[a-z]+$|Tests?\.(java|cs|kt)$/i;
const MANIFEST = /(^|\/)(package\.json|pom\.xml|build\.gradle(\.kts)?|requirements\.txt|pyproject\.toml|go\.mod|Cargo\.toml|composer\.json|Gemfile|[\w.-]+\.csproj)$/;
const SOURCE = /\.(js|jsx|ts|tsx|java|kt|cs|py|go|rb|php|vue|svelte|scala|swift)$/i;

export function analyzeDiff(files: NonNullable<CompareResponse["files"]>, htmlUrl: string, headSha: string): Finding[] {
  const findings: Finding[] = [];
  const blob = (path: string, line?: number) => `${htmlUrl}/blob/${headSha}/${path}${line ? `#L${line}` : ""}`;
  let seq = 0;

  for (const f of files) {
    if (f.status === "removed") continue;
    const isSql = /\.sql$/i.test(f.filename);
    if (f.patch) {
      const lines = addedLines(f.patch);
      for (const rule of RULES) {
        if (rule.only && !rule.only.test(f.filename)) continue;
        if (rule.source === "sql" && !isSql && !/\b(SELECT|DELETE|DROP)\b/.test(f.patch)) continue;
        const hits = lines.filter((l) => rule.test.test(l.text));
        if (!hits.length) continue;
        findings.push({
          id: `R${++seq}`,
          severity: rule.severity,
          source: rule.source,
          title: rule.title,
          detail: `${rule.detail}${hits.length > 1 ? ` (${hits.length} líneas en este archivo)` : ""} Línea: «${hits[0].text.trim().slice(0, 120)}»`,
          file: f.filename,
          line: hits[0].line,
          url: blob(f.filename, hits[0].line),
          suggestion: rule.suggestion,
        });
      }
    }
    if (f.additions + f.deletions > 400) {
      findings.push({ id: `R${++seq}`, severity: "media", source: "code", title: "Cambio muy grande en un archivo", detail: `+${f.additions} −${f.deletions} líneas: difícil de revisar con garantías.`, file: f.filename, url: blob(f.filename), suggestion: "Dividir el cambio en commits o PR más pequeños." });
    } else if (!f.patch && SOURCE.test(f.filename)) {
      findings.push({ id: `R${++seq}`, severity: "info", source: "code", title: "Diff no disponible", detail: "GitHub no devuelve el diff de este archivo (demasiado grande o binario); no se analizó.", file: f.filename, url: blob(f.filename) });
    }
  }

  const source = files.filter((f) => f.status !== "removed" && SOURCE.test(f.filename) && !TEST_FILE.test(f.filename));
  const tests = files.filter((f) => TEST_FILE.test(f.filename));
  if (source.length && !tests.length) {
    findings.push({ id: `R${++seq}`, severity: "media", source: "code", title: "Cambio de código sin pruebas", detail: `Se modifican ${source.length} archivo(s) de código y ningún archivo de pruebas.`, suggestion: "Añadir o actualizar pruebas que cubran el cambio." });
  }
  const manifests = files.filter((f) => MANIFEST.test(f.filename));
  if (manifests.length) {
    findings.push({ id: `R${++seq}`, severity: "info", source: "code", title: "Dependencias modificadas", detail: `Cambian ${manifests.map((m) => m.filename).join(", ")}: revisar licencias y vulnerabilidades de las nuevas versiones.`, file: manifests[0].filename, url: blob(manifests[0].filename) });
  }
  return findings;
}

export function languageSummary(languages: Record<string, number>, max = 3): string {
  const total = Object.values(languages).reduce((s, v) => s + v, 0);
  if (!total) return "—";
  return Object.entries(languages)
    .sort((a, b) => b[1] - a[1])
    .slice(0, max)
    .map(([k, v]) => `${k} ${Math.round((v / total) * 100)} %`)
    .join(" · ");
}

export const FRONTEND_FILE = /\.(tsx|jsx|vue|svelte|html|css|scss|less)$/i;
