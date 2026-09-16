"""Identidad: entrar, permisos, caducidad de sesión y qué se guarda de una contraseña (ORQ-5).

Los seis criterios de la tarea se comprueban aquí. El más importante —«sin sesión válida ningún
endpoint devuelve datos de requerimientos»— se comprueba **recorriendo el contrato publicado**, no
una lista escrita a mano: si alguien añade una ruta y se olvida de protegerla, esta prueba salta.
"""
from __future__ import annotations

import logging
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from orq.application.auth import (
    CreateUserCommand,
    LoginCommand,
    UpdateUserCommand,
)
from orq.config import Settings
from orq.domain.identity import (
    ROLE_PERMISSIONS,
    AccountLockedError,
    AuthProvider,
    ForbiddenError,
    InvalidCredentialsError,
    LockPolicy,
    NotAuthenticatedError,
    Permission,
    Role,
    Session,
    SessionPolicy,
    User,
    require,
)
from orq.domain.errors import DomainError
from orq.domain.passwords import (
    hash_password,
    needs_rehash,
    new_session_token,
    token_digest,
    verify_password,
)
from orq.main import create_app

from .conftest import START, logged_client, make_container, make_user, run_async

CLAVE = "una-frase-larga-de-prueba"


def _usuario(**extra) -> User:
    datos = {
        "id": "USR-001",
        "email": "ana@acme.test",
        "name": "Ana Ruiz",
        "role": Role.DESARROLLADOR,
        "created_at": START,
        **extra,
    }
    return User(**datos)


def test_a_user_has_nowhere_to_put_a_password() -> None:
    """Igual que con los secretos: si no cabe en la estructura, no puede filtrarse."""
    user = _usuario()

    # `must_change_password` es una bandera, no una contraseña: se excluye a propósito.
    campos = set(user.__slots__) - {"must_change_password"}
    assert not any("password" in campo or "hash" in campo for campo in campos)
    assert CLAVE not in repr(user)


def test_the_password_is_stored_with_a_modern_hash() -> None:
    guardado = hash_password(CLAVE)

    assert guardado.startswith("scrypt$")
    assert CLAVE not in guardado
    assert verify_password(CLAVE, guardado)
    assert not verify_password(CLAVE + "x", guardado)


def test_two_equal_passwords_produce_different_hashes() -> None:
    """Cada hash lleva su propia sal: dos personas con la misma contraseña no se delatan."""
    assert hash_password(CLAVE) != hash_password(CLAVE)


def test_a_broken_hash_does_not_blow_up() -> None:
    for basura in ("", "no-es-un-hash", "scrypt$mal", "argon2$x$y$z$a$b"):
        assert verify_password(CLAVE, basura) is False


def test_a_hash_with_weaker_parameters_is_marked_for_rehash() -> None:
    assert needs_rehash("scrypt$1024$8$1$c2Fs$aGFzaA")
    assert not needs_rehash(hash_password(CLAVE))


def test_a_short_password_is_refused() -> None:
    with pytest.raises(DomainError) as error:
        from orq.domain.identity import validate_password

        validate_password("corta")

    assert "caracteres" in str(error.value)


def test_the_session_token_is_not_what_gets_stored() -> None:
    token = new_session_token()

    assert len(token) > 30
    assert token_digest(token) != token
    assert len(token_digest(token)) == 64  # sha-256 en hexadecimal


def test_each_role_has_the_permissions_it_should() -> None:
    admin = _usuario(role=Role.ADMINISTRADOR)
    desarrollador = _usuario(role=Role.DESARROLLADOR)
    observador = _usuario(role=Role.OBSERVADOR)

    assert admin.can(Permission.GESTIONAR_USUARIOS)
    assert desarrollador.can(Permission.EJECUTAR)
    assert not desarrollador.can(Permission.APROBAR_CAMBIO_AGENTE)
    assert not desarrollador.can(Permission.GESTIONAR_USUARIOS)
    assert observador.permissions == frozenset()


