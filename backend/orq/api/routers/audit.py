"""Auditoría: consulta y verificación de la cadena."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from ...domain.audit import verify_chain
from ..container import Container
from ...domain.identity import Permission
from ..deps import get_container, requires
from ..schemas import ERROR_RESPONSES, AuditEntryOut, AuditVerificationOut, Schema


class AuditPage(Schema):
    items: list[AuditEntryOut]
    total: int
    limit: int
    offset: int


router = APIRouter(prefix="/audit", tags=["auditoría"], responses=ERROR_RESPONSES)


@router.get("", response_model=AuditPage)
async def index(
    target: str | None = Query(None, description="Requerimiento o ejecución"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    user=Depends(requires(Permission.VER_AUDITORIA)),
    container: Container = Depends(get_container),
) -> AuditPage:
    entries = await container.audit.list(target=target, limit=limit, offset=offset)
    return AuditPage(
        items=[AuditEntryOut.from_domain(e) for e in entries],
        total=await container.audit.count(target=target),
        limit=limit,
        offset=offset,
    )


@router.get("/verify", response_model=AuditVerificationOut)
async def verify(
    user=Depends(requires(Permission.VER_AUDITORIA)),
    container: Container = Depends(get_container),
) -> AuditVerificationOut:
    """Recalcula la cadena y dice si alguien tocó una entrada."""
    entries = await container.audit.list(limit=1000)
    stored = await container.audit.stored_hashes(limit=1000)
    broken = verify_chain(entries, hashes=stored)
    return AuditVerificationOut(
        entries=len(entries),
        valid=broken is None,
        broken_at=entries[broken].seq if broken is not None else None,
    )
