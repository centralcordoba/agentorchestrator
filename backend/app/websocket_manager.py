"""Gestión de conexiones WebSocket por ejecución (run)."""
from __future__ import annotations

import asyncio
import logging
from collections import defaultdict

from fastapi import WebSocket

from .models import Event

log = logging.getLogger(__name__)


class WebSocketManager:
    def __init__(self) -> None:
        self._connections: dict[str, set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def connect(self, run_id: str, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self._connections[run_id].add(ws)

    async def disconnect(self, run_id: str, ws: WebSocket) -> None:
        async with self._lock:
            self._connections[run_id].discard(ws)

    async def send_event(self, ws: WebSocket, event: Event) -> None:
        await ws.send_text(event.model_dump_json())

    async def broadcast(self, run_id: str, event: Event) -> None:
        async with self._lock:
            targets = list(self._connections.get(run_id, ()))
        if not targets:
            return
        payload = event.model_dump_json()
        dead: list[WebSocket] = []
        for ws in targets:
            try:
                await ws.send_text(payload)
            except Exception:  # conexión cerrada por el cliente
                dead.append(ws)
        if dead:
            async with self._lock:
                for ws in dead:
                    self._connections[run_id].discard(ws)
