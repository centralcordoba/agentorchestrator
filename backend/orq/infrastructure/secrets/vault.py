"""Bóveda de secretos: en memoria y sobre PostgreSQL."""
from __future__ import annotations

import logging
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert

from ...domain.errors import NotFoundError
from ...domain.secrets import (
    NewSecret,
    SecretKind,
    SecretMetadata,
    SecretValue,
    hint_of,
    resolution_order,
)
from ..db import schema as s
from ..db.engine import Database
from .scrubber import SecretScrubber

log = logging.getLogger(__name__)


def _metadata_from_row(row: sa.Row) -> SecretMetadata:
    return SecretMetadata(
        id=row.id,
        kind=SecretKind(row.kind),
        name=row.name,
        scope=row.scope,
        created_by=row.created_by,
        created_at=row.created_at,
        updated_at=row.updated_at,
        expires_at=row.expires_at,
        revoked_at=row.revoked_at,
        revoked_by=row.revoked_by,
        last_used_at=row.last_used_at,
        uses=row.uses,
        hint=row.hint,
    )


class InMemorySecretVault:
    """Bóveda de memoria: sirve para las pruebas y para arrancar sin base de datos.

    Se avisa por log de que no persiste: arrancar sin `DATABASE_URL` y guardar un token que
    desaparece al reiniciar sería una sorpresa desagradable.
    """

    def __init__(self, scrubber: SecretScrubber | None = None) -> None:
        self._by_id: dict[str, SecretMetadata] = {}
        self._values: dict[str, tuple[str, str]] = {}
        self._scrubber = scrubber
        self._next = 0

    async def save(self, secret: NewSecret, *, at: datetime) -> SecretMetadata:
        limpio = secret.validated()
        existente = self._find(limpio.kind, limpio.name, limpio.scope)
        if existente is not None:
            anterior = self._values.pop(existente.id, None)
            if anterior is not None and self._scrubber is not None:
                self._scrubber.forget(anterior[0])
            identificador = existente.id
            creado = existente.created_at
            creado_por = existente.created_by
        else:
            self._next += 1
            identificador = f"SEC-{self._next:03d}"
            creado = at
            creado_por = limpio.created_by

        metadata = SecretMetadata(
            id=identificador,
            kind=limpio.kind,
            name=limpio.name,
            scope=limpio.scope,
            created_by=creado_por,
            created_at=creado,
            updated_at=at,
            username=limpio.username,
            expires_at=limpio.expires_at,
            hint=hint_of(limpio.value),
        )
        self._by_id[identificador] = metadata
        self._values[identificador] = (limpio.value, limpio.username)
        if self._scrubber is not None:
            self._scrubber.remember(limpio.value)
        return metadata

    async def list(self, *, scope: str | None = None) -> list[SecretMetadata]:
        valores = [m for m in self._by_id.values() if scope is None or m.scope == scope]
        return sorted(valores, key=lambda m: (m.kind.value, m.name, m.scope))

    async def get(self, secret_id: str) -> SecretMetadata | None:
        return self._by_id.get(secret_id)

    async def revoke(self, secret_id: str, *, at: datetime, by: str) -> SecretMetadata:
        metadata = self._by_id.get(secret_id)
        if metadata is None:
            raise NotFoundError(f"No existe el secreto {secret_id}.")
        revocado = metadata.revoked(at, by=by)
        self._by_id[secret_id] = revocado
        # El valor se borra de memoria al revocar: no hay por qué seguir teniéndolo.
        valor = self._values.pop(secret_id, None)
        if valor is not None and self._scrubber is not None:
            self._scrubber.forget(valor[0])
        return revocado

    async def reveal(
        self, kind: SecretKind, name: str, *, scope: str = "", at: datetime
    ) -> SecretValue | None:
        for nombre, ambito in resolution_order(kind, name.lower(), scope):
            metadata = self._find(kind, nombre, ambito)
            if metadata is None or not metadata.is_active(at):
                continue
            valor = self._values.get(metadata.id)
            if valor is None:
                continue
            usado = metadata.used(at)
            self._by_id[metadata.id] = usado
            return SecretValue(metadata=usado, value=valor[0], username=valor[1])
        return None

    async def prime(self) -> int:
        """Carga los valores activos en el tachador. **No cuenta como uso.**"""
        if self._scrubber is None:
            return 0
        self._scrubber.remember(*(valor for valor, _ in self._values.values()))
        return len(self._values)

    def _find(self, kind: SecretKind, name: str, scope: str) -> SecretMetadata | None:
        return next(
            (
                m
                for m in self._by_id.values()
                if m.kind is kind and m.name == name and m.scope == scope
            ),
            None,
        )


