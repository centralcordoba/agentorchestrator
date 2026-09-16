"""Persistencia real: PostgreSQL en contenedor, no SQLite.

Estas pruebas necesitan una base de datos viva. Sin `TEST_DATABASE_URL` se saltan, y así el
conjunto sigue corriendo en cualquier máquina; en integración continua la variable estará puesta
(ORQ-30).

    docker run -d --name orq-postgres -e POSTGRES_PASSWORD=orq -e POSTGRES_USER=orq \
        -e POSTGRES_DB=orq -p 55432:5432 postgres:16-alpine
    set TEST_DATABASE_URL=postgresql://orq:orq@localhost:55432/orq
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
import sqlalchemy as sa

from orq.api.container import Container
from orq.application.use_cases import CreateRequirementCommand, NewAttachment, StartRunCommand
from orq.config import Settings
from orq.domain.audit import AuditAction, verify_chain
from orq.domain.enums import (
    AgentId,
    AgentRunStatus,
    AttachmentKind,
    FileStatus,
    PhiClassification,
    ProviderId,
    RunStatus,
)
from orq.domain.planning import suggest_plan
from orq.domain.requirement import Attachment, RepoCommit, RepoFile, RepoInfo, Requirement
from orq.domain.run import ProfileSnapshot, Run
from orq.infrastructure.ai.gateway import AIGateway
from orq.infrastructure.db import (
    Cipher,
    Database,
    PostgresAuditLog,
    PostgresIdGenerator,
    PostgresPlanRepository,
    PostgresProfileRepository,
    PostgresRequirementRepository,
    PostgresRunRepository,
    RetentionService,
    metadata,
    normalize_url,
)
from orq.infrastructure.db import schema as s
from orq.infrastructure.events import NullEventBus
from orq.infrastructure.profiles import default_profiles
from orq.infrastructure.services import FixedClock, SequentialIdGenerator

from .conftest import START

DATABASE_URL = os.getenv("TEST_DATABASE_URL", "").strip()

pytestmark = [
    pytest.mark.skipif(
        not DATABASE_URL, reason="Sin TEST_DATABASE_URL: no hay PostgreSQL contra el que probar."
    ),
    # asyncpg ata sus conexiones al bucle que las creó: toda la prueba va en el mismo.
    pytest.mark.asyncio,
]


@pytest_asyncio.fixture
async def database():
    """Base limpia para cada prueba: el esquema se recrea desde el metadata."""
    db = Database(url=normalize_url(DATABASE_URL), cipher=Cipher(Cipher.generate_key()))
    async with db.engine.begin() as connection:
        await connection.run_sync(metadata.drop_all)
        await connection.run_sync(metadata.create_all)
    try:
        yield db
    finally:
        await db.dispose()


def _requirement() -> Requirement:
    repo = RepoInfo(
        provider="github",
        owner="acme",
        name="portal",
        full_name="acme/portal",
        html_url="https://github.com/acme/portal",
        default_branch="main",
        branch="feature/pagos",
        base="main",
        head_sha="abc123",
        description="Portal de pacientes",
        range_label="main…feature/pagos",
        ahead_by=3,
        commits=(
            RepoCommit(sha="abc123", message="Conciliación", author="ana", date="2026-09-01"),
        ),
        files=(
            RepoFile(path="src/pagos.py", status=FileStatus.MODIFIED, additions=12, deletions=3),
            RepoFile(path="sql/conciliacion.sql", status=FileStatus.ADDED, additions=40),
        ),
        languages={"Python": 900},
        fetched_at=START,
    )
    return Requirement(
        id="REQ-001",
        title="Conciliación de pagos del portal",
        description="Ajustar la pantalla de pagos y la tabla de conciliación.",
        owner="ana",
        created_at=START,
        acceptance_criteria=("El pago se concilia el mismo día", "El portal muestra el estado"),
        phi=PhiClassification.SI,
        phi_set_by="ana",
        attachments=(
            Attachment(
                id="ATT-001",
                kind=AttachmentKind.REPO,
                name="acme/portal",
                added_by="ana",
                added_at=START,
                detail="rama feature/pagos",
                repo=repo,
            ),
            Attachment(
                id="ATT-002",
                kind=AttachmentKind.VTR_TEMPLATE,
                name="plantilla.docx",
                added_by="ana",
                added_at=START,
            ),
        ),
    )


async def _container(database: Database) -> Container:
    profiles = PostgresProfileRepository(
        database, seed=default_profiles(force_provider=ProviderId.MOCK)
    )
    await profiles.ensure_seeded()
    return Container(
        settings=Settings(ai_provider=ProviderId.MOCK, cors_origins=()),
        clock=FixedClock(START),
        ids=SequentialIdGenerator(),
        events=NullEventBus(),
        gateway=AIGateway(),
        requirements=PostgresRequirementRepository(database),
        plans=PostgresPlanRepository(database),
        runs=PostgresRunRepository(database),
        profiles=profiles,
        audit=PostgresAuditLog(database),
        database=database,
    )


async def test_requirement_round_trip(database: Database) -> None:
    repository = PostgresRequirementRepository(database)
    original = _requirement()

    await repository.add(original)
    recovered = await repository.get(original.id)

    assert recovered == original  # incluye adjuntos y el repositorio conectado entero
    assert recovered.repo is not None
    assert recovered.repo.files[1].path == "sql/conciliacion.sql"
    assert await repository.list() == [original]
    assert await repository.get("REQ-999") is None


async def test_sensitive_columns_are_encrypted_at_rest(database: Database) -> None:
    """Quien lea la tabla sin la clave no ve el contenido."""
    await PostgresRequirementRepository(database).add(_requirement())

    async with database.session() as session:
        row = (
            await session.execute(
                sa.select(s.requirements.c.title_enc, s.requirements.c.description_enc)
            )
        ).first()
    assert row is not None
    title, description = row
    assert b"Conciliaci" not in title
    assert b"pantalla de pagos" not in description

    # Con otra clave no se descifra: el contenido no viaja con una copia de la base.
    other = Database(url=normalize_url(DATABASE_URL), cipher=Cipher(Cipher.generate_key()))
    try:
        with pytest.raises(Exception):
            await PostgresRequirementRepository(other).get("REQ-001")
    finally:
        await other.dispose()


async def test_plan_round_trip(database: Database) -> None:
    requirements = PostgresRequirementRepository(database)
    plans = PostgresPlanRepository(database)
    requirement = _requirement()
    await requirements.add(requirement)

    plan = suggest_plan(requirement, now=START)
    await plans.save(requirement.id, plan)
    assert await plans.get(requirement.id) == plan

    # Guardar otra vez actualiza en lugar de duplicar.
    toggled = plan.toggled(AgentId.UIUX, enabled=False, by="ana")
    await plans.save(requirement.id, toggled)
    assert await plans.get(requirement.id) == toggled


async def test_profiles_round_trip_and_seed(database: Database) -> None:
    seed = default_profiles(force_provider=ProviderId.MOCK)
    profiles = PostgresProfileRepository(database, seed=seed)

    await profiles.ensure_seeded()
    await profiles.ensure_seeded()  # idempotente

    assert await profiles.defaults() == seed

    # Un ajuste por requerimiento se superpone al global sin pisarlo.
    override = seed[AgentId.CODE].with_prompt(
        system_prompt="prompt del requerimiento",
        task_prompt="tarea",
        author="ana",
        note="ajuste local",
        at=START,
    )
    await profiles.save_override("REQ-001", override)

    effective = await profiles.effective("REQ-001")
    assert effective[AgentId.CODE].system_prompt == "prompt del requerimiento"
    assert effective[AgentId.CODE].prompt_version == 2
    assert len(effective[AgentId.CODE].versions) == 2  # el historial se conserva entero

    defaults = await profiles.defaults()
    assert defaults[AgentId.CODE].prompt_version == 1


async def test_full_run_survives_a_round_trip(database: Database) -> None:
    container = await _container(database)

    requirement = await container.create_requirement()(
        CreateRequirementCommand(
            title="Conciliación de pagos",
            description="Pantalla de pagos y tabla de conciliación.",
            owner="ana",
            acceptance_criteria=("El pago se concilia el mismo día",),
            phi=PhiClassification.SI,
            attachments=(
                NewAttachment(kind=AttachmentKind.REPO, name="acme/portal"),
                NewAttachment(kind=AttachmentKind.VTR_TEMPLATE, name="plantilla.docx"),
            ),
        )
    )
    await container.suggest_plan()(requirement.id)
    run = await container.start_run()(
        StartRunCommand(requirement_id=requirement.id, started_by="ana", wait=True)
    )
    assert run.status is RunStatus.COMPLETADA

    # Lo que se lee de la base es lo mismo que quedó en memoria.
    recovered = await container.runs.get(run.id)
    assert recovered is not None
    assert recovered.status is RunStatus.COMPLETADA
    assert recovered.enabled_agents == run.enabled_agents
    assert recovered.profiles == run.profiles
    for agent_id in run.enabled_agents:
        original = run.execution(agent_id)
        stored = recovered.execution(agent_id)
        assert stored.status is original.status
        assert stored.output == original.output
        assert stored.usage == original.usage
        assert len(stored.calls) == len(original.calls)

    events = await container.runs.events(run.id)
    assert events
    assert [e.seq for e in events] == sorted(e.seq for e in events)
    assert await container.runs.events(run.id, after_seq=events[0].seq) == events[1:]

    view = await container.get_run()(run.id)
    assert view.deliverables.verdict is not None


async def test_frozen_profiles_are_never_rewritten(database: Database) -> None:
    """La ejecución congela proveedor, modelo y versión de prompt; el `UPDATE` no los toca."""
    container = await _container(database)
    requirement = await container.create_requirement()(
        CreateRequirementCommand(
            title="Requerimiento", description="", owner="ana", phi=PhiClassification.NO
        )
    )
    run = Run(
        id="RUN-FIJA",
        requirement_id=requirement.id,
        started_by="ana",
        started_at=START,
        enabled_agents=(AgentId.CODE,),
        profiles={
            AgentId.CODE: ProfileSnapshot(provider=ProviderId.MOCK, model="mock", prompt_version=1)
        },
    )
    await container.runs.add(run)

    # Alguien intenta guardar la misma ejecución con otros perfiles.
    run.profiles[AgentId.CODE] = ProfileSnapshot(
        provider=ProviderId.ANTHROPIC, model="otro-modelo", prompt_version=9
    )
    run.status = RunStatus.COMPLETADA
    await container.runs.save(run)

    stored = await container.runs.get(run.id)
    assert stored is not None
    assert stored.status is RunStatus.COMPLETADA  # el estado sí se actualiza
    snapshot = stored.profile(AgentId.CODE)
    assert snapshot.provider is ProviderId.MOCK
    assert snapshot.model == "mock"
    assert snapshot.prompt_version == 1


async def test_unfinished_runs_are_listed_for_resume(database: Database) -> None:
    container = await _container(database)
    requirement = await container.create_requirement()(
        CreateRequirementCommand(
            title="Requerimiento", description="", owner="ana", phi=PhiClassification.NO
        )
    )

    for run_id, status in (("RUN-A", RunStatus.EN_CURSO), ("RUN-B", RunStatus.COMPLETADA)):
        run = Run(
            id=run_id,
            requirement_id=requirement.id,
            started_by="ana",
            started_at=START,
            enabled_agents=(AgentId.CODE,),
            profiles={
                AgentId.CODE: ProfileSnapshot(
                    provider=ProviderId.MOCK, model="mock", prompt_version=1
                )
            },
            status=status,
        )
        run.execution(AgentId.CODE).status = AgentRunStatus.TRABAJANDO
        await container.runs.add(run)

    unfinished = await container.runs.list_unfinished()
    assert [r.id for r in unfinished] == ["RUN-A"]


async def test_ids_do_not_restart_after_a_restart(database: Database) -> None:
    """Con persistencia, un contador en memoria pisaría lo ya guardado."""
    first = PostgresIdGenerator(database)
    assert [await first.new_id("REQ") for _ in range(3)] == ["REQ-001", "REQ-002", "REQ-003"]

    # Otro proceso (o el mismo tras reiniciar) sigue la cuenta, no la reinicia.
    second = PostgresIdGenerator(database)
    assert await second.new_id("REQ") == "REQ-004"
    # Cada prefijo lleva su propia cuenta.
    assert await second.new_id("RUN") == "RUN-001"


async def test_audit_is_append_only_and_chained(database: Database) -> None:
    log = PostgresAuditLog(database)
    for index in range(3):
        await log.append(
            at=START + timedelta(minutes=index),
            actor="ana",
            action=AuditAction.REQUERIMIENTO_CREADO,
            target=f"REQ-{index:03d}",
            detail="alta",
        )

    entries = await log.list()
    hashes = await log.stored_hashes()
    assert len(entries) == 3
    assert verify_chain(entries, hashes=hashes) is None
    assert entries[1].prev_hash == entries[0].hash

    # El repositorio no ofrece modificar ni borrar: no es un olvido, es el contrato.
    assert not hasattr(log, "update")
    assert not hasattr(log, "delete")

    # Si alguien altera una fila por detrás, la verificación lo detecta.
    async with database.session() as session:
        await session.execute(
            sa.update(s.audit_entries)
            .where(s.audit_entries.c.target == "REQ-001")
            .values(detail="otra cosa")
        )
    tampered = await log.list()
    assert verify_chain(tampered, hashes=await log.stored_hashes()) == 1


async def test_use_cases_leave_their_trail(database: Database) -> None:
    container = await _container(database)
    requirement = await container.create_requirement()(
        CreateRequirementCommand(
            title="Requerimiento con PHI",
            description="",
            owner="ana",
            phi=PhiClassification.SI,
            attachments=(NewAttachment(kind=AttachmentKind.VTR_TEMPLATE, name="p.docx"),),
        )
    )
    await container.suggest_plan()(requirement.id)

    entries = await container.audit.list(target=requirement.id)
    actions = [e.action for e in entries]
    assert AuditAction.REQUERIMIENTO_CREADO in actions
    assert AuditAction.CLASIFICACION_PHI in actions
    assert AuditAction.PLAN_SUGERIDO in actions
    # El detalle describe la acción; no copia el contenido del requerimiento.
    assert all("Requerimiento con PHI" not in e.detail for e in entries)


async def test_retention_purges_the_requirement_and_everything_under_it(
    database: Database,
) -> None:
    container = await _container(database)
    retention = RetentionService(database, default_days=30)
    assert retention.due_date(START) == START + timedelta(days=30)

    requirement = await container.create_requirement()(
        CreateRequirementCommand(
            title="Antiguo",
            description="",
            owner="ana",
            phi=PhiClassification.NO,
            attachments=(NewAttachment(kind=AttachmentKind.VTR_TEMPLATE, name="p.docx"),),
        )
    )
    await container.suggest_plan()(requirement.id)
    await container.start_run()(
        StartRunCommand(requirement_id=requirement.id, started_by="ana", wait=True)
    )
    await container.requirements.set_retention(
        requirement.id, datetime.now(timezone.utc) - timedelta(days=1)
    )

    result = await retention.purge_expired()
    assert result.requirements == 1
    assert result.runs >= 1
    assert result.events > 0
    assert await container.requirements.get(requirement.id) is None

    async with database.session() as session:
        runs = (await session.execute(sa.select(sa.func.count()).select_from(s.runs))).scalar_one()
        events = (
            await session.execute(sa.select(sa.func.count()).select_from(s.trace_events))
        ).scalar_one()
    assert (runs, events) == (0, 0)

    # La auditoría no se borra con el requerimiento: es el registro de que existió.
    assert await container.audit.list(target=requirement.id)


SECRETO = "ghp_9fK2mQ7xZr4TvB1nLsWc8JdYh3Ee6Aa"


async def test_a_secret_is_never_stored_in_the_clear(database: Database) -> None:
    """Criterio de ORQ-18: ni el volcado de la base ni ninguna columna enseña el valor."""
    from orq.domain.secrets import NewSecret, SecretKind
    from orq.infrastructure.secrets import PostgresSecretVault

    vault = PostgresSecretVault(database, ids=SequentialIdGenerator())
    metadata_secreto = await vault.save(
        NewSecret(
            kind=SecretKind.GIT_TOKEN,
            name="github.com",
            value=SECRETO,
            username="x-access-token",
            created_by="ana",
        ),
        at=START,
    )

    async with database.engine.connect() as connection:
        fila = (await connection.execute(sa.select(s.secrets))).one()
        # Se busca el valor en **todas** las columnas, no solo en la que debería llevarlo.
        volcado = " ".join(str(v) for v in fila._mapping.values())

    assert SECRETO not in volcado, "el secreto aparece en claro en alguna columna"
    assert SECRETO.encode() not in fila.value_enc
    assert fila.hint == "…" + SECRETO[-4:]
    assert metadata_secreto.hint == fila.hint
    # Y se puede recuperar para usarlo: cifrado no es perdido.
    revelado = await vault.reveal(SecretKind.GIT_TOKEN, "github.com", at=START)
    assert revelado is not None and revelado.value == SECRETO
    assert revelado.username == "x-access-token"


async def test_revoking_wipes_the_value_from_the_database(database: Database) -> None:
    from orq.domain.secrets import NewSecret, SecretKind
    from orq.infrastructure.secrets import PostgresSecretVault

    vault = PostgresSecretVault(database, ids=SequentialIdGenerator())
    guardado = await vault.save(
        NewSecret(kind=SecretKind.GIT_TOKEN, name="github.com", value=SECRETO, created_by="ana"),
        at=START,
    )

    revocado = await vault.revoke(guardado.id, at=START, by="ana")

    assert revocado.revoked_at == START
    async with database.engine.connect() as connection:
        fila = (await connection.execute(sa.select(s.secrets))).one()
    assert fila.value_enc == b"", "al revocar, el valor deja de estar ni siquiera cifrado"
    assert await vault.reveal(SecretKind.GIT_TOKEN, "github.com", at=START) is None
    # La ficha se conserva para la auditoría: quién lo puso, cuándo y cuándo se revocó.
    assert fila.created_by == "ana"
    assert fila.hint == "…" + SECRETO[-4:]


async def test_saving_the_same_secret_twice_rotates_the_row(database: Database) -> None:
    from orq.domain.secrets import NewSecret, SecretKind
    from orq.infrastructure.secrets import PostgresSecretVault

    vault = PostgresSecretVault(database, ids=SequentialIdGenerator())
    otro = "pat_5vN8qR2wXy7ZmK4bTgHf1Ss9Dd3Cc0"
    primero = await vault.save(
        NewSecret(kind=SecretKind.GIT_TOKEN, name="github.com", value=SECRETO, created_by="ana"),
        at=START,
    )
    await vault.revoke(primero.id, at=START, by="ana")

    await vault.save(
        NewSecret(kind=SecretKind.GIT_TOKEN, name="github.com", value=otro, created_by="luis"),
        at=START,
    )

    async with database.engine.connect() as connection:
        filas = (await connection.execute(sa.select(s.secrets))).all()
    assert len(filas) == 1, "rotar no puede duplicar la fila"
    activo = await vault.reveal(SecretKind.GIT_TOKEN, "github.com", at=START)
    assert activo is not None and activo.value == otro  # y levanta la revocación
