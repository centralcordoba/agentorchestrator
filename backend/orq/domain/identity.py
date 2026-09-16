"""Identidad: quién es quién, qué puede hacer y cuándo caduca su sesión."""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from enum import Enum

from .errors import DomainError


class Permission(str, Enum):
    """Lo que se puede hacer. Los valores son los del prototipo, para no traducir nada."""

    CREAR_REQUERIMIENTO = "crear_requerimiento"
    EJECUTAR = "ejecutar"
    SOLICITAR_CAMBIO_AGENTE = "solicitar_cambio_agente"
    APROBAR_CAMBIO_AGENTE = "aprobar_cambio_agente"
    FIRMAR_DICTAMEN = "firmar_dictamen"
    VER_AUDITORIA = "ver_auditoria"
    GESTIONAR_SECRETOS = "gestionar_secretos"
    GESTIONAR_USUARIOS = "gestionar_usuarios"


PERMISSION_LABELS: dict[Permission, str] = {
    Permission.CREAR_REQUERIMIENTO: "Crear requerimientos",
    Permission.EJECUTAR: "Ejecutar revisiones",
    Permission.SOLICITAR_CAMBIO_AGENTE: "Solicitar cambios de agentes",
    Permission.APROBAR_CAMBIO_AGENTE: "Aprobar cambios de agentes",
    Permission.FIRMAR_DICTAMEN: "Firmar dictámenes",
    Permission.VER_AUDITORIA: "Ver auditoría",
    Permission.GESTIONAR_SECRETOS: "Gestionar la bóveda de secretos",
    Permission.GESTIONAR_USUARIOS: "Gestionar usuarios",
}


class Role(str, Enum):
    """Roles del equipo. Se corresponden con los del prototipo (`governance.ts`)."""

    ADMINISTRADOR = "administrador"
    LIDER_TECNICO = "lider_tecnico"
    QA = "qa"
    DESARROLLADOR = "desarrollador"
    ARQUITECTO = "arquitecto"
    ANALISTA = "analista"
    OBSERVADOR = "observador"


ROLE_LABELS: dict[Role, str] = {
    Role.ADMINISTRADOR: "Administrador",
    Role.LIDER_TECNICO: "Líder técnico",
    Role.QA: "QA",
    Role.DESARROLLADOR: "Desarrollador",
    Role.ARQUITECTO: "Arquitecto",
    Role.ANALISTA: "Analista funcional",
    Role.OBSERVADOR: "Observador",
}

#: Qué puede hacer cada rol. **Esta tabla es la única fuente**: la UI la consulta, no la copia.
ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.ADMINISTRADOR: frozenset(Permission),
    Role.LIDER_TECNICO: frozenset(
        {
            Permission.CREAR_REQUERIMIENTO,
            Permission.EJECUTAR,
            Permission.SOLICITAR_CAMBIO_AGENTE,
            Permission.APROBAR_CAMBIO_AGENTE,
            Permission.FIRMAR_DICTAMEN,
            Permission.VER_AUDITORIA,
            Permission.GESTIONAR_SECRETOS,
        }
    ),
    Role.QA: frozenset(
        {
            Permission.CREAR_REQUERIMIENTO,
            Permission.EJECUTAR,
            Permission.SOLICITAR_CAMBIO_AGENTE,
            Permission.FIRMAR_DICTAMEN,
            Permission.VER_AUDITORIA,
        }
    ),
    Role.DESARROLLADOR: frozenset(
        {
            Permission.CREAR_REQUERIMIENTO,
            Permission.EJECUTAR,
            Permission.SOLICITAR_CAMBIO_AGENTE,
        }
    ),
    Role.ARQUITECTO: frozenset(
        {
            Permission.EJECUTAR,
            Permission.SOLICITAR_CAMBIO_AGENTE,
            Permission.APROBAR_CAMBIO_AGENTE,
            Permission.FIRMAR_DICTAMEN,
            Permission.VER_AUDITORIA,
        }
    ),
    Role.ANALISTA: frozenset({Permission.CREAR_REQUERIMIENTO}),
    Role.OBSERVADOR: frozenset(),
}


class AuthProvider(str, Enum):
    """De dónde viene la identidad. Preparado para el inicio de sesión corporativo."""

    LOCAL = "local"
    OIDC = "oidc"


