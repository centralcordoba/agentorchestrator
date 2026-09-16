"""Canal en vivo de una ejecución (WebSocket) con replay."""
from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from ...domain.errors import NotFoundError
from ...domain.run import TraceEvent
from ..container import Container
from ..schemas import RunOut, TraceEventOut

log = logging.getLogger(__name__)

router = APIRouter(tags=["ejecuciones"])

KEEPALIVE_S = 20.0

#: Espera de cortesía cuando la ejecución ya figura terminada pero puede faltar su último evento.
GRACE_S = 2.0

TERMINAL = {"run_completed", "run_cancelled"}

CLOSE_NOT_FOUND = 4404
CLOSE_UNAVAILABLE = 4503


@router.websocket("/runs/{run_id}/stream")
async def stream(
    websocket: WebSocket,
    run_id: str,
    after_seq: int = Query(0, alias="afterSeq", ge=0),
) -> None:
    """Traza en vivo de una ejecución, con replay desde `afterSeq`."""
    container: Container = websocket.app.state.container
    bus = container.events
    if not hasattr(bus, "subscription"):  # pragma: no cover - solo en pruebas con doble
        await websocket.close(code=CLOSE_UNAVAILABLE, reason="Canal en vivo no disponible")
        return

    await websocket.accept()

    # La suscripción se abre antes de leer lo guardado: lo que pase mientras tanto se encola.
    async with bus.subscription(run_id) as subscription:
        try:
            view = await container.get_run()(run_id)
        except NotFoundError:
            await websocket.close(code=CLOSE_NOT_FOUND, reason=f"No existe la ejecución {run_id}")
            return

        await websocket.send_json(
            {
                "type": "hello",
                "run": RunOut.from_domain(view.run).model_dump(by_alias=True, mode="json"),
                "afterSeq": after_seq,
            }
        )

        last_sent = after_seq
        last_type = ""
        for event in await container.runs.events(run_id, after_seq=after_seq):
            await _send_event(websocket, event)
            last_sent = max(last_sent, event.seq)
            last_type = event.type.value

        for event in subscription.drain():
            if event.seq > last_sent:
                await _send_event(websocket, event)
                last_sent = max(last_sent, event.seq)
                last_type = event.type.value

        # Cerrar en cuanto la ejecución figura acabada dejaría fuera su último evento: se cierra
        # cuando ese evento ha salido de verdad, o cuando pasa la espera y ya no va a llegar.
        if _is_terminal(last_type) or await _nothing_else_is_coming(container, run_id, last_type):
            await _close_end(websocket, container, run_id)
            return

        try:
            while True:
                timeout = GRACE_S if await _is_finished(container, run_id) else KEEPALIVE_S
                try:
                    event = await asyncio.wait_for(subscription.get(), timeout=timeout)
                except asyncio.TimeoutError:
                    if await _is_finished(container, run_id):
                        await _close_end(websocket, container, run_id)
                        return
                    await websocket.send_json({"type": "ping"})
                    continue

                if event.seq <= last_sent:
                    continue  # duplicado: ya salió en el replay
                await _send_event(websocket, event)
                last_sent = event.seq

                if _is_terminal(event.type.value):
                    await _close_end(websocket, container, run_id)
                    return
        except WebSocketDisconnect:
            log.debug("espectador desconectado de %s", run_id)
        except Exception:  # pragma: no cover - la conexión se cierra igualmente
            log.exception("fallo en el canal de %s", run_id)
            await websocket.close(code=CLOSE_UNAVAILABLE)


async def _send_event(websocket: WebSocket, event: TraceEvent) -> None:
    await websocket.send_json(
        {
            "type": "event",
            "event": TraceEventOut.from_domain(event).model_dump(by_alias=True, mode="json"),
        }
    )


def _is_terminal(event_type: str) -> bool:
    return event_type in TERMINAL


async def _is_finished(container: Container, run_id: str) -> bool:
    run = await container.runs.get(run_id)
    return bool(run and run.is_finished)


async def _nothing_else_is_coming(container: Container, run_id: str, last_type: str) -> bool:
    """La ejecución terminó hace rato y su último evento ya salió en el replay.

    Si figura terminada pero el último evento no es terminal, todavía puede estar guardándose:
    en ese caso no se cierra, se espera en el bucle.
    """
    if not await _is_finished(container, run_id):
        return False
    return last_type == "" and not await container.runs.events(run_id)


async def _close_end(websocket: WebSocket, container: Container, run_id: str) -> None:
    run = await container.runs.get(run_id)
    await websocket.send_json(
        {"type": "end", "status": run.status.value if run else "desconocido"}
    )
    await websocket.close()
