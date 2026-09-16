"""Servicios de apoyo: reloj e identificadores.

Se inyectan como puertos para que las pruebas sean deterministas (reloj fijo, contador).
"""
from __future__ import annotations

import itertools
from datetime import datetime, timezone


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(timezone.utc)


class FixedClock:
    """Reloj de pruebas: avanza solo cuando se le pide."""

    def __init__(self, start: datetime) -> None:
        self._now = start

    def now(self) -> datetime:
        return self._now

    def advance(self, seconds: float) -> None:
        from datetime import timedelta

        self._now = self._now + timedelta(seconds=seconds)


class SequentialIdGenerator:
    """Identificadores legibles y estables: REQ-001, RUN-002…"""

    def __init__(self) -> None:
        self._counters: dict[str, itertools.count[int]] = {}

    async def new_id(self, prefix: str) -> str:
        counter = self._counters.setdefault(prefix, itertools.count(1))
        return f"{prefix}-{next(counter):03d}"
