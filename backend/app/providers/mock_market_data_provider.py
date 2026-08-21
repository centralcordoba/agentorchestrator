"""Proveedor de datos simulado y determinista.

Genera series sintéticas reproducibles (misma semilla → misma serie) para un
universo conocido de símbolos. Incluye casos especiales para enseñar la gestión
de errores:

- Símbolo desconocido  → SymbolNotFoundError  (p. ej. "XYZ123")
- "NODATA"             → InsufficientDataError (muy pocas sesiones)
- "FAIL"               → MarketDataError       (fallo simulado del proveedor)
"""
from __future__ import annotations

import asyncio
import math
import random
from datetime import date, timedelta

from ..config import settings
from .market_data_provider import (
    Bar,
    InsufficientDataError,
    MarketDataError,
    MarketDataProvider,
    MarketSeries,
    SymbolNotFoundError,
)

# (precio base, deriva anual, volatilidad anual, tendencia reciente) — regímenes distintos
# para que la demo produzca COMPRA / VENTA / ESPERAR con los mismos símbolos.
# `tendencia reciente` es una deriva anualizada extra que crece linealmente (rampa) durante las
# últimas RECENT_BARS sesiones, de modo que los indicadores de momento (MACD) la capten.
RECENT_BARS = 90
UNIVERSE: dict[str, tuple[float, float, float, float]] = {
    "AAPL": (190.0, 0.28, 0.22, 0.0),    # lectura neutral → ESPERAR
    "MSFT": (410.0, 0.22, 0.20, -1.3),   # bajista sin objeciones → VENTA
    "NVDA": (120.0, 0.60, 0.55, 1.0),    # alcista pero riesgo ALTO → el escéptico discrepa → ESPERAR
    "AMZN": (180.0, 0.02, 0.24, 1.5),    # alcista, riesgo medio, sin objeciones → COMPRA
    "META": (500.0, -0.30, 0.34, -0.3),  # bajista con RSI en sobreventa → el técnico concede → ESPERAR
    "GOOGL": (165.0, 0.15, 0.25, 2.0),   # COMPRA
    "TSLA": (240.0, -0.20, 0.62, -0.3),  # alcista con riesgo ALTO y momento negativo → discrepancia
    "NFLX": (650.0, 0.35, 0.30, 1.2),    # COMPRA
    "AMD": (150.0, -0.10, 0.48, 0.0),
    "INTC": (30.0, -0.45, 0.40, 0.0),    # VENTA
    "JPM": (200.0, 0.12, 0.18, 0.0),
    "KO": (62.0, 0.04, 0.12, 0.0),
    "XOM": (110.0, -0.05, 0.21, 0.0),
    "SPY": (520.0, 0.12, 0.14, 0.75),    # COMPRA con riesgo BAJO
    "IBE.MC": (12.0, 0.10, 0.17, -1.0),  # VENTA
    "SAN.MC": (4.5, 0.25, 0.28, 1.0),    # riesgo ALTO → discrepancia
}


class MockMarketDataProvider(MarketDataProvider):
    name = "mock"

    async def fetch(self, symbol: str, days: int) -> MarketSeries:
        await asyncio.sleep(settings.demo_delay_ms / 1000)
        if symbol == "FAIL":
            raise MarketDataError("Fallo simulado del proveedor de datos (timeout).")
        if symbol == "NODATA":
            return self._generate(symbol, 8, 100.0, 0.0, 0.2, 0.0)
        if symbol not in UNIVERSE:
            known = ", ".join(sorted(UNIVERSE))
            raise SymbolNotFoundError(f"El proveedor mock no conoce '{symbol}'. Símbolos disponibles: {known}.")
        base, drift, vol, recent = UNIVERSE[symbol]
        trading_days = int(days * 252 / 365)
        return self._generate(symbol, trading_days, base, drift, vol, recent)

    @staticmethod
    def _generate(symbol: str, n_bars: int, base: float, drift: float, vol: float, recent: float) -> MarketSeries:
        # Generamos siempre la serie larga con la misma semilla y devolvemos la cola:
        # así el historial ampliado es consistente con el inicial (mismos precios).
        total = max(n_bars, 400)
        rng = random.Random(f"seed::{symbol}")
        dt = 1 / 252
        price = base * math.exp(-drift * total * dt / 2)  # para que el precio final ronde `base`
        bars: list[Bar] = []
        day = date.today() - timedelta(days=int(total * 365 / 252) + 3)
        while len(bars) < total:
            day += timedelta(days=1)
            if day.weekday() >= 5:
                continue
            shock = rng.gauss(0, 1)
            progress = max(0.0, (len(bars) - (total - RECENT_BARS)) / RECENT_BARS)
            eff_drift = drift + recent * progress
            ret = (eff_drift - 0.5 * vol**2) * dt + vol * math.sqrt(dt) * shock
            open_ = price
            price = price * math.exp(ret)
            intraday = abs(rng.gauss(0, 1)) * vol * math.sqrt(dt) * price
            high = max(open_, price) + intraday
            low = max(0.01, min(open_, price) - intraday)
            volume = float(int(rng.uniform(5e6, 4e7)))
            bars.append(Bar(day.isoformat(), round(open_, 4), round(high, 4), round(low, 4), round(price, 4), volume))
        series = MarketSeries(symbol=symbol, bars=bars[-n_bars:], source="mock", currency="USD")
        if len(series.bars) < 20:
            raise InsufficientDataError(
                f"Solo hay {len(series.bars)} sesiones para {symbol}; se requieren al menos 20."
            )
        return series
