"""Indicadores técnicos en Python puro (deterministas y auditables).

Todos los valores que ven los agentes y el LLM salen de estas funciones; el LLM
nunca calcula ni inventa números.
"""
from __future__ import annotations

import math
from typing import Optional, Sequence


def sma(values: Sequence[float], period: int) -> Optional[float]:
    if len(values) < period or period <= 0:
        return None
    window = values[-period:]
    return sum(window) / period


def ema_series(values: Sequence[float], period: int) -> list[float]:
    if len(values) < period or period <= 0:
        return []
    k = 2 / (period + 1)
    out = [sum(values[:period]) / period]
    for v in values[period:]:
        out.append(v * k + out[-1] * (1 - k))
    return out


def rsi(values: Sequence[float], period: int = 14) -> Optional[float]:
    if len(values) < period + 1:
        return None
    gains, losses = [], []
    for prev, cur in zip(values[:-1], values[1:]):
        delta = cur - prev
        gains.append(max(delta, 0.0))
        losses.append(max(-delta, 0.0))
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for g, l in zip(gains[period:], losses[period:]):
        avg_gain = (avg_gain * (period - 1) + g) / period
        avg_loss = (avg_loss * (period - 1) + l) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - 100 / (1 + rs)


def macd(values: Sequence[float], fast: int = 12, slow: int = 26, signal: int = 9) -> Optional[dict]:
    if len(values) < slow + signal:
        return None
    ema_fast = ema_series(values, fast)
    ema_slow = ema_series(values, slow)
    # Alinear: ema_fast tiene (slow - fast) elementos más al principio.
    offset = len(ema_fast) - len(ema_slow)
    macd_line = [f - s for f, s in zip(ema_fast[offset:], ema_slow)]
    signal_line = ema_series(macd_line, signal)
    if not signal_line:
        return None
    hist = macd_line[-1] - signal_line[-1]
    return {"macd": macd_line[-1], "signal": signal_line[-1], "histogram": hist}


def atr(highs: Sequence[float], lows: Sequence[float], closes: Sequence[float], period: int = 14) -> Optional[float]:
    n = len(closes)
    if n < period + 1:
        return None
    trs = []
    for i in range(1, n):
        tr = max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1]))
        trs.append(tr)
    return sum(trs[-period:]) / period


def daily_returns(values: Sequence[float]) -> list[float]:
    return [(cur / prev) - 1 for prev, cur in zip(values[:-1], values[1:]) if prev]


def annualized_volatility(values: Sequence[float], trading_days: int = 252) -> Optional[float]:
    rets = daily_returns(values)
    if len(rets) < 20:
        return None
    mean = sum(rets) / len(rets)
    var = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)
    return math.sqrt(var) * math.sqrt(trading_days)


def max_drawdown(values: Sequence[float]) -> Optional[float]:
    if len(values) < 2:
        return None
    peak = values[0]
    worst = 0.0
    for v in values:
        peak = max(peak, v)
        if peak > 0:
            worst = min(worst, v / peak - 1)
    return worst


def pct_change(values: Sequence[float], bars: int) -> Optional[float]:
    if len(values) <= bars or values[-bars - 1] == 0:
        return None
    return values[-1] / values[-bars - 1] - 1


def round_or_none(value: Optional[float], digits: int = 2) -> Optional[float]:
    return None if value is None else round(value, digits)
