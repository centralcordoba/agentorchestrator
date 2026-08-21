"""Proveedor de datos reales vía yfinance (Yahoo Finance, solo lectura).

Nota: yfinance es síncrono; se ejecuta en un hilo para no bloquear el event loop.
"""
from __future__ import annotations

import asyncio
import logging
import math

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
            return await asyncio.wait_for(asyncio.to_thread(self._fetch_sync, symbol, days), timeout=30)
        except asyncio.TimeoutError as e:
            raise MarketDataError(f"Timeout al descargar datos de {symbol}.") from e

    def _fetch_sync(self, symbol: str, days: int) -> MarketSeries:
        try:
            import yfinance as yf  # import perezoso: solo si se usa este proveedor
        except ImportError as e:  # pragma: no cover
            raise MarketDataError("yfinance no está instalado.") from e

        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period=f"{max(days, 5)}d", interval="1d", auto_adjust=True)
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
                    open=float(row.get("Open", close)),
                    high=float(row.get("High", close)),
                    low=float(row.get("Low", close)),
                    close=close,
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
