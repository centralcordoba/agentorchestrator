// Banner superior de aviso. Actualmente desactivado (no se importa en app/page.tsx);
// el aviso corto sigue visible en el pie de página.
export default function DisclaimerBanner() {
  return (
    <div role="note" className="flex items-start gap-3 border-b border-warn/30 bg-warn-soft px-6 py-2.5 text-[13px] text-ink-700">
      <span aria-hidden className="mt-0.5 text-warn">
        ●
      </span>
      <div>
        <strong className="font-semibold text-ink-900">
          Demo educativa. No constituye asesoramiento financiero ni recomendación de inversión.
        </strong>{" "}
        <span className="text-ink-500">
          Las clasificaciones (COMPRA / VENTA / ESPERAR / NO_ANALIZABLE) son señales experimentales generadas a partir
          de datos históricos para ilustrar cómo se comunican agentes de IA. No se ejecutan órdenes ni existe conexión
          con ningún bróker.
        </span>
      </div>
    </div>
  );
}
