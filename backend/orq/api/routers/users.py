"""Gestión de personas. Solo para quien tenga el permiso de gestionar usuarios."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import Field

from ...application.auth import CreateUserCommand, UpdateUserCommand
from ...domain.identity import Permission, Role
from ..container import Container
from ..deps import get_container, requires
from ..schemas import ERROR_RESPONSES, Schema, UserOut

router = APIRouter(prefix="/users", tags=["identidad"], responses=ERROR_RESPONSES)


class CreateUserIn(Schema):
    email: str = Field(min_length=3)
    name: str = ""
    role: Role
    #: Contraseña inicial. La persona la cambia al entrar si `mustChangePassword` es cierto.
    password: str = Field(min_length=12)
    must_change_password: bool = True


class UpdateUserIn(Schema):
    role: Role | None = None
    active: bool | None = None
    name: str | None = None


class UserPage(Schema):
    items: list[UserOut]
    total: int


@router.get("", response_model=UserPage)
async def index(
    user=Depends(requires(Permission.GESTIONAR_USUARIOS)),
    container: Container = Depends(get_container),
) -> UserPage:
    ahora = datetime.now(timezone.utc)
    personas = await container.list_users()(by=user)
    return UserPage(
        items=[UserOut.from_domain(p, now=ahora) for p in personas], total=len(personas)
    )


@router.post("", status_code=201, response_model=UserOut)
async def create(
    body: CreateUserIn,
    user=Depends(requires(Permission.GESTIONAR_USUARIOS)),
    container: Container = Depends(get_container),
) -> UserOut:
    creado = await container.create_user()(
        CreateUserCommand(
            email=body.email,
            name=body.name,
            role=body.role,
            password=body.password,
            must_change_password=body.must_change_password,
        ),
        by=user,
    )
    return UserOut.from_domain(creado)


@router.put("/{user_id}", response_model=UserOut)
async def update(
    user_id: str,
    body: UpdateUserIn,
    user=Depends(requires(Permission.GESTIONAR_USUARIOS)),
    container: Container = Depends(get_container),
) -> UserOut:
    """Cambia rol, nombre o si la cuenta está activa.

    Desactivar o cambiar de rol **cierra las sesiones abiertas** de esa persona: si no, el cambio
    no surtiría efecto hasta que cerrara sesión por su cuenta.
    """
    actualizado = await container.update_user()(
        UpdateUserCommand(
            user_id=user_id, role=body.role, active=body.active, name=body.name
        ),
        by=user,
    )
    return UserOut.from_domain(actualizado)