@dataclass(frozen=True, slots=True)
class User:
    """Una persona. **No tiene contraseña, y es deliberado**: el hash vive en la persistencia."""

    id: str
    email: str
    name: str
    role: Role
    created_at: datetime
    provider: AuthProvider = AuthProvider.LOCAL
    active: bool = True
    last_login_at: datetime | None = None
    failed_attempts: int = 0
    locked_until: datetime | None = None
    must_change_password: bool = False

    @property
    def permissions(self) -> frozenset[Permission]:
        return ROLE_PERMISSIONS.get(self.role, frozenset())

    @property
    def initials(self) -> str:
        partes = [p for p in self.name.split() if p]
        if not partes:
            return self.email[:2].upper()
        return "".join(p[0] for p in partes[:2]).upper()

    def can(self, permission: Permission) -> bool:
        return self.active and permission in self.permissions

    def is_locked(self, now: datetime) -> bool:
        return self.locked_until is not None and self.locked_until > now

    def with_failure(self, now: datetime, *, policy: "LockPolicy") -> "User":
        """Suma un intento fallido y, si toca, bloquea la cuenta."""
        intentos = self.failed_attempts + 1
        bloqueo = now + policy.lock_for if intentos >= policy.max_attempts else self.locked_until
        return replace(self, failed_attempts=intentos, locked_until=bloqueo)

    def with_login(self, now: datetime) -> "User":
        return replace(self, last_login_at=now, failed_attempts=0, locked_until=None)


@dataclass(frozen=True, slots=True)
class LockPolicy:
    """Bloqueo tras varios intentos fallidos.

    No hay que confundirlo con un antifuerza bruta completo: eso necesita también límite por IP
    (va en la pasarela o el proxy). Esto protege una cuenta concreta.
    """

    max_attempts: int = 5
    lock_for: timedelta = timedelta(minutes=15)


@dataclass(frozen=True, slots=True)
class SessionPolicy:
    """Cuánto vive una sesión."""

    max_age: timedelta = timedelta(hours=12)
    #: Sin actividad durante este tiempo, se cierra. Es lo que pide HIPAA 164.312(a)(2)(iii).
    idle_timeout: timedelta = timedelta(minutes=30)


@dataclass(frozen=True, slots=True)
class Session:
    """Sesión abierta. **Guarda el hash del testigo, no el testigo.**

    Si alguien se lleva un volcado de la tabla, no puede suplantar a nadie: el valor que viaja en
    la cookie no está ahí, igual que no está la contraseña.
    """

    id: str
    user_id: str
    created_at: datetime
    last_seen_at: datetime
    user_agent: str = ""
    ip: str = ""
    revoked_at: datetime | None = None

    def expires_at(self, policy: SessionPolicy) -> datetime:
        """Cuándo caduca: lo que ocurra antes, el tope absoluto o la inactividad."""
        return min(self.created_at + policy.max_age, self.last_seen_at + policy.idle_timeout)

    def is_valid(self, now: datetime, policy: SessionPolicy) -> bool:
        return self.revoked_at is None and self.expires_at(policy) > now

    def expiry_reason(self, now: datetime, policy: SessionPolicy) -> str:
        """Por qué dejó de valer. La UI lo dice: no es lo mismo cerrar sesión que caducar."""
        if self.revoked_at is not None:
            return "cerrada"
        if self.last_seen_at + policy.idle_timeout <= now:
            return "inactividad"
        if self.created_at + policy.max_age <= now:
            return "duracion_maxima"
        return ""

    def seen(self, now: datetime) -> "Session":
        return replace(self, last_seen_at=now)


#: Sin reglas de composición a propósito: empujan a `Password1!` y no aportan; la longitud
#: sí. Es lo que recomienda el NIST 800-63B.
MIN_PASSWORD_LENGTH = 12


def validate_password(password: str) -> str:
    """Comprueba lo mínimo. Devuelve la contraseña lista para cifrar."""
    limpia = password.strip()
    if len(limpia) < MIN_PASSWORD_LENGTH:
        raise DomainError(
            f"La contraseña necesita al menos {MIN_PASSWORD_LENGTH} caracteres. "
            "Una frase de varias palabras es más segura y más fácil de recordar."
        )
    return limpia


def normalize_email(email: str) -> str:
    return email.strip().lower()


def require(user: User | None, permission: Permission) -> None:
    """Lanza si la persona no puede. Es la comprobación que hace el servidor, no la UI."""
    if user is None:
        raise NotAuthenticatedError("Hace falta iniciar sesión.")
    if not user.active:
        raise ForbiddenError("La cuenta está desactivada.")
    if not user.can(permission):
        raise ForbiddenError(
            f"Tu rol ({ROLE_LABELS[user.role]}) no tiene el permiso "
            f"«{PERMISSION_LABELS[permission]}»."
        )


class NotAuthenticatedError(DomainError):
    """No hay sesión válida. La API lo traduce a 401."""


class ForbiddenError(DomainError):
    """Hay sesión, pero no permiso. La API lo traduce a 403."""


class InvalidCredentialsError(DomainError):
    """Usuario o contraseña incorrectos.

    **El mensaje es el mismo exista o no el usuario**: decir «ese correo no existe» le confirma a
    quien prueba direcciones cuáles son válidas.
    """

    def __init__(self, message: str = "Correo o contraseña incorrectos.") -> None:
        super().__init__(message)


class AccountLockedError(DomainError):
    """Demasiados intentos fallidos."""
