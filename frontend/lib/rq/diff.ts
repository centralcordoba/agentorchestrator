// Utilidades sobre diffs unificados (formato "patch" de GitHub).

/** Líneas añadidas de un patch con su número de línea en la versión nueva del archivo. */
export function addedLines(patch: string): { line: number; text: string }[] {
  const out: { line: number; text: string }[] = [];
  let n = 0;
  for (const raw of patch.split("\n")) {
    const h = raw.match(/^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@/);
    if (h) {
      n = Number(h[1]);
      continue;
    }
    if (raw.startsWith("+")) out.push({ line: n++, text: raw.slice(1) });
    else if (raw.startsWith(" ")) n++;
  }
  return out;
}
