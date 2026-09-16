"""Casos de uso de identidad: entrar, salir, quién soy y gestionar personas."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

from ..domain.audit import AuditAction
from ..domain.errors import DomainError, NotFoundError
from ..domain.identity import (
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
    normalize_email,
    require,
    validate_password,
)
from ..domain.passwords import (
    hash_password,
    needs_rehash,
    new_session_token,
    token_digest,
    verify_password,
)
from .ports import AuditLog, Clock, IdGenerator, SessionRepository, UserRepository

log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class LoginCommand:
    email: str
    password: str
    user_agent: str = ""
    ip: str = ""


@dataclass(frozen=True, slots=True)
class LoginResult:
    """Lo que necesita la API: a quién dejó entrar y qué testigo poner en la cookie."""

    user: User
    token: str
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class CreateUserCommand:
    email: str
    name: str
    role: Role
    password: str = ""
    provider: AuthProvider = AuthProvider.LOCAL
    must_change_password: bool = False


@dataclass(frozen=True, slots=True)
class UpdateUserCommand:
    user_id: str
    role: Role | None = None
    active: bool | None = None
    name: str | None = None


async def _record(audit: AuditLog | None, **entry) -> None:
    if audit is None:
        return
    try:
        await audit.append(**entry)
    except Exception:  # pragma: no cover - depende de la base
        log.exception("no se pudo registrar en auditoría: %s", entry.get("action"))


class Login:
    """Comprueba credenciales y abre sesión."""

    def __init__(
        self,
        *,
        users: UserRepository,
        sessions: SessionRepository,
        clock: Clock,
        audit: AuditLog | None = None,
        lock_policy: LockPolicy | None = None,
        session_policy: SessionPolicy | None = None,
    ) -> None:
        self._users = users
        self._sessions = sessions
        self._clock = clock
        self._audit = audit
        self._lock = lock_policy or LockPolicy()
        self._policy = session_policy or SessionPolicy()

    async def __call__(self, command: LoginCommand) -> LoginResult:
        now = self._clock.now()
        email = normalize_email(command.email)
        user = await self._users.by_email(email)

        if user is None:
            # Se gasta el mismo tiempo que con un usuario real: si no, el tiempo de respuesta
            # diría qué correos existen.
            verify_password(command.password, hash_password("no-existe-este-usuario"))
            await self._failed(email, "usuario desconocido")
            raise InvalidCredentialsError()

        if user.is_locked(now):
            await self._failed(email, "cuenta bloqueada", user_id=user.id)
            raise AccountLockedError(
                "La cuenta está bloqueada por varios intentos fallidos. "
                "Vuelve a intentarlo más tarde o pide al administrador que la desbloquee."
            )

        if not user.active:
            await self._failed(email, "cuenta desactivada", user_id=user.id)
            raise InvalidCredentialsError()

        guardado = await self._users.credential_of(user.id)
        if not guardado or not verify_password(command.password, guardado):
            await self._users.save(user.with_failure(now, policy=self._lock))
            await self._failed(email, "contraseña incorrecta", user_id=user.id)
            raise InvalidCredentialsError()

        # Si los parámetros de scrypt subieron desde que se guardó, se aprovecha que ahora sí se
        # tiene la contraseña en claro para volver a cifrarla con los nuevos.
        if needs_rehash(guardado):
            await self._users.set_password(user.id, hash_password(command.password))

        entrado = user.with_login(now)
        await self._users.save(entrado)

        token = new_session_token()
        session = Session(
            id=token_digest(token),
            user_id=user.id,
            created_at=now,
            last_seen_at=now,
            user_agent=command.user_agent,
            ip=command.ip,
        )
        await self._sessions.add(session)
        await _record(
            self._audit,
            at=now,
            actor=user.email,
            action=AuditAction.SESION_INICIADA,
            target=user.id,
            detail=f"rol {entrado.role.value}",
        )
        return LoginResult(
            user=entrado, token=token, expires_at=session.expires_at(self._policy)
        )

    async def _failed(self, email: str, reason: str, *, user_id: str = "") -> None:
        """Deja constancia del intento. Nunca se registra la contraseña, ni siquiera su longitud."""
        log.warning("intento de acceso fallido para %s: %s", email, reason)
        await _record(
            self._audit,
            at=self._clock.now(),
            actor=email,
            action=AuditAction.ACCESO_FALLIDO,
            target=user_id or email,
            detail=reason,
        )


class Logout:
    def __init__(
        self,
        *,
        sessions: SessionRepository,
        clock: Clock,
        audit: AuditLog | None = None,
    ) -> None:
        self._sessions = sessions
        self._clock = clock
        self._audit = audit

    async def __call__(self, token: str, *, user: User | None = None) -> None:
        if not token:
            return
        now = self._clock.now()
        await self._sessions.revoke(token_digest(token), at=now)
        if user is not None:
            await _record(
                self._audit,
                at=now,
                actor=user.email,
                action=AuditAction.SESION_CERRADA,
                target=user.id,
            )


@dataclass(frozen=True, slots=True)
class Authenticated:
    """Resultado de resolver una cookie: quién es y qué le pasó a su sesión."""

    user: User | None = None
    session: Session | None = None
    expired_reason: str = ""


class ResolveSession:
    """Traduce el testigo de la cookie en un usuario. Es lo que llama cada petición."""

    def __init__(
        self,
        *,
        users: UserRepository,
        sessions: SessionRepository,
        clock: Clock,
        policy: SessionPolicy | None = None,
        #: Refrescar `last_seen_at` en cada petición sería una escritura por lectura.
        touch_every: timedelta = timedelta(minutes=1),
    ) -> None:
        self._users = users
        self._sessions = sessions
        self._clock = clock
        self._policy = policy or SessionPolicy()
        self._touch_every = touch_every

    async def __call__(self, token: str) -> Authenticated:
        if not token:
            return Authenticated()
        session = await self._sessions.get(token_digest(token))
        if session is None:
            return Authenticated()

        now = self._clock.now()
        if not session.is_valid(now, self._policy):
            return Authenticated(expired_reason=session.expiry_reason(now, self._policy))

        user = await self._users.get(session.user_id)
        if user is None or not user.active:
            await self._sessions.revoke(session.id, at=now)
            return Authenticated(expired_reason="cuenta_desactivada")

        if now - session.last_seen_at >= self._touch_every:
            session = session.seen(now)
            await self._sessions.save(session)
        return Authenticated(user=user, session=session)


class CreateUser:
    """Alta de una persona. Solo para quien tenga el permiso de gestionar usuarios."""

    def __init__(
        self,
        *,
        users: UserRepository,
        clock: Clock,
        ids: IdGenerator,
        audit: AuditLog | None = None,
    ) -> None:
        self._users = users
        self._clock = clock
        self._ids = ids
        self._audit = audit

    async def __call__(self, command: CreateUserCommand, *, by: User | None = None) -> User:
        require(by, Permission.GESTIONAR_USUARIOS)
        return await self.unchecked(command, by=by)

    async def unchecked(self, command: CreateUserCommand, *, by: User | None = None) -> User:
        """Sin comprobar permisos: solo para sembrar la primera cuenta al arrancar."""
        email = normalize_email(command.email)
        if not email or "@" not in email:
            raise DomainError("Hace falta un correo válido.")
        if await self._users.by_email(email) is not None:
            raise DomainError(f"Ya existe una cuenta con el correo {email}.")

        password_hash: str | None = None
        if command.provider is AuthProvider.LOCAL:
            password_hash = hash_password(validate_password(command.password))

        now = self._clock.now()
        user = User(
            id=await self._ids.new_id("USR"),
            email=email,
            name=command.name.strip() or email.split("@")[0],
            role=command.role,
            created_at=now,
            provider=command.provider,
            must_change_password=command.must_change_password,
        )
        await self._users.add(user, password_hash=password_hash)
        await _record(
            self._audit,
            at=now,
            actor=by.email if by else "sistema",
            action=AuditAction.USUARIO_CREADO,
            target=user.id,
            detail=f"{user.email} · rol {user.role.value}",
        )
        return user


class ListUsers:
    def __init__(self, *, users: UserRepository) -> None:
        self._users = users

    async def __call__(self, *, by: User | None = None) -> list[User]:
        require(by, Permission.GESTIONAR_USUARIOS)
        return await self._users.list()


class UpdateUser:
    """Cambia el rol, el nombre o si la cuenta está activa."""

    def __init__(
        self,
        *,
        users: UserRepository,
        sessions: SessionRepository,
        clock: Clock,
        audit: AuditLog | None = None,
    ) -> None:
        self._users = users
        self._sessions = sessions
        self._clock = clock
        self._audit = audit

    async def __call__(self, command: UpdateUserCommand, *, by: User | None = None) -> User:
        require(by, Permission.GESTIONAR_USUARIOS)
        user = await self._users.get(command.user_id)
        if user is None:
            raise NotFoundError(f"No existe el usuario {command.user_id}.")
        if by is not None and user.id == by.id and command.active is False:
            raise DomainError("No puedes desactivar tu propia cuenta.")

        from dataclasses import replace

        actualizado = replace(
            user,
            role=command.role if command.role is not None else user.role,
            active=command.active if command.active is not None else user.active,
            name=command.name.strip() if command.name else user.name,
            # Reactivar una cuenta la desbloquea: si no, el administrador la activa y la persona
            # sigue sin poder entrar sin saber por qué.
            failed_attempts=0 if command.active else user.failed_attempts,
            locked_until=None if command.active else user.locked_until,
        )
        await self._users.save(actualizado)

        now = self._clock.now()
        # Si no se cortan las sesiones abiertas, quitarle el acceso a alguien no surte efecto
        # hasta que cierre sesión por su cuenta.
        if command.active is False or (command.role is not None and command.role != user.role):
            cerradas = await self._sessions.revoke_all_for(user.id, at=now)
            if cerradas:
                log.info("se cerraron %s sesión(es) de %s", cerradas, user.email)

        await _record(
            self._audit,
            at=now,
            actor=by.email if by else "sistema",
            action=AuditAction.USUARIO_ACTUALIZADO,
            target=user.id,
            detail=f"rol {actualizado.role.value} · {'activa' if actualizado.active else 'desactivada'}",
        )
        return actualizado


class ChangePassword:
    """Cambio de contraseña de la propia cuenta."""

    def __init__(
        self,
        *,
        users: UserRepository,
        sessions: SessionRepository,
        clock: Clock,
        audit: AuditLog | None = None,
    ) -> None:
        self._users = users
        self._sessions = sessions
        self._clock = clock
        self._audit = audit

    async def __call__(
        self, *, user: User | None, current: str, new: str, keep_session: str = ""
    ) -> None:
        if user is None:
            raise NotAuthenticatedError("Hace falta iniciar sesión.")
        if user.provider is not AuthProvider.LOCAL:
            raise ForbiddenError(
                "Esta cuenta entra con el inicio de sesión corporativo: la contraseña se cambia allí."
            )
        guardado = await self._users.credential_of(user.id)
        if not guardado or not verify_password(current, guardado):
            raise InvalidCredentialsError("La contraseña actual no es correcta.")
        if current == new:
            raise DomainError("La contraseña nueva tiene que ser distinta de la actual.")

        await self._users.set_password(user.id, hash_password(validate_password(new)))
        from dataclasses import replace

        await self._users.save(replace(user, must_change_password=False))

        now = self._clock.now()
        # Se cierran las demás sesiones: es lo que se espera si se cambia porque alguien la vio.
        await self._sessions.revoke_all_for(user.id, at=now)
        if keep_session:
            sesion = await self._sessions.get(token_digest(keep_session))
            if sesion is not None:
                from dataclasses import replace as _replace

                await self._sessions.save(_replace(sesion, revoked_at=None))

        await _record(
            self._audit,
            at=now,
            actor=user.email,
            action=AuditAction.CONTRASENA_CAMBIADA,
            target=user.id,
        )