def test_a_deactivated_account_can_do_nothing() -> None:
    user = _usuario(role=Role.ADMINISTRADOR, active=False)

    assert not user.can(Permission.EJECUTAR)
    with pytest.raises(ForbiddenError):
        require(user, Permission.EJECUTAR)


def test_require_distinguishes_no_session_from_no_permission() -> None:
    with pytest.raises(NotAuthenticatedError):
        require(None, Permission.EJECUTAR)
    with pytest.raises(ForbiddenError):
        require(_usuario(role=Role.OBSERVADOR), Permission.EJECUTAR)


def test_only_the_administrator_manages_users_and_secrets() -> None:
    con_usuarios = {r for r, p in ROLE_PERMISSIONS.items() if Permission.GESTIONAR_USUARIOS in p}

    assert con_usuarios == {Role.ADMINISTRADOR}


def _sesion(**extra) -> Session:
    datos = {"id": "abc", "user_id": "USR-001", "created_at": START, "last_seen_at": START, **extra}
    return Session(**datos)


def test_a_session_expires_by_inactivity() -> None:
    """Criterio de la tarea, y lo que pide HIPAA para un puesto desatendido."""
    politica = SessionPolicy(max_age=timedelta(hours=12), idle_timeout=timedelta(minutes=30))
    sesion = _sesion()

    assert sesion.is_valid(START + timedelta(minutes=29), politica)
    assert not sesion.is_valid(START + timedelta(minutes=31), politica)
    assert sesion.expiry_reason(START + timedelta(minutes=31), politica) == "inactividad"


def test_a_session_also_has_a_hard_limit() -> None:
    """Aunque se use sin parar, a las 12 horas hay que volver a entrar."""
    politica = SessionPolicy(max_age=timedelta(hours=12), idle_timeout=timedelta(minutes=30))
    # Alguien que ha estado usando la aplicación todo el rato.
    sesion = _sesion(last_seen_at=START + timedelta(hours=12))

    assert not sesion.is_valid(START + timedelta(hours=12, seconds=1), politica)
    assert (
        sesion.expiry_reason(START + timedelta(hours=12, seconds=1), politica)
        == "duracion_maxima"
    )


def test_a_closed_session_stops_working() -> None:
    politica = SessionPolicy()
    sesion = _sesion(revoked_at=START)

    assert not sesion.is_valid(START + timedelta(seconds=1), politica)
    assert sesion.expiry_reason(START + timedelta(seconds=1), politica) == "cerrada"


def test_an_account_locks_after_too_many_failures(settings) -> None:
    container = make_container(settings)
    make_user(container, email="ana@acme.test", password=CLAVE)
    login = container.login()

    for _ in range(5):
        with pytest.raises(InvalidCredentialsError):
            run_async(login(LoginCommand(email="ana@acme.test", password="lo-que-sea-largo")))

    # Con la contraseña correcta tampoco entra: la cuenta está bloqueada.
    with pytest.raises(AccountLockedError):
        run_async(login(LoginCommand(email="ana@acme.test", password=CLAVE)))


def test_a_good_login_clears_the_failures(settings) -> None:
    container = make_container(settings)
    make_user(container, email="ana@acme.test", password=CLAVE)
    login = container.login()

    with pytest.raises(InvalidCredentialsError):
        run_async(login(LoginCommand(email="ana@acme.test", password="incorrecta-pero-larga")))
    resultado = run_async(login(LoginCommand(email="ana@acme.test", password=CLAVE)))

    assert resultado.user.failed_attempts == 0
    assert resultado.user.locked_until is None


