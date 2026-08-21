"""Bus de eventos: asigna números de secuencia, persiste en el RunStore y difunde por WebSocket."""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

from .models import AgentMessage, AgentName, Event, EventType
from .services.run_store import RunStore
from .websocket_manager import WebSocketManager

log = logging.getLogger(__name__)


class EventBus:
    def __init__(self, store: RunStore, ws: WebSocketManager) -> None:
        self._store = store
        self._ws = ws
        self._locks: dict[str, asyncio.Lock] = {}

    def _lock(self, run_id: str) -> asyncio.Lock:
        if run_id not in self._locks:
            self._locks[run_id] = asyncio.Lock()
        return self._locks[run_id]

    async def emit(
        self,
        run_id: str,
        type: EventType,
        *,
        symbol: Optional[str] = None,
        agent: Optional[AgentName] = None,
        message: Optional[AgentMessage] = None,
        data: Optional[dict[str, Any]] = None,
    ) -> Event:
        async with self._lock(run_id):
            seq = self._store.next_seq(run_id)
            event = Event(
                seq=seq,
                run_id=run_id,
                type=type,
                symbol=symbol,
                agent=agent,
                message=message,
                data=data or {},
            )
            self._store.append_event(event)
        log.debug("event %s #%s %s %s", run_id, event.seq, type.value, symbol or "")
        await self._ws.broadcast(run_id, event)
        return event

    async def emit_message(self, message: AgentMessage) -> Event:
        """Todo mensaje entre agentes se hace visible como evento MESSAGE_SENT."""
        return await self.emit(
            message.run_id,
            EventType.MESSAGE_SENT,
            symbol=message.symbol,
            agent=message.sender,
            message=message,
        )
