"""Usuarios y sesiones: en memoria y sobre PostgreSQL."""
from __future__ import annotations

import logging
from datetime import datetime

import sqlalchemy as sa

from ...domain.identity import AuthProvider, Role, Session, User, normalize_email
from ..db import schema as s
from ..db.engine import Database

log = logging.getLogger(__name__)


def _user_from_row(row: sa.Row) -> User:
    return User(
        id=row.id,
        email=row.email,
        name=row.name,
        role=Role(row.role),
        created_at=row.created_at,
        provider=AuthProvider(row.provider),
        active=row.active,
        last_login_at=row.last_login_at,
        failed_attempts=row.failed_attempts,
        locked_until=row.locked_until,
        must_change_password=row.must_change_password,
    )


def _session_from_row(row: sa.Row) -> Session:
    return Session(
        id=row.id,
        user_id=row.user_id,
        created_at=row.created_at,
        last_seen_at=row.last_seen_at,
        revoked_at=row.revoked_at,
        user_agent=row.user_agent,
        ip=row.ip,
    )


def _user_values(user: User, password_hash: str | None) -> dict[str, object]:
    valores: dict[str, object] = {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "role": user.role.value,
        "provider": user.provider.value,
        "active": user.active,
        "must_change_password": user.must_change_password,
        "created_at": user.created_at,
        "last_login_at": user.last_login_at,
        "failed_attempts": user.failed_attempts,
        "locked_until": user.locked_until,
    }
    if password_hash is not None:
        valores["password_hash"] = password_hash
    return valores


class InMemoryUserRepository:
    """Usuarios en memoria. Para las pruebas y para arrancar sin base de datos."""

    def __init__(self) -> None:
        self._users: dict[str, User] = {}
        self._hashes: dict[str, str] = {}

    async def add(self, user: User, *, password_hash: str | None = None) -> None:
        self._users[user.id] = user
        if password_hash is not None:
            self._hashes[user.id] = password_hash

    async def save(self, user: User) -> None:
        self._users[user.id] = user

    async def get(self, user_id: str) -> User | None:
        return self._users.get(user_id)

    async def by_email(self, email: str) -> User | None:
        buscado = normalize_email(email)
        return next((u for u in self._users.values() if u.email == buscado), None)

    async def list(self) -> list[User]:
        return sorted(self._users.values(), key=lambda u: (u.name.lower(), u.email))

    async def count(self) -> int:
        return len(self._users)

    async def credential_of(self, user_id: str) -> str | None:
        """Hash guardado. **Solo lo llama el caso de uso de login.**"""
        return self._hashes.get(user_id)

    async def set_password(self, user_id: str, password_hash: str) -> None:
        self._hashes[user_id] = password_hash


class InMemorySessionRepository:
    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}

    async def add(self, session: Session) -> None:
        self._sessions[session.id] = session

    async def get(self, session_id: str) -> Session | None:
        return self._sessions.get(session_id)

    async def save(self, session: Session) -> None:
        self._sessions[session.id] = session

    async def revoke(self, session_id: str, *, at: datetime) -> None:
        sesion = self._sessions.get(session_id)
        if sesion is not None:
            self._sessions[session_id] = Session(
                id=sesion.id,
                user_id=sesion.user_id,
                created_at=sesion.created_at,
                last_seen_at=sesion.last_seen_at,
                revoked_at=at,
                user_agent=sesion.user_agent,
                ip=sesion.ip,
            )

    async def revoke_all_for(self, user_id: str, *, at: datetime) -> int:
        cuantas = 0
        for sesion in list(self._sessions.values()):
            if sesion.user_id == user_id and sesion.revoked_at is None:
                await self.revoke(sesion.id, at=at)
                cuantas += 1
        return cuantas

    async def purge_before(self, cutoff: datetime) -> int:
        viejas = [s_.id for s_ in self._sessions.values() if s_.last_seen_at < cutoff]
        for identificador in viejas:
            self._sessions.pop(identificador, None)
        return len(viejas)