def test_the_error_is_the_same_whether_the_user_exists_or_not(settings) -> None:
    """Decir «ese correo no existe» le confirma a quien prueba direcciones cuáles son válidas."""
    container = make_container(settings)
    make_user(container, email="ana@acme.test", password=CLAVE)
    login = container.login()

    with pytest.raises(InvalidCredentialsError) as desconocido:
        run_async(login(LoginCommand(email="nadie@acme.test", password=CLAVE)))
    with pytest.raises(InvalidCredentialsError) as incorrecta:
        run_async(login(LoginCommand(email="ana@acme.test", password="otra-cosa-larga")))

    assert str(desconocido.value) == str(incorrecta.value)


def test_a_failed_attempt_never_logs_the_password(settings, caplog) -> None:
    container = make_container(settings)
    make_user(container, email="ana@acme.test", password=CLAVE)

    with caplog.at_level(logging.DEBUG):
        with pytest.raises(InvalidCredentialsError):
            run_async(
                container.login()(
                    LoginCommand(email="ana@acme.test", password="secreta-y-larga-de-verdad")
                )
            )

    registros = "\n".join(r.getMessage() for r in caplog.records)
    assert "secreta-y-larga-de-verdad" not in registros
    assert "ana@acme.test" in registros  # el intento sí queda registrado

    auditoria = run_async(container.audit.list(limit=20))
    texto = "\n".join(f"{e.action.value} {e.target} {e.detail}" for e in auditoria)
    assert "secreta-y-larga-de-verdad" not in texto
    assert "acceso_fallido" in texto


#: Rutas que funcionan sin sesión, y por qué.
PUBLICAS = {
    ("/api/auth/login", "post"),  # es por donde se entra
    ("/api/auth/logout", "post"),  # idempotente: sin cookie no hace nada
    ("/api/auth/me", "get"),  # la aplicación lo llama al cargar para saber si hay sesión
    ("/api/auth/catalog", "get"),  # roles y permisos: no es dato de nadie
    ("/api/health", "get"),  # lo consulta el arranque y la supervisión
}


def test_no_endpoint_returns_data_without_a_session(settings) -> None:
    """Criterio de la tarea, comprobado **recorriendo el contrato**, no una lista a mano.

    Si alguien añade una ruta nueva y se olvida de protegerla, esta prueba lo caza.
    """
    cliente = TestClient(create_app(Settings(database_url="", cors_origins=())))
    esquema = cliente.app.openapi()
    sin_proteger: list[str] = []

    for ruta, metodos in esquema["paths"].items():
        for metodo in metodos:
            if (ruta, metodo) in PUBLICAS or metodo not in {"get", "post", "put", "delete"}:
                continue
            url = ruta.replace("{requirement_id}", "REQ-001").replace("{run_id}", "RUN-001")
            url = url.replace("{secret_id}", "SEC-001").replace("{user_id}", "USR-001")
            respuesta = cliente.request(metodo, url, json={})
            if respuesta.status_code != 401:
                sin_proteger.append(f"{metodo.upper()} {ruta} -> {respuesta.status_code}")

    assert not sin_proteger, "rutas que responden sin sesión: " + ", ".join(sin_proteger)


def test_a_user_without_permission_gets_403_calling_the_api_directly(settings) -> None:
    """Criterio de la tarea: la UI oculta, pero quien bloquea es el servidor."""
    cliente, _ = logged_client(settings, role=Role.OBSERVADOR, email="ojos@acme.test")

    creado = cliente.post("/api/requirements", json={"title": "No debería poder", "phi": "no"})
    secretos = cliente.get("/api/secrets")
    usuarios = cliente.get("/api/users")

    assert creado.status_code == 403
    assert secretos.status_code == 403
    assert usuarios.status_code == 403
    assert "permiso" in creado.json()["message"]
    # Y sí puede leer: el observador está para mirar.
    assert cliente.get("/api/requirements").status_code == 200


