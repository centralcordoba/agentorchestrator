"""Bus de eventos en memoria."""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from ..domain.run import TraceEvent

log = logging.getLogger(__name__)

#: Tope de eventos en cola por suscriptor. Si un cliente no lee, se le cierra antes de que el
#: servidor acumule memoria por su culpa.
QUEUE_LIMIT = 1000


class Subscription:
    """Cola de eventos de una ejecución para un espectador."""

    def __init__(self, run_id: str) -> None:
        self.run_id = run_id
        self._queue: asyncio.Queue[TraceEvent] = asyncio.Queue(maxsize=QUEUE_LIMIT)
        self.dropped = 0

    def offer(self, event: TraceEvent) -> None:
        try:
            self._queue.put_nowait(event)
        except asyncio.QueueFull:
            # Quien no lee pierde eventos; al reconectar los recupera del replay.
            self.dropped += 1
            log.warning("suscriptor lento en %s: %s evento(s) descartados", self.run_id, self.dropped)

    async def get(self) -> TraceEvent:
        return await self._queue.get()

    def drain(self) -> list[TraceEvent]:
        """Vacía lo acumulado sin esperar."""
        events: list[TraceEvent] = []
        while True:
            try:
                events.append(self._queue.get_nowait())
            except asyncio.QueueEmpty:
                return events


class InMemoryEventBus:
    def __init__(self) -> None:
        self._subscribers: dict[str, set[Subscription]] = {}

    async def publish(self, event: TraceEvent) -> None:
        for subscription in list(self._subscribers.get(event.run_id, ())):
            subscription.offer(event)
        log.debug("evento %s #%s %s", event.run_id, event.seq, event.type.value)

    @asynccontextmanager
    async def subscription(self, run_id: str) -> AsyncIterator[Subscription]:
        """Abre una suscripción y la cierra al salir, pase lo que pase."""
        subscription = Subscription(run_id)
        self._subscribers.setdefault(run_id, set()).add(subscription)
        try:
            yield subscription
        finally:
            listeners = self._subscribers.get(run_id)
            if listeners is not None:
                listeners.discard(subscription)
                if not listeners:
                    del self._subscribers[run_id]

    def subscribers(self, run_id: str) -> int:
        return len(self._subscribers.get(run_id, ()))


class NullEventBus:
    """Descarta los eventos. Útil en pruebas que solo miran el resultado."""

    async def publish(self, event: TraceEvent) -> None:  # noqa: D401 - contrato del puerto
        return None
