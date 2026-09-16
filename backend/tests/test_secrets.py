"""Bóveda de secretos (ORQ-18): se escribe, se usa y no se lee nunca.

Los cuatro criterios de la tarea se comprueban aquí, y el tercero —«buscar el valor en los logs de
una ejecución completa no arroja resultados»— se comprueba **de verdad**: se captura todo lo que
el proceso escribe en el log durante una revisión entera y se busca el token dentro.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from orq.application.use_cases import (
    CreateRequirementCommand,
    NewAttachment,
    SaveSecretCommand,
    StartRunCommand,
)
from orq.domain.audit import AuditAction
from orq.domain.enums import AttachmentKind, PhiClassification, RunStatus
from orq.domain.errors import DomainError, NotFoundError
from orq.domain.secrets import (
    ORGANIZATION,
    NewSecret,
    SecretKind,
    SecretMetadata,
    SecretValue,
    hint_of,
)
from orq.infrastructure.git.credentials import ConfiguredCredentialStore
from orq.infrastructure.secrets import (
    InMemorySecretVault,
    SecretScrubber,
    VaultCredentialStore,
)
from orq.main import create_app

from .conftest import START, logged_client, make_container, run_async

TOKEN = "ghp_9fK2mQ7xZr4TvB1nLsWc8JdYh3Ee6Aa"
OTRO = "pat_5vN8qR2wXy7ZmK4bTgHf1Ss9Dd3Cc0"


@pytest.fixture
def vault() -> InMemorySecretVault:
    return InMemorySecretVault()


def _guardar(vault: InMemorySecretVault, **extra) -> SecretMetadata:
    datos = {
        "kind": SecretKind.GIT_TOKEN,
        "name": "github.com",
        "value": TOKEN,
        "created_by": "ana",
        **extra,
    }
    return run_async(vault.save(NewSecret(**datos), at=START))


def test_the_metadata_has_nowhere_to_put_the_value(vault: InMemorySecretVault) -> None:
    """La garantía es estructural: no hay campo, así que no puede filtrarse por descuido."""
    metadata = _guardar(vault)

    assert TOKEN not in str(metadata)
    assert TOKEN not in repr(metadata)
    assert not any("value" in campo or "token" in campo for campo in metadata.__slots__)
    assert metadata.hint == "…" + TOKEN[-4:]


def test_a_secret_value_never_prints_itself() -> None:
    metadata = SecretMetadata(
        id="SEC-001",
        kind=SecretKind.GIT_TOKEN,
        name="github.com",
        scope=ORGANIZATION,
        created_by="ana",
        created_at=START,
        updated_at=START,
    )
    secreto = SecretValue(metadata=metadata, value=TOKEN)

    assert TOKEN not in repr(secreto)
    assert TOKEN not in str(secreto)
    assert TOKEN not in f"{secreto}"
    assert "***" in repr(secreto)


def test_the_hint_does_not_give_the_secret_away() -> None:
    assert hint_of(TOKEN) == "…" + TOKEN[-4:]
    assert len(hint_of(TOKEN)) == 5
    # Uno muy corto no enseña ni eso.
    assert hint_of("corto") == "…"


def test_saving_twice_rotates_instead_of_duplicating(vault: InMemorySecretVault) -> None:
    primero = _guardar(vault)
    segundo = _guardar(vault, value=OTRO)

    assert segundo.id == primero.id
    assert segundo.created_at == primero.created_at  # quién lo creó y cuándo se conserva
    assert segundo.hint == "…" + OTRO[-4:]
    assert len(run_async(vault.list())) == 1

    activo = run_async(vault.reveal(SecretKind.GIT_TOKEN, "github.com", at=START))
    assert activo is not None and activo.value == OTRO


def test_a_revoked_secret_stops_working_immediately(vault: InMemorySecretVault) -> None:
    """Criterio de la tarea: revocar corta el uso en ejecuciones nuevas."""
    metadata = _guardar(vault)
    assert run_async(vault.reveal(SecretKind.GIT_TOKEN, "github.com", at=START)) is not None

    revocado = run_async(vault.revoke(metadata.id, at=START, by="ana"))

    assert revocado.revoked_at == START
    assert revocado.status(START) == "revocado"
    assert run_async(vault.reveal(SecretKind.GIT_TOKEN, "github.com", at=START)) is None


def test_an_expired_secret_stops_working_on_its_own(vault: InMemorySecretVault) -> None:
    metadata = _guardar(vault, expires_at=START + timedelta(days=1))

    assert metadata.is_active(START)
    assert run_async(vault.reveal(SecretKind.GIT_TOKEN, "github.com", at=START)) is not None

    despues = START + timedelta(days=2)
    assert not metadata.is_active(despues)
    assert metadata.status(despues) == "caducado"
    assert run_async(vault.reveal(SecretKind.GIT_TOKEN, "github.com", at=despues)) is None


def test_saving_again_lifts_a_revocation(vault: InMemorySecretVault) -> None:
    metadata = _guardar(vault)
    run_async(vault.revoke(metadata.id, at=START, by="ana"))

    _guardar(vault, value=OTRO)

    activo = run_async(vault.reveal(SecretKind.GIT_TOKEN, "github.com", at=START))
    assert activo is not None and activo.value == OTRO


def test_revoking_something_that_does_not_exist_says_so(vault: InMemorySecretVault) -> None:
    with pytest.raises(NotFoundError):
        run_async(vault.revoke("SEC-999", at=START, by="ana"))


def test_a_secret_that_is_too_short_is_refused() -> None:
    with pytest.raises(DomainError) as error:
        NewSecret(kind=SecretKind.GIT_TOKEN, name="github.com", value="corto").validated()

    assert "corto" in str(error.value)


def test_using_a_secret_is_counted(vault: InMemorySecretVault) -> None:
    _guardar(vault)

    run_async(vault.reveal(SecretKind.GIT_TOKEN, "github.com", at=START))
    segundo = run_async(vault.reveal(SecretKind.GIT_TOKEN, "github.com", at=START))

    assert segundo is not None
    assert segundo.metadata.uses == 2
    assert segundo.metadata.last_used_at == START


def test_a_requirement_secret_wins_over_the_organization_one(vault: InMemorySecretVault) -> None:
    """Un requerimiento puede usar el token de otro cliente sin tocar el de la organización."""
    _guardar(vault)
    _guardar(vault, value=OTRO, scope="REQ-001")

    organizacion = run_async(vault.reveal(SecretKind.GIT_TOKEN, "github.com", at=START))
    requerimiento = run_async(
        vault.reveal(SecretKind.GIT_TOKEN, "github.com", scope="REQ-001", at=START)
    )

    assert organizacion is not None and organizacion.value == TOKEN
    assert requerimiento is not None and requerimiento.value == OTRO


def test_the_scrubber_masks_every_known_value() -> None:
    scrubber = SecretScrubber()
    scrubber.remember(TOKEN)

    limpio = scrubber.scrub(f"fatal: no se pudo clonar con el token {TOKEN} en github.com")

    assert TOKEN not in limpio
    assert "«secreto»" in limpio
    assert "github.com" in limpio  # lo demás se conserva: el mensaje sigue sirviendo


def test_the_scrubber_masks_the_longest_value_first() -> None:
    """Si un secreto contiene a otro, sustituir antes el corto dejaría media cadena a la vista."""
    scrubber = SecretScrubber()
    corto = "abcdefgh"
    largo = corto + "ijklmnop"
    scrubber.remember(corto, largo)

    limpio = scrubber.scrub(f"valor={largo}")

    assert corto not in limpio
    assert largo not in limpio


def test_the_scrubber_forgets_a_revoked_value() -> None:
    scrubber = SecretScrubber()
    vault = InMemorySecretVault(scrubber=scrubber)
    metadata = _guardar(vault)
    assert scrubber.contains_secret(TOKEN)

    run_async(vault.revoke(metadata.id, at=START, by="ana"))

    assert not scrubber.contains_secret(TOKEN)


def test_the_logging_filter_masks_the_value(caplog: pytest.LogCaptureFixture) -> None:
    scrubber = SecretScrubber()
    scrubber.remember(TOKEN)
    logger = logging.getLogger("prueba.secretos")
    filtro = scrubber.logging_filter()
    logger.addFilter(filtro)
    try:
        with caplog.at_level(logging.INFO, logger="prueba.secretos"):
            logger.info("clonando con %s", TOKEN)
            logger.warning("falló: token=%s", TOKEN)
    finally:
        logger.removeFilter(filtro)

    texto = "\n".join(r.getMessage() for r in caplog.records)
    assert TOKEN not in texto
    assert texto.count("«secreto»") == 2


def test_git_credentials_come_from_the_vault(vault: InMemorySecretVault) -> None:
    _guardar(vault, username="x-access-token")
    store = VaultCredentialStore(vault)

    credencial = run_async(store.git_credential("github.com"))

    assert credencial is not None
    assert credencial.token == TOKEN
    assert TOKEN not in repr(credencial)


def test_the_configuration_is_only_a_fallback(vault: InMemorySecretVault) -> None:
    store = VaultCredentialStore(
        vault, fallback=ConfiguredCredentialStore(f"github.com={OTRO}")
    )

    # Sin nada en la bóveda, se usa la configuración.
    assert run_async(store.git_credential("github.com")).token == OTRO

    # En cuanto se guarda en la bóveda, manda la bóveda.
    _guardar(vault)
    assert run_async(store.git_credential("github.com")).token == TOKEN


def test_a_revoked_token_stops_being_handed_out(vault: InMemorySecretVault) -> None:
    metadata = _guardar(vault)
    store = VaultCredentialStore(vault)
    assert run_async(store.git_credential("github.com")) is not None

    run_async(vault.revoke(metadata.id, at=START, by="ana"))

    assert run_async(store.git_credential("github.com")) is None


def test_using_a_credential_is_audited_without_the_value(settings) -> None:
    container = make_container(settings)
    vault = InMemorySecretVault()
    _guardar(vault)
    store = VaultCredentialStore(vault, audit=container.audit)

    run_async(store.git_credential("github.com"))

    entradas = run_async(container.audit.list(limit=50))
    usos = [e for e in entradas if e.action is AuditAction.SECRETO_USADO]
    assert usos, "el uso de una credencial tiene que quedar registrado"
    assert "github.com" in usos[0].detail
    assert TOKEN not in usos[0].detail


@pytest.fixture
def client(settings) -> TestClient:
    """Cliente con sesión de administrador: gestionar la bóveda exige permiso (ORQ-5)."""
    container = make_container(settings)
    container.vault = InMemorySecretVault(scrubber=container.scrubber)
    cliente, _ = logged_client(settings, container)
    return cliente


def test_no_endpoint_ever_returns_the_value(client: TestClient) -> None:
    """Criterio de la tarea: ni siquiera para un administrador."""
    creado = client.post(
        "/api/secrets",
        json={"kind": "git_token", "name": "GitHub.com", "value": TOKEN},
    )
    assert creado.status_code == 201, creado.text
    secreto = creado.json()

    listado = client.get("/api/secrets")
    detalle = client.delete(f"/api/secrets/{secreto['id']}")

    for respuesta in (creado, listado, detalle):
        assert TOKEN not in respuesta.text, f"{respuesta.url} devolvió el valor"
    assert secreto["hint"] == "…" + TOKEN[-4:]
    assert secreto["name"] == "github.com"  # se normaliza a minúsculas
    assert secreto["status"] == "activo"
    assert listado.json()["items"][0]["status"] == "activo"
    assert detalle.json()["status"] == "revocado"


def test_there_is_no_route_that_reads_a_secret(client: TestClient) -> None:
    """Si alguien añadiera un `GET /secrets/{id}/value`, esta prueba lo caza.

    Se mira el contrato publicado, que es lo que ve quien usa la API, no la tabla interna de
    rutas: así también salta si el valor apareciera en la respuesta de cualquier otro endpoint.
    """
    esquema = client.app.openapi()

    rutas = {
        (ruta, tuple(sorted(metodos)))
        for ruta, metodos in esquema["paths"].items()
        if ruta.startswith("/api/secrets")
    }
    assert rutas == {
        ("/api/secrets", ("get", "post")),
        ("/api/secrets/{secret_id}", ("delete",)),
    }

    # Y el modelo de salida no tiene ningún campo donde quepa el valor.
    campos = set(esquema["components"]["schemas"]["SecretOut"]["properties"])
    assert not campos & {"value", "token", "password", "secret"}
    assert "hint" in campos


def test_a_short_value_is_refused_by_the_api(client: TestClient) -> None:
    respuesta = client.post(
        "/api/secrets", json={"kind": "git_token", "name": "github.com", "value": "x"}
    )

    assert respuesta.status_code == 422


def test_saving_is_audited_without_the_value(client: TestClient) -> None:
    client.post(
        "/api/secrets",
        json={"kind": "git_token", "name": "github.com", "value": TOKEN},
    )

    auditoria = client.get("/api/audit").text

    assert TOKEN not in auditoria
    assert "secreto_guardado" in auditoria


def test_a_whole_run_never_writes_the_secret_to_the_log(settings, caplog) -> None:
    """Criterio de la tarea: buscar el valor en los logs de una ejecución completa no da nada.

    Se captura **todo** lo que el proceso escribe durante una revisión entera, no solo lo del
    código propio: el filtro va en el logger raíz justamente para cubrir a las bibliotecas.
    """
    container = make_container(settings)
    scrubber = container.scrubber or SecretScrubber()
    container.scrubber = scrubber
    container.vault = InMemorySecretVault(scrubber=scrubber)

    run_async(
        container.save_secret()(
            SaveSecretCommand(
                kind=SecretKind.GIT_TOKEN, name="github.com", value=TOKEN, by="ana"
            )
        )
    )
    filtro = scrubber.install(logging.getLogger())
    try:
        with caplog.at_level(logging.DEBUG):
            # Alguien pega el token donde no debe: en la descripción del requerimiento.
            requirement = run_async(
                container.create_requirement()(
                    CreateRequirementCommand(
                        title="Conectar el repositorio",
                        description=f"Usar el token {TOKEN} para clonar.",
                        owner="ana",
                        phi=PhiClassification.NO,
                        attachments=(
                            NewAttachment(kind=AttachmentKind.REPO, name="acme/portal"),
                            NewAttachment(kind=AttachmentKind.VTR_TEMPLATE, name="VTR.docx"),
                        ),
                    )
                )
            )
            run_async(container.suggest_plan()(requirement.id))
            # Y algo del proceso lo registra, como haría una biblioteca de terceros.
            logging.getLogger("terceros.git").warning("clonando con %s", TOKEN)
            run = run_async(
                container.start_run()(
                    StartRunCommand(requirement_id=requirement.id, started_by="ana", wait=True)
                )
            )
    finally:
        logging.getLogger().removeFilter(filtro)

    assert run.status is RunStatus.COMPLETADA

    registros = "\n".join(r.getMessage() for r in caplog.records)
    assert TOKEN not in registros, "el token apareció en el log de la ejecución"

    eventos = run_async(container.runs.events(run.id))
    traza = "\n".join(f"{e.title} {e.detail} {e.data}" for e in eventos)
    assert TOKEN not in traza, "el token apareció en la traza"

    auditoria = "\n".join(
        f"{e.action} {e.target} {e.detail}" for e in run_async(container.audit.list(limit=500))
    )
    assert TOKEN not in auditoria, "el token apareció en la auditoría"


def test_saving_a_secret_does_not_count_as_using_it(settings) -> None:
    """Guardar no es usar: si contara, el «último uso» del panel mentiría desde el minuto uno."""
    container = make_container(settings)
    container.vault = InMemorySecretVault()

    guardado = run_async(
        container.save_secret()(
            SaveSecretCommand(kind=SecretKind.GIT_TOKEN, name="github.com", value=TOKEN, by="ana")
        )
    )
    # Y rotarlo tampoco.
    rotado = run_async(
        container.save_secret()(
            SaveSecretCommand(kind=SecretKind.GIT_TOKEN, name="github.com", value=OTRO, by="ana")
        )
    )

    assert guardado.uses == 0
    assert guardado.last_used_at is None
    assert rotado.uses == 0

    entradas = run_async(container.audit.list(limit=50))
    acciones = [e.detail for e in entradas if e.action is AuditAction.SECRETO_GUARDADO]
    assert acciones[0].startswith("guardado")
    assert acciones[1].startswith("rotado")
