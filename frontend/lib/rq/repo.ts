// Ayudas sobre un repositorio ya conectado. **Sin red**: el navegador ya no habla con ningún
// proveedor de git. Clonar, calcular el diff y aplicar las reglas ocurre en el servidor (ORQ-22);
// aquí solo queda lo que es dar formato a lo que el backend devuelve.

/** Archivos que pintan pantalla: sirven para saber si tiene sentido el agente de UI/UX. */
export const FRONTEND_FILE = /\.(tsx|jsx|vue|svelte|html|css|scss|less)$/i;

/** «TypeScript 62 % · Java 31 %» a partir del recuento por lenguaje. */
export function languageSummary(languages: Record<string, number>, max = 3): string {
  const total = Object.values(languages).reduce((s, v) => s + v, 0);
  if (!total) return "—";
  return Object.entries(languages)
    .sort((a, b) => b[1] - a[1])
    .slice(0, max)
    .map(([k, v]) => `${k} ${Math.round((v / total) * 100)} %`)
    .join(" · ");
}
