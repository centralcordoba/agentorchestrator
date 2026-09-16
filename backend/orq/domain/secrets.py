"""Bóveda de secretos: qué es un secreto y cuándo se puede usar."""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from enum import Enum

from .errors import DomainError

ORGANIZATION = ""


class SecretKind(str, Enum):
    """Para qué sirve el secreto. Determina quién lo pide y cómo se usa."""

    GIT_TOKEN = "git_token"
    SITE_CREDENTIAL = "site_credential"
    LLM_API_KEY = "llm_api_key"
    AZURE_DEVOPS = "azure_devops"


KIND_LABELS: dict[SecretKind, str] = {
    SecretKind.GIT_TOKEN: "Token de repositorio",
    SecretKind.SITE_CREDENTIAL: "Credencial de sitio",
    SecretKind.LLM_API_KEY: "Clave de proveedor de IA",
    SecretKind.AZURE_DEVOPS: "Credencial de Azure DevOps",
}

MIN_LENGTH = 8


@dataclass(frozen=True, slots=True)
class SecretMetadata:
    """Lo que se puede enseñar de un secreto. **Sin el valor, y sin sitio donde ponerlo.**"""

    id: str
    kind: SecretKind
    name: str
    scope: str
    created_by: str
    created_at: datetime
    updated_at: datetime
    username: str = ""
    expires_at: datetime | None = None
    revoked_at: datetime | None = None
    revoked_by: str = ""
    last_used_at: datetime | None = None
    uses: int = 0
    hint: str = ""

    def is_active(self, now: datetime) -> bool:
        """¿Se puede usar ahora mismo?"""
        if self.revoked_at is not None:
            return False
        return self.expires_at is None or self.expires_at > now

    def status(self, now: datetime) -> str:
        if self.revoked_at is not None:
            return "revocado"
        if self.expires_at is not None and self.expires_at <= now:
            return "caducado"
        return "activo"

    def used(self, at: datetime) -> "SecretMetadata":
        return replace(self, last_used_at=at, uses=self.uses + 1)

    def revoked(self, at: datetime, *, by: str) -> "SecretMetadata":
        if self.revoked_at is not None:
            return self
        return replace(self, revoked_at=at, revoked_by=by, updated_at=at)


@dataclass(frozen=True, slots=True)
class SecretValue:
    """El valor, solo mientras se usa. Nunca se serializa ni se devuelve por la API."""

    metadata: SecretMetadata
    value: str
    username: str = ""

    def __repr__(self) -> str:  # pragma: no cover - trivial, pero es la salvaguarda
        return f"SecretValue(id={self.metadata.id!r}, kind={self.metadata.kind.value!r}, value='***')"

    def __str__(self) -> str:  # pragma: no cover - idem
        return self.__repr__()


@dataclass(frozen=True, slots=True)
class NewSecret:
    """Petición de guardar o rotar un secreto."""

    kind: SecretKind
    name: str
    value: str
    scope: str = ORGANIZATION
    username: str = ""
    expires_at: datetime | None = None
    created_by: str = ""

    def validated(self) -> "NewSecret":
        """Comprueba lo poco que se puede comprobar sin conocer al proveedor."""
        if not self.name.strip():
            raise DomainError("El secreto necesita un nombre (host, URL o proveedor).")
        if len(self.value.strip()) < MIN_LENGTH:
            raise DomainError(
                f"El valor del secreto es demasiado corto: se esperan al menos {MIN_LENGTH} "
                "caracteres. Comprueba que lo has pegado entero."
            )
        return replace(self, name=self.name.strip().lower(), value=self.value.strip())


def hint_of(value: str) -> str:
    """Pista para reconocer un secreto sin enseñarlo: los últimos cuatro caracteres.

    Cuatro es lo que usan los bancos con las tarjetas: bastan para distinguir dos tokens y no
    para reconstruir ninguno.
    """
    limpio = value.strip()
    return f"…{limpio[-4:]}" if len(limpio) > 8 else "…"


def resolution_order(kind: SecretKind, name: str, scope: str) -> tuple[tuple[str, str], ...]:
    """En qué orden se busca un secreto: lo del requerimiento manda sobre lo de la organización.

    Devuelve pares (nombre, ámbito) a probar. Permite que un requerimiento concreto use un token
    distinto —por ejemplo, un repositorio de otro cliente— sin tocar el de la organización.
    """
    candidatos: list[tuple[str, str]] = []
    if scope:
        candidatos.append((name, scope))
    candidatos.append((name, ORGANIZATION))
    return tuple(candidatos)
