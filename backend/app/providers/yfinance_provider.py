"""Proveedor de datos reales vía yfinance (Yahoo Finance, solo lectura).

Nota: yfinance es síncrono; se ejecuta en un hilo para no bloquear el event loop.
"""
from __future__ import annotations

import asyncio
import logging
import math
from datetime import date, timedelta

from .market_data_provider import (
    Bar,
    InsufficientDataError,
    MarketDataError,
    MarketDataProvider,
    MarketSeries,
    SymbolNotFoundError,
)

log = logging.getLogger(__name__)


class YFinanceProvider(MarketDataProvider):
    name = "yfinance"

    async def fetch(self, symbol: str, days: int) -> MarketSeries:
        try:
            return await asyncio.wait_for(asyncio.to_thread(self._fetch_sync, symbol, days), timeout=60)
        except asyncio.TimeoutError as e:
            raise MarketDataError(f"Timeout al descargar datos de {symbol}.") from e

    def _fetch_sync(self, symbol: str, days: int) -> MarketSeries:
        try:
            import yfinance as yf  # import perezoso: solo si se usa este proveedor
        except ImportError as e:  # pragma: no cover
            raise MarketDataError("yfinance no está instalado.") from e

        # `days` son días naturales (como en el proveedor mock): se piden por rango de fechas,
        # no con `period="Nd"`, que en yfinance significa N sesiones de mercado.
        start = date.today() - timedelta(days=max(days, 7))
        end = date.today() + timedelta(days=1)
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(start=start.isoformat(), end=end.isoformat(), interval="1d", auto_adjust=True)
        except Exception as e:  # errores de red / parsing de yfinance
            raise MarketDataError(f"Fallo al consultar {symbol}: {e.__class__.__name__}") from e

        if df is None or df.empty:
            raise SymbolNotFoundError(f"Yahoo Finance no devolvió datos para '{symbol}'.")

        bars: list[Bar] = []
        for idx, row in df.iterrows():
            close = float(row.get("Close", float("nan")))
            if math.isnan(close):
                continue
            bars.append(
                Bar(
                    date=idx.strftime("%Y-%m-%d"),
                    open=round(float(row.get("Open", close)), 4),
                    high=round(float(row.get("High", close)), 4),
                    low=round(float(row.get("Low", close)), 4),
                    close=round(close, 4),
                    volume=float(row.get("Volume", 0) or 0),
                )
            )
        if len(bars) < 5:
            raise InsufficientDataError(f"Solo hay {len(bars)} sesiones válidas para {symbol}.")

        currency = None
        try:
            currency = (ticker.fast_info or {}).get("currency")
        except Exception:
            pass
        return MarketSeries(symbol=symbol, bars=bars, source="yfinance", currency=currency)
