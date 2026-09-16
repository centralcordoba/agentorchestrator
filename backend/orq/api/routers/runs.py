"""Ejecuciones: estado, traza, entregables y cancelación."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from ..container import Container
from ...domain.identity import Permission
from ..deps import current_user, get_container, requires
from ..schemas import ERROR_RESPONSES, DeliverablesOut, RunDetailOut, RunOut, TraceEventOut

router = APIRouter(prefix="/runs", tags=["ejecuciones"], responses=ERROR_RESPONSES)


@router.get("/{run_id}", response_model=RunDetailOut)
async def detail(
    run_id: str,
    events: bool = Query(False, description="Incluir la traza completa"),
    user=Depends(current_user),
    container: Container = Depends(get_container),
) -> RunDetailOut:
    view = await container.get_run()(run_id, with_events=events)
    return RunDetailOut(
        run=RunOut.from_domain(view.run),
        deliverables=DeliverablesOut.from_domain(view.deliverables),
        events=[TraceEventOut.from_domain(e) for e in view.events] if events else None,
    )


@router.get("/{run_id}/events", response_model=list[TraceEventOut])
async def trace(
    run_id: str,
    after_seq: int = Query(0, alias="afterSeq", ge=0),
    user=Depends(current_user),
    container: Container = Depends(get_container),
) -> list[TraceEventOut]:
    """Traza persistida. El canal en vivo con replay llega en ORQ-17."""
    await container.get_run()(run_id)  # 404 si no existe
    events = await container.runs.events(run_id, after_seq=after_seq)
    return [TraceEventOut.from_domain(e) for e in events]


@router.post("/{run_id}/cancel", response_model=RunOut)
async def cancel(
    run_id: str,
    user=Depends(requires(Permission.EJECUTAR)),
    container: Container = Depends(get_container),
) -> RunOut:
    """Detiene la ejecución: corta las llamadas en curso y cierra los agentes pendientes."""
    return RunOut.from_domain(await container.cancel_run()(run_id, by=user.email))


@router.get("/{run_id}/deliverables", response_model=DeliverablesOut)
async def deliverables(
    run_id: str,
    user=Depends(current_user),
    container: Container = Depends(get_container),
) -> DeliverablesOut:
    return DeliverablesOut.from_domain(await container.get_deliverables()(run_id))
