"""Punto de entrada del servicio."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import errors
from .api.container import Container, build_container
from .api.routers import (
    audit,
    auth,
    catalog,
    health,
    requirements,
    runs,
    secrets,
    stream,
    users,
)
from .config import Settings, load_settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("orq")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Al arrancar, recupera lo que quedó a medias; al apagar, espera a lo que esté vivo."""
    container: Container = app.state.container
    await container.startup()
    resumed = await container.resume_runs()()
    if resumed:
        log.info("reanudadas %s ejecución(es) interrumpidas: %s", len(resumed), [r.id for r in resumed])
    try:
        yield
    finally:
        await container.supervisor.drain()
        await container.shutdown()


def create_app(settings: Settings | None = None, *, container: Container | None = None) -> FastAPI:
    """Crea la aplicación. Las pruebas pasan su propio contenedor con dobles."""
    settings = settings or load_settings()
    app = FastAPI(
        title="Orquestador de revisión de requerimientos",
        description=(
            "Backend del orquestador multiagente. El dominio gira alrededor de un Requerimiento: "
            "adjuntos, plan de agentes, ejecuciones y entregables."
        ),
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state.container = container or build_container(settings)
    errors.install(app)

    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(settings.cors_origins),
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    # Identidad primero: es lo unico que funciona sin sesion.
    app.include_router(auth.router, prefix="/api")
    app.include_router(users.router, prefix="/api")
    app.include_router(health.router, prefix="/api")
    app.include_router(catalog.router, prefix="/api")
    app.include_router(requirements.router, prefix="/api")
    app.include_router(runs.router, prefix="/api")
    app.include_router(audit.router, prefix="/api")
    app.include_router(secrets.router, prefix="/api")
    # Canal en vivo: WebSocket, fuera del contrato OpenAPI (que solo describe HTTP).
    app.include_router(stream.router, prefix="/api")
    return app


app = create_app()
