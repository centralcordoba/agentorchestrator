export default function DisclaimerBanner() {
  return (
    <div
      role="note"
      className="flex items-start gap-3 border-b border-amber-500/40 bg-amber-500/10 px-4 py-2 text-sm text-amber-200"
    >
      <span aria-hidden className="mt-0.5 text-base">
        ⚠️
      </span>
      <div>
        <strong className="font-semibold">
          Demo educativa. No constituye asesoramiento financiero ni recomendación de inversión.
        </strong>{" "}
        <span className="text-amber-200/80">
          Las clasificaciones (COMPRA / VENTA / ESPERAR / NO_ANALIZABLE) son señales experimentales generadas a
          partir de datos históricos para ilustrar cómo se comunican agentes de IA. No se ejecutan órdenes ni
          existe conexión con ningún bróker.
        </span>
      </div>
    </div>
  );
}
