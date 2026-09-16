// Tipos de la API a partir del contrato del backend (`backend/openapi.json`).
//
//   npm run api:types   → regenera `lib/api/schema.d.ts`
//   npm run api:check   → falla si el archivo del repositorio está desfasado
//
// La comprobación la ejecuta `npm run typecheck`: si alguien cambia el backend y no regenera el
// contrato, la compilación del frontend estaría tipando contra una API que ya no existe.
import { readFile, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";
import openapiTS, { astToString } from "openapi-typescript";

const here = path.dirname(fileURLToPath(import.meta.url));
const contract = path.resolve(here, "..", "..", "backend", "openapi.json");
const target = path.resolve(here, "..", "lib", "api", "schema.d.ts");

const BANNER = `/**
 * Generado desde backend/openapi.json. No editar a mano.
 * Regenerar con: npm run api:types
 */

`;

async function generate() {
  const url = new URL(`file://${contract.replace(/\\/g, "/")}`);
  return BANNER + astToString(await openapiTS(url));
}

function normalize(text) {
  return text.replace(/\r\n/g, "\n").trimEnd();
}

function rel(file) {
  return path.relative(process.cwd(), file);
}

function fail(message, hint) {
  console.error(`\n  ${message}\n  ${hint}\n`);
  process.exit(1);
}

const write = process.argv.includes("--write");

let expected;
try {
  expected = await generate();
} catch (error) {
  fail(
    `No se pudo leer el contrato ${rel(contract)}: ${error.message}`,
    "Expórtalo con: cd backend && .venv\\Scripts\\python.exe scripts/export_openapi.py",
  );
}

if (write) {
  await writeFile(target, expected, "utf8");
  console.log(`Tipos escritos en ${rel(target)}`);
} else {
  let current = null;
  try {
    current = await readFile(target, "utf8");
  } catch {
    fail(`Falta ${rel(target)}.`, "Genera los tipos con: npm run api:types");
  }
  if (normalize(current) !== normalize(expected)) {
    fail(
      "Los tipos de la API no coinciden con el contrato del backend.",
      "Ejecuta: npm run api:types (y revisa el diff antes de confirmarlo)",
    );
  }
  console.log("Tipos de la API al día con el contrato.");
}
