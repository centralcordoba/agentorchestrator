"""Salud del servicio."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from ... import __version__
from ..container import Container
from ..deps import get_container
from ..schemas import ERROR_RESPONSES, HealthOut

router = APIRouter(tags=["salud"], responses=ERROR_RESPONSES)


@router.get("/health", response_model=HealthOut)
async def health(container: Container = Depends(get_container)) -> HealthOut:
    """Estado y configuración efectiva. Nunca devuelve el valor de una credencial."""
    database = "memoria"
    if container.database is not None:
        database = "ok" if await container.database.ping() else "sin conexión"
    return HealthOut(
        status="ok",
        version=__version__,
        database=database,
        config=container.settings.describe(),
    )