def test_the_auditor_is_the_authenticated_user_not_one_chosen_by_the_client(settings) -> None:
    """Criterio de la tarea: el actor sale de la sesión."""
    cliente, container = logged_client(settings, email="lucia@acme.test")

    creado = cliente.post(
        "/api/requirements",
        json={"title": "Conciliación", "phi": "no", "owner": "otro@acme.test"},
    )

    assert creado.status_code == 201
    assert creado.json()["owner"] == "lucia@acme.test", "el owner del cuerpo se ignoró, bien"
    entradas = run_async(container.audit.list(limit=50))
    creacion = next(e for e in entradas if e.action.value == "requerimiento_creado")
    assert creacion.actor == "lucia@acme.test"


def test_logging_in_and_out_works_over_http(settings) -> None:
    cliente, _ = logged_client(settings)

    yo = cliente.get("/api/auth/me").json()
    assert yo["authenticated"] is True
    assert yo["user"]["email"] == "ana@acme.test"
    assert "gestionar_usuarios" in yo["user"]["permissions"]

    assert cliente.post("/api/auth/logout").status_code == 204
    assert cliente.get("/api/auth/me").json()["authenticated"] is False
    assert cliente.get("/api/requirements").status_code == 401


def test_the_session_cookie_is_not_readable_from_javascript(settings) -> None:
    container = make_container(settings)
    make_user(container)
    cliente = TestClient(create_app(settings, container=container))

    respuesta = cliente.post(
        "/api/auth/login",
        json={"email": "ana@acme.test", "password": "contrasena-de-prueba-larga"},
    )

    cookie = respuesta.headers["set-cookie"].lower()
    assert "httponly" in cookie  # un script inyectado no puede leer el testigo
    assert "samesite=lax" in cookie  # no viaja desde otro sitio: corta el CSRF de formulario
    # Y el testigo no aparece en el cuerpo: solo va en la cookie.
    assert "token" not in respuesta.json()


def test_a_wrong_password_over_http_says_nothing_useful(settings) -> None:
    container = make_container(settings)
    make_user(container)
    cliente = TestClient(create_app(settings, container=container))

    respuesta = cliente.post(
        "/api/auth/login", json={"email": "ana@acme.test", "password": "no-es-la-buena"}
    )

    assert respuesta.status_code == 401
    assert respuesta.json()["message"] == "Correo o contraseña incorrectos."
    assert "set-cookie" not in respuesta.headers


def test_an_expired_session_says_why(settings) -> None:
    """La UI necesita distinguir «caducó por inactividad» de «no has entrado»."""
    settings_corta = Settings(
        ai_provider=settings.ai_provider,
        cors_origins=(),
        session_idle_minutes=0,
    )
    container = make_container(settings_corta)
    make_user(container)
    cliente = TestClient(create_app(settings_corta, container=container))
    cliente.post(
        "/api/auth/login",
        json={"email": "ana@acme.test", "password": "contrasena-de-prueba-larga"},
    )

    respuesta = cliente.get("/api/requirements")

    assert respuesta.status_code == 401
    assert respuesta.headers.get("X-Sesion-Caducada") == "inactividad"
    assert "inactividad" in respuesta.json()["message"]


def test_deactivating_someone_closes_their_sessions(settings) -> None:
    """Si no, quitarle el acceso a alguien no surtiría efecto hasta que cerrara sesión."""
    container = make_container(settings)
    admin = make_user(container, email="jefa@acme.test", role=Role.ADMINISTRADOR)
    otra, _ = logged_client(settings, container, email="ana@acme.test", role=Role.DESARROLLADOR)
    assert otra.get("/api/requirements").status_code == 200

    persona = run_async(container.users.by_email("ana@acme.test"))
    run_async(container.update_user()(UpdateUserCommand(user_id=persona.id, active=False), by=admin))

    assert otra.get("/api/requirements").status_code == 401