class PostgresSecretVault:
    """Bóveda sobre PostgreSQL, con el valor cifrado en reposo."""

    def __init__(
        self,
        database: Database,
        *,
        ids: object | None = None,
        scrubber: SecretScrubber | None = None,
    ) -> None:
        self._db = database
        self._cipher = database.cipher
        self._ids = ids
        self._scrubber = scrubber

    async def save(self, secret: NewSecret, *, at: datetime) -> SecretMetadata:
        limpio = secret.validated()
        identificador = await self._new_id()
        valores = {
            "id": identificador,
            "kind": limpio.kind.value,
            "name": limpio.name,
            "scope": limpio.scope,
            "value_enc": self._cipher.encrypt(limpio.value),
            "username_enc": self._cipher.encrypt(limpio.username) if limpio.username else None,
            "hint": hint_of(limpio.value),
            "created_by": limpio.created_by,
            "created_at": at,
            "updated_at": at,
            "expires_at": limpio.expires_at,
        }
        async with self._db.session() as session:
            # Guardar otra vez el mismo (tipo, nombre, ámbito) es **rotar**: se sustituye el
            # valor y se levanta la revocación, conservando quién lo creó y cuándo.
            sentencia = insert(s.secrets).values(**valores)
            sentencia = sentencia.on_conflict_do_update(
                constraint="uq_secrets_kind_name_scope",
                set_={
                    "value_enc": sentencia.excluded.value_enc,
                    "username_enc": sentencia.excluded.username_enc,
                    "hint": sentencia.excluded.hint,
                    "updated_at": sentencia.excluded.updated_at,
                    "expires_at": sentencia.excluded.expires_at,
                    "revoked_at": None,
                    "revoked_by": "",
                },
            ).returning(s.secrets)
            row = (await session.execute(sentencia)).one()

        if self._scrubber is not None:
            self._scrubber.remember(limpio.value)
        return _with_username(_metadata_from_row(row), limpio.username)

    async def list(self, *, scope: str | None = None) -> list[SecretMetadata]:
        consulta = sa.select(s.secrets).order_by(s.secrets.c.kind, s.secrets.c.name, s.secrets.c.scope)
        if scope is not None:
            consulta = consulta.where(s.secrets.c.scope == scope)
        async with self._db.session() as session:
            filas = (await session.execute(consulta)).all()
        return [self._con_usuario(row) for row in filas]

    async def get(self, secret_id: str) -> SecretMetadata | None:
        async with self._db.session() as session:
            row = (
                await session.execute(sa.select(s.secrets).where(s.secrets.c.id == secret_id))
            ).one_or_none()
        return self._con_usuario(row) if row is not None else None

    async def revoke(self, secret_id: str, *, at: datetime, by: str) -> SecretMetadata:
        async with self._db.session() as session:
            row = (
                await session.execute(
                    sa.update(s.secrets)
                    .where(s.secrets.c.id == secret_id, s.secrets.c.revoked_at.is_(None))
                    # Revocar **borra el valor**: deja de estar ni siquiera cifrado en la base.
                    .values(revoked_at=at, revoked_by=by, updated_at=at, value_enc=b"")
                    .returning(s.secrets)
                )
            ).one_or_none()
            if row is None:
                actual = (
                    await session.execute(sa.select(s.secrets).where(s.secrets.c.id == secret_id))
                ).one_or_none()
                if actual is None:
                    raise NotFoundError(f"No existe el secreto {secret_id}.")
                return self._con_usuario(actual)  # ya estaba revocado
        return _metadata_from_row(row)

    async def reveal(
        self, kind: SecretKind, name: str, *, scope: str = "", at: datetime
    ) -> SecretValue | None:
        for nombre, ambito in resolution_order(kind, name.lower(), scope):
            async with self._db.session() as session:
                row = (
                    await session.execute(
                        sa.select(s.secrets).where(
                            s.secrets.c.kind == kind.value,
                            s.secrets.c.name == nombre,
                            s.secrets.c.scope == ambito,
                            s.secrets.c.revoked_at.is_(None),
                        )
                    )
                ).one_or_none()
                if row is None or not row.value_enc:
                    continue
                metadata = _metadata_from_row(row)
                if not metadata.is_active(at):
                    continue
                await session.execute(
                    sa.update(s.secrets)
                    .where(s.secrets.c.id == row.id)
                    .values(last_used_at=at, uses=s.secrets.c.uses + 1)
                )
            valor = self._cipher.decrypt(row.value_enc)
            usuario = self._cipher.decrypt(row.username_enc) if row.username_enc else ""
            if self._scrubber is not None:
                self._scrubber.remember(valor)
            return SecretValue(metadata=metadata.used(at), value=valor, username=usuario)
        return None

    async def prime(self) -> int:
        """Carga los valores activos en el tachador. **No cuenta como uso.**

        Descifra para poder tachar, que es justo lo contrario de filtrar: los valores se quedan
        en memoria del proceso para poder reconocerlos y sustituirlos allá donde aparezcan.
        """
        if self._scrubber is None:
            return 0
        async with self._db.session() as session:
            filas = (
                await session.execute(
                    sa.select(s.secrets.c.value_enc).where(s.secrets.c.revoked_at.is_(None))
                )
            ).all()
        cargados = 0
        for (cifrado,) in filas:
            if not cifrado:
                continue
            self._scrubber.remember(self._cipher.decrypt(cifrado))
            cargados += 1
        return cargados

    def _con_usuario(self, row: sa.Row) -> SecretMetadata:
        metadata = _metadata_from_row(row)
        if not row.username_enc:
            return metadata
        return _with_username(metadata, self._cipher.decrypt(row.username_enc))

    async def _new_id(self) -> str:
        if self._ids is not None:
            return await self._ids.new_id("SEC")  # type: ignore[union-attr]
        import uuid

        return f"SEC-{uuid.uuid4().hex[:8]}"


def _with_username(metadata: SecretMetadata, username: str) -> SecretMetadata:
    from dataclasses import replace

    return replace(metadata, username=username)
