// Construye la versión estática del frontend (carpeta `out/`) de forma portable
// (sin depender de `set VAR=` / `VAR=` de cada shell).
import { spawnSync } from "node:child_process";
import { createRequire } from "node:module";
import { existsSync, rmSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const nextBin = require.resolve("next/dist/bin/next");
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

for (const dir of ["out", ".next"]) {
  const p = path.join(root, dir);
  if (existsSync(p)) rmSync(p, { recursive: true, force: true });
}

const result = spawnSync(process.execPath, [nextBin, "build"], {
  cwd: root,
  stdio: "inherit",
  env: { ...process.env, NEXT_OUTPUT: "export" },
});

if (result.status !== 0) process.exit(result.status ?? 1);
console.log("\nFrontend estático generado en frontend/out/ — FastAPI lo servirá en http://localhost:8000\n");