class PostgresUserRepository:
    def __init__(self, database: Database) -> None:
        self._db = database

    async def add(self, user: User, *, password_hash: str | None = None) -> None:
        async with self._db.session() as session:
            await session.execute(sa.insert(s.users).values(**_user_values(user, password_hash)))

    async def save(self, user: User) -> None:
        async with self._db.session() as session:
            await session.execute(
                sa.update(s.users).where(s.users.c.id == user.id).values(**_user_values(user, None))
            )

    async def get(self, user_id: str) -> User | None:
        async with self._db.session() as session:
            row = (
                await session.execute(sa.select(s.users).where(s.users.c.id == user_id))
            ).one_or_none()
        return _user_from_row(row) if row is not None else None

    async def by_email(self, email: str) -> User | None:
        async with self._db.session() as session:
            row = (
                await session.execute(
                    sa.select(s.users).where(s.users.c.email == normalize_email(email))
                )
            ).one_or_none()
        return _user_from_row(row) if row is not None else None

    async def list(self) -> list[User]:
        async with self._db.session() as session:
            filas = (await session.execute(sa.select(s.users).order_by(s.users.c.name))).all()
        return [_user_from_row(row) for row in filas]

    async def count(self) -> int:
        async with self._db.session() as session:
            return int(
                (await session.execute(sa.select(sa.func.count()).select_from(s.users))).scalar()
                or 0
            )

    async def credential_of(self, user_id: str) -> str | None:
        """Hash guardado. **Solo lo llama el caso de uso de login.**"""
        async with self._db.session() as session:
            return (
                await session.execute(
                    sa.select(s.users.c.password_hash).where(s.users.c.id == user_id)
                )
            ).scalar()

    async def set_password(self, user_id: str, password_hash: str) -> None:
        async with self._db.session() as session:
            await session.execute(
                sa.update(s.users)
                .where(s.users.c.id == user_id)
                .values(password_hash=password_hash, must_change_password=False)
            )


class PostgresSessionRepository:
    def __init__(self, database: Database) -> None:
        self._db = database

    async def add(self, session_: Session) -> None:
        async with self._db.session() as session:
            await session.execute(
                sa.insert(s.sessions).values(
                    id=session_.id,
                    user_id=session_.user_id,
                    created_at=session_.created_at,
                    last_seen_at=session_.last_seen_at,
                    revoked_at=session_.revoked_at,
                    user_agent=session_.user_agent[:255],
                    ip=session_.ip[:64],
                )
            )

    async def get(self, session_id: str) -> Session | None:
        async with self._db.session() as session:
            row = (
                await session.execute(sa.select(s.sessions).where(s.sessions.c.id == session_id))
            ).one_or_none()
        return _session_from_row(row) if row is not None else None

    async def save(self, session_: Session) -> None:
        async with self._db.session() as session:
            await session.execute(
                sa.update(s.sessions)
                .where(s.sessions.c.id == session_.id)
                .values(last_seen_at=session_.last_seen_at, revoked_at=session_.revoked_at)
            )

    async def revoke(self, session_id: str, *, at: datetime) -> None:
        async with self._db.session() as session:
            await session.execute(
                sa.update(s.sessions)
                .where(s.sessions.c.id == session_id, s.sessions.c.revoked_at.is_(None))
                .values(revoked_at=at)
            )

    async def revoke_all_for(self, user_id: str, *, at: datetime) -> int:
        async with self._db.session() as session:
            resultado = await session.execute(
                sa.update(s.sessions)
                .where(s.sessions.c.user_id == user_id, s.sessions.c.revoked_at.is_(None))
                .values(revoked_at=at)
            )
        return int(resultado.rowcount or 0)

    async def purge_before(self, cutoff: datetime) -> int:
        """Borra sesiones viejas. Se llama al arrancar: la tabla no puede crecer sin fin."""
        async with self._db.session() as session:
            resultado = await session.execute(
                sa.delete(s.sessions).where(s.sessions.c.last_seen_at < cutoff)
            )
        return int(resultado.rowcount or 0)
