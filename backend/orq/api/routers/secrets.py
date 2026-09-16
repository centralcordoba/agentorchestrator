"""Bóveda de secretos: escribir sí, leer no."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from pydantic import Field

from ...application.use_cases import SaveSecretCommand
from ...domain.secrets import ORGANIZATION, SecretKind
from ..container import Container
from ...domain.identity import Permission
from ..deps import get_container, requires
from ..schemas import ERROR_RESPONSES, Schema, SecretOut

router = APIRouter(prefix="/secrets", tags=["secretos"], responses=ERROR_RESPONSES)


class SaveSecretIn(Schema):
    """Lo que entra. `value` es lo único que no vuelve a salir por ninguna ruta."""

    kind: SecretKind
    name: str = Field(min_length=1, description="Host, URL del sitio o proveedor")
    value: str = Field(min_length=8, description="El secreto. No se devuelve nunca.")
    scope: str = Field(
        ORGANIZATION,
        description="Vacío = toda la organización. Si no, el requerimiento al que pertenece.",
    )
    username: str = Field("", description="Usuario, cuando es un par usuario/contraseña")
    expires_at: datetime | None = None


class SecretPage(Schema):
    items: list[SecretOut]
    total: int


@router.get("", response_model=SecretPage)
async def index(
    scope: str | None = Query(
        None, description="Filtrar por ámbito. Ausente = todos; vacío = organización."
    ),
    user=Depends(requires(Permission.GESTIONAR_SECRETOS)),
    container: Container = Depends(get_container),
) -> SecretPage:
    """Qué secretos hay configurados: tipo, a qué se aplican, quién y cuándo. **Sin valores.**"""
    ahora = datetime.now(timezone.utc)
    items = await container.list_secrets()(scope=scope)
    return SecretPage(
        items=[SecretOut.from_domain(s, now=ahora) for s in items], total=len(items)
    )


@router.post("", status_code=201, response_model=SecretOut)
async def save(
    body: SaveSecretIn,
    user=Depends(requires(Permission.GESTIONAR_SECRETOS)),
    container: Container = Depends(get_container),
) -> SecretOut:
    """Guarda o **rota** un secreto.

    Guardar otra vez el mismo tipo, nombre y ámbito sustituye el valor y levanta una revocación
    anterior: es la rotación. La respuesta son metadatos.
    """
    metadata = await container.save_secret()(
        SaveSecretCommand(
            kind=body.kind,
            name=body.name,
            value=body.value,
            scope=body.scope,
            username=body.username,
            expires_at=body.expires_at,
            by=user.email,
        )
    )
    return SecretOut.from_domain(metadata, now=datetime.now(timezone.utc))


@router.delete("/{secret_id}", response_model=SecretOut)
async def revoke(
    secret_id: str,
    user=Depends(requires(Permission.GESTIONAR_SECRETOS)),
    container: Container = Depends(get_container),
) -> SecretOut:
    """Revoca un secreto: deja de funcionar de inmediato y su valor se borra de la base."""
    metadata = await container.revoke_secret()(secret_id, by=user.email)
    return SecretOut.from_domain(metadata, now=datetime.now(timezone.utc))
