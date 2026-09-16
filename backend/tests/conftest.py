"""Utilidades comunes de las pruebas.

Todo determinista y sin red: reloj fijo, identificadores secuenciales y proveedor `mock`.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

import pytest

from orq.api.container import Container
from orq.application.auth import CreateUserCommand
from orq.config import Settings
from orq.domain.enums import AttachmentKind, PhiClassification, ProviderId
from orq.domain.identity import Role
from orq.domain.requirement import Attachment, Requirement
from orq.infrastructure.ai.gateway import AIGateway
from orq.infrastructure.events import NullEventBus
from orq.infrastructure.persistence import (
    InMemoryAuditLog,
    InMemoryPlanRepository,
    InMemoryProfileRepository,
    InMemoryRequirementRepository,
    InMemoryRunRepository,
)
from orq.infrastructure.auth import InMemorySessionRepository, InMemoryUserRepository
from orq.infrastructure.profiles import default_profiles
from orq.infrastructure.secrets import InMemorySecretVault, SecretScrubber
from orq.infrastructure.services import FixedClock, SequentialIdGenerator

START = datetime(2026, 9, 15, 10, 0, tzinfo=timezone.utc)


def run_async(coro: Any) -> Any:
    """Ejecuta una corrutina sin depender de pytest-asyncio."""
    return asyncio.run(coro)


@pytest.fixture
def settings() -> Settings:
    return Settings(ai_provider=ProviderId.MOCK, ai_max_attempts=2, cors_origins=())


def make_container(settings: Settings, *, gateway: Any = None) -> Container:
    """Contenedor de pruebas. El supervisor se crea con la pasarela que se le pase."""
    return Container(
        settings=settings,
        clock=FixedClock(START),
        ids=SequentialIdGenerator(),
        events=NullEventBus(),
        gateway=gateway or AIGateway(max_attempts=settings.ai_max_attempts),
        requirements=InMemoryRequirementRepository(),
        plans=InMemoryPlanRepository(),
        runs=InMemoryRunRepository(),
        profiles=InMemoryProfileRepository(default_profiles(force_provider=ProviderId.MOCK)),
        audit=InMemoryAuditLog(),
        vault=InMemorySecretVault(),
        scrubber=SecretScrubber(),
        users=InMemoryUserRepository(),
        sessions=InMemorySessionRepository(),
    )


@pytest.fixture
def container(settings: Settings) -> Container:
    return make_container(settings)


def make_requirement(
    *,
    id: str = "REQ-001",
    title: str = "Conciliación de pagos del portal de pacientes",
    description: str = "Ajustar la pantalla de pagos y la consulta de la tabla de conciliación.",
    phi: PhiClassification = PhiClassification.DESCONOCIDO,
    kinds: tuple[AttachmentKind, ...] = (
        AttachmentKind.REPO,
        AttachmentKind.VTR_TEMPLATE,
        AttachmentKind.KIUWAN_CSV,
    ),
    criteria: tuple[str, ...] = ("El pago se concilia en el mismo día", "El portal muestra el estado"),
) -> Requirement:
    attachments = tuple(
        Attachment(
            id=f"ATT-{index:03d}",
            kind=kind,
            name=f"adjunto-{kind.value}",
            added_by="ana",
            added_at=START,
        )
        for index, kind in enumerate(kinds, start=1)
    )
    return Requirement(
        id=id,
        title=title,
        description=description,
        owner="ana",
        created_at=START,
        acceptance_criteria=criteria,
        phi=phi,
        attachments=attachments,
    )


def make_user(
    container: Container,
    *,
    email: str = "ana@acme.test",
    role: Role = Role.ADMINISTRADOR,
    password: str = "contrasena-de-prueba-larga",
) -> Any:
    """Crea una persona directamente en el contenedor, sin pasar por permisos."""
    return run_async(
        container.create_user().unchecked(
            CreateUserCommand(email=email, name=email.split("@")[0], role=role, password=password)
        )
    )


def logged_client(
    settings: Settings,
    container: Container | None = None,
    *,
    role: Role = Role.ADMINISTRADOR,
    email: str = "ana@acme.test",
    password: str = "contrasena-de-prueba-larga",
) -> tuple[Any, Container]:
    """Cliente HTTP con sesión abierta.

    Desde ORQ-5 **ninguna ruta de datos funciona sin sesión**, así que las pruebas de API entran
    igual que lo haría una persona: por `/api/auth/login`, y el resto va con la cookie.
    """
    from fastapi.testclient import TestClient

    from orq.main import create_app

    container = container or make_container(settings)
    if run_async(container.users.by_email(email)) is None:
        make_user(container, email=email, role=role, password=password)
    client = TestClient(create_app(settings, container=container))
    respuesta = client.post("/api/auth/login", json={"email": email, "password": password})
    assert respuesta.status_code == 200, respuesta.text
    return client, container