def test_changing_a_role_also_closes_their_sessions(settings) -> None:
    container = make_container(settings)
    admin = make_user(container, email="jefa@acme.test", role=Role.ADMINISTRADOR)
    otra, _ = logged_client(settings, container, email="ana@acme.test", role=Role.DESARROLLADOR)

    persona = run_async(container.users.by_email("ana@acme.test"))
    run_async(
        container.update_user()(
            UpdateUserCommand(user_id=persona.id, role=Role.OBSERVADOR), by=admin
        )
    )

    assert otra.get("/api/requirements").status_code == 401


def test_you_cannot_deactivate_yourself(settings) -> None:
    container = make_container(settings)
    admin = make_user(container, email="jefa@acme.test", role=Role.ADMINISTRADOR)

    with pytest.raises(DomainError) as error:
        run_async(
            container.update_user()(UpdateUserCommand(user_id=admin.id, active=False), by=admin)
        )

    assert "propia cuenta" in str(error.value)


def test_creating_a_user_needs_the_permission(settings) -> None:
    container = make_container(settings)
    desarrollador = make_user(container, email="dev@acme.test", role=Role.DESARROLLADOR)

    with pytest.raises(ForbiddenError):
        run_async(
            container.create_user()(
                CreateUserCommand(
                    email="nueva@acme.test",
                    name="Nueva",
                    role=Role.QA,
                    password="otra-frase-larga-de-prueba",
                ),
                by=desarrollador,
            )
        )


def test_two_accounts_cannot_share_an_email(settings) -> None:
    container = make_container(settings)
    make_user(container, email="ana@acme.test")

    with pytest.raises(DomainError) as error:
        make_user(container, email="ANA@acme.test")  # el correo se normaliza

    assert "Ya existe" in str(error.value)


def test_an_oidc_user_has_no_local_password(settings) -> None:
    """Preparado para el inicio de sesión corporativo: la identidad no se ata a una contraseña."""
    container = make_container(settings)

    user = run_async(
        container.create_user().unchecked(
            CreateUserCommand(
                email="corporativa@acme.test",
                name="Cuenta corporativa",
                role=Role.QA,
                provider=AuthProvider.OIDC,
            )
        )
    )

    assert user.provider is AuthProvider.OIDC
    assert run_async(container.users.credential_of(user.id)) is None
    # Y no puede entrar con contraseña: no tiene ninguna.
    with pytest.raises(InvalidCredentialsError):
        run_async(
            container.login()(LoginCommand(email="corporativa@acme.test", password=CLAVE))
        )


def test_the_first_account_is_seeded_on_startup(settings) -> None:
    """Sin esto no habría forma de entrar la primera vez."""
    arranque = Settings(
        ai_provider=settings.ai_provider,
        cors_origins=(),
        admin_email="jefa@acme.test",
        admin_password="contrasena-inicial-larga",
    )
    container = make_container(arranque)

    run_async(container.startup())

    admin = run_async(container.users.by_email("jefa@acme.test"))
    assert admin is not None
    assert admin.role is Role.ADMINISTRADOR
    # Viene de una variable de entorno, que acaba en el historial del terminal: se cambia al entrar.
    assert admin.must_change_password is True

    # Y no se duplica al reiniciar.
    run_async(container.startup())
    assert run_async(container.users.count()) == 1


def test_changing_the_password_closes_the_other_sessions(settings) -> None:
    container = make_container(settings)
    make_user(container, email="ana@acme.test", password=CLAVE)
    primera, _ = logged_client(settings, container, email="ana@acme.test", password=CLAVE)
    segunda = TestClient(create_app(settings, container=container))
    segunda.post("/api/auth/login", json={"email": "ana@acme.test", "password": CLAVE})
    assert segunda.get("/api/requirements").status_code == 200

    cambio = primera.put(
        "/api/auth/password", json={"current": CLAVE, "new": "otra-frase-todavia-mas-larga"}
    )

    assert cambio.status_code == 204
    assert primera.get("/api/requirements").status_code == 200, "la sesión propia sigue viva"
    assert segunda.get("/api/requirements").status_code == 401, "las demás se cerraron"
