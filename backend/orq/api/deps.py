"""Dependencias de FastAPI."""
from __future__ import annotations

from fastapi import Depends, Request, Response

from ..application.auth import Authenticated
from ..domain.identity import (
    ForbiddenError,
    NotAuthenticatedError,
    Permission,
    User,
)
from .container import Container

#: Nombre de la cookie de sesión. `__Host-` no se usa porque obliga a HTTPS y en desarrollo se
#: sirve por HTTP; al desplegar con TLS conviene cambiarlo (ORQ-31).
SESSION_COOKIE = "orq_session"

#: Cabecera con el motivo de que la sesión ya no valga. La UI la lee para decir «caducó por
#: inactividad» en vez de un genérico «no autorizado».
EXPIRED_HEADER = "X-Sesion-Caducada"


def get_container(request: Request) -> Container:
    return request.app.state.container


async def authenticate(
    request: Request, response: Response, container: Container = Depends(get_container)
) -> Authenticated:
    """Resuelve la cookie. No lanza: hay rutas que funcionan sin sesión."""
    token = request.cookies.get(SESSION_COOKIE, "")
    resultado = await container.resolve_session()(token)
    if resultado.expired_reason:
        # Se borra la cookie muerta para que el navegador deje de mandarla, y se dice por qué.
        response.delete_cookie(SESSION_COOKIE, path="/")
        response.headers[EXPIRED_HEADER] = resultado.expired_reason
    request.state.auth = resultado
    return resultado


async def current_user(auth: Authenticated = Depends(authenticate)) -> User:
    """Usuario autenticado. Falla con 401 si no hay sesión válida."""
    if auth.user is None:
        raise NotAuthenticatedError(
            "La sesión caducó por inactividad. Vuelve a entrar."
            if auth.expired_reason == "inactividad"
            else "Hace falta iniciar sesión."
        )
    return auth.user


async def optional_user(auth: Authenticated = Depends(authenticate)) -> User | None:
    return auth.user


def requires(permission: Permission):
    """Dependencia que exige un permiso concreto.

    Es lo que hace cierto el criterio «un usuario sin permiso recibe 403 aunque llame directamente
    a la API»: la comprobación está en el servidor, y la UI solo oculta lo que además está
    bloqueado aquí.
    """

    async def comprobar(user: User = Depends(current_user)) -> User:
        if not user.can(permission):
            raise ForbiddenError(
                f"Tu rol no tiene el permiso «{permission.value}» para esta acción."
            )
        return user

    return comprobar
