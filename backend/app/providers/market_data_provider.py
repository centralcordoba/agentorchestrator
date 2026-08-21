"""Interfaz de proveedor de datos de mercado (solo lectura, sin broker)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


class MarketDataError(RuntimeError):
    """Error genérico del proveedor (red, formato, timeout...)."""


class SymbolNotFoundError(MarketDataError):
    """El símbolo no existe o el proveedor no lo reconoce."""


class InsufficientDataError(MarketDataError):
    """Hay datos, pero no los suficientes para el análisis solicitado."""


@dataclass(frozen=True)
class Bar:
    date: str       # ISO YYYY-MM-DD
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass
class MarketSeries:
    symbol: str
    bars: list[Bar] = field(default_factory=list)
    source: str = "unknown"
    currency: Optional[str] = None

    @property
    def closes(self) -> list[float]:
        return [b.close for b in self.bars]

    @property
    def highs(self) -> list[float]:
        return [b.high for b in self.bars]

    @property
    def lows(self) -> list[float]:
        return [b.low for b in self.bars]

    def summary(self) -> dict:
        if not self.bars:
            return {"symbol": self.symbol, "bars": 0, "source": self.source}
        return {
            "symbol": self.symbol,
            "bars": len(self.bars),
            "source": self.source,
            "currency": self.currency,
            "first_date": self.bars[0].date,
            "last_date": self.bars[-1].date,
            "last_close": round(self.bars[-1].close, 4),
        }


class MarketDataProvider(ABC):
    name: str = "abstract"

    @abstractmethod
    async def fetch(self, symbol: str, days: int) -> MarketSeries:
        """Devuelve barras diarias de los últimos `days` días naturales (aprox.)."""
