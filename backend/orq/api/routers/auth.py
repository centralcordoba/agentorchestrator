"""Entrar, salir y saber quién soy."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response
from pydantic import Field

from ...application.auth import LoginCommand
from ...domain.identity import PERMISSION_LABELS, ROLE_LABELS, ROLE_PERMISSIONS
from ..container import Container
from ..deps import SESSION_COOKIE, current_user, get_container, optional_user
from ..schemas import ERROR_RESPONSES, Schema, UserOut

router = APIRouter(prefix="/auth", tags=["identidad"], responses=ERROR_RESPONSES)


class LoginIn(Schema):
    email: str = Field(min_length=3)
    password: str = Field(min_length=1)


class ChangePasswordBody(Schema):
    current: str = Field(min_length=1)
    new: str = Field(min_length=12)


class SessionOut(Schema):
    """Quién eres y qué puedes hacer. Lo pide la aplicación al cargar."""

    user: UserOut | None = None
    authenticated: bool = False


class CatalogOut(Schema):
    """Roles y permisos, para que la UI no duplique la tabla del dominio."""

    roles: dict[str, str]
    permissions: dict[str, str]
    role_permissions: dict[str, list[str]]


def _set_session_cookie(response: Response, token: str, *, secure: bool, max_age: int) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=max_age,
        httponly=True,  # el JavaScript de la página no puede leerla
        secure=secure,  # solo por HTTPS cuando el despliegue lo tiene
        samesite="lax",  # no viaja en peticiones de otros sitios: corta el CSRF de formulario
        path="/",
    )


@router.post("/login", response_model=SessionOut)
async def login(
    body: LoginIn,
    request: Request,
    response: Response,
    container: Container = Depends(get_container),
) -> SessionOut:
    """Inicia sesión.

    Con credenciales incorrectas responde siempre lo mismo, exista o no el correo: decir «ese
    usuario no existe» le confirma a quien prueba direcciones cuáles son válidas.
    """
    resultado = await container.login()(
        LoginCommand(
            email=body.email,
            password=body.password,
            user_agent=request.headers.get("user-agent", "")[:255],
            ip=request.client.host if request.client else "",
        )
    )
    _set_session_cookie(
        response,
        resultado.token,
        secure=container.settings.session_cookie_secure,
        max_age=int(container.settings.session_max_age_minutes * 60),
    )
    return SessionOut(user=UserOut.from_domain(resultado.user), authenticated=True)


@router.post("/logout", status_code=204)
async def logout(
    request: Request, response: Response, container: Container = Depends(get_container)
) -> None:
    """Cierra la sesión. Es idempotente: sin cookie no falla."""
    token = request.cookies.get(SESSION_COOKIE, "")
    auth = getattr(request.state, "auth", None)
    await container.logout()(token, user=auth.user if auth else None)
    response.delete_cookie(SESSION_COOKIE, path="/")


@router.get("/me", response_model=SessionOut)
async def me(user=Depends(optional_user)) -> SessionOut:
    """Quién soy. Sin sesión responde `authenticated: false`, no un error.

    Es a propósito: la aplicación lo llama al cargar para decidir si enseña el login o la
    aplicación, y un 401 ahí ensuciaría la consola del navegador en cada arranque.
    """
    if user is None:
        return SessionOut(authenticated=False)
    return SessionOut(user=UserOut.from_domain(user), authenticated=True)


@router.put("/password", status_code=204)
async def change_password(
    body: ChangePasswordBody,
    request: Request,
    user=Depends(current_user),
    container: Container = Depends(get_container),
) -> None:
    """Cambia la contraseña propia y cierra las demás sesiones."""
    await container.change_password()(
        user=user,
        current=body.current,
        new=body.new,
        keep_session=request.cookies.get(SESSION_COOKIE, ""),
    )


@router.get("/catalog", response_model=CatalogOut)
async def catalog() -> CatalogOut:
    """Roles y permisos. La UI los consulta en vez de copiar la tabla."""
    return CatalogOut(
        roles={role.value: label for role, label in ROLE_LABELS.items()},
        permissions={p.value: label for p, label in PERMISSION_LABELS.items()},
        role_permissions={
            role.value: sorted(p.value for p in permisos)
            for role, permisos in ROLE_PERMISSIONS.items()
        },
    )
