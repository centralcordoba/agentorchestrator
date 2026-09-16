"""Errores de la API con una forma única."""
from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from .deps import EXPIRED_HEADER, SESSION_COOKIE
from ..domain.identity import (
    AccountLockedError,
    ForbiddenError,
    InvalidCredentialsError,
    NotAuthenticatedError,
)
from ..domain.errors import (
    BudgetExceededError,
    DomainError,
    InvalidAgentOutputError,
    NotFoundError,
    PlanBlockedError,
    PolicyViolationError,
    ProviderError,
    ToolNotAllowedError,
)

log = logging.getLogger(__name__)

#: Error del dominio → código HTTP. Lo que no esté aquí es una petición mal formada (400).
STATUS_BY_ERROR: list[tuple[type[DomainError], int]] = [
    (NotAuthenticatedError, 401),
    (ForbiddenError, 403),
    (InvalidCredentialsError, 401),
    (AccountLockedError, 423),
    (NotFoundError, 404),
    (PlanBlockedError, 409),
    (BudgetExceededError, 402),
    (PolicyViolationError, 403),
    (ToolNotAllowedError, 403),
    (InvalidAgentOutputError, 502),
    (ProviderError, 502),
]


def status_for(error: Exception) -> int:
    for error_type, status in STATUS_BY_ERROR:
        if isinstance(error, error_type):
            return status
    return 400


def error_body(code: str, message: str, detail: dict | None = None) -> dict:
    body: dict = {"code": code, "message": message}
    if detail:
        body["detail"] = detail
    return body


def install(app: FastAPI) -> None:
    """Registra los manejadores. Una sola forma de error para toda la API."""

    @app.exception_handler(DomainError)
    async def _domain(request: Request, error: DomainError) -> JSONResponse:
        detail = {"reasons": error.reasons} if isinstance(error, PlanBlockedError) else None
        respuesta = JSONResponse(
            status_code=status_for(error),
            content=error_body(type(error).__name__, str(error), detail),
        )
        # Cuando la sesión caducó, el 401 lleva el motivo y borra la cookie muerta. La dependencia
        # no puede hacerlo: al lanzar, su `Response` se descarta y esta es la que sale (ORQ-5).
        auth = getattr(request.state, "auth", None)
        if auth is not None and getattr(auth, "expired_reason", ""):
            respuesta.headers[EXPIRED_HEADER] = auth.expired_reason
            respuesta.delete_cookie(SESSION_COOKIE, path="/")
        return respuesta

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, error: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=error_body(
                "ValidationError",
                "La petición no tiene el formato esperado.",
                {"errors": _safe_errors(error)},
            ),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, error: StarletteHTTPException) -> JSONResponse:
        # Un 404 de ruta inexistente también sale con la forma de siempre.
        if isinstance(error.detail, dict) and "code" in error.detail:
            return JSONResponse(status_code=error.status_code, content=error.detail)
        return JSONResponse(
            status_code=error.status_code,
            content=error_body(f"Http{error.status_code}", str(error.detail)),
        )

    @app.exception_handler(Exception)
    async def _unexpected(request: Request, error: Exception) -> JSONResponse:
        # El detalle interno va al log, no a la respuesta: podría llevar datos del cliente.
        log.exception("error no controlado en %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content=error_body("InternalError", "Error interno del servicio."),
        )


def _safe_errors(error: RequestValidationError) -> list[dict]:
    """Errores de validación sin el valor recibido: podría contener datos del cliente."""
    return [
        {"loc": [str(part) for part in item.get("loc", ())], "msg": item.get("msg", ""), "type": item.get("type", "")}
        for item in error.errors()
    ]
