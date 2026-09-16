"""Conexión a PostgreSQL."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from .crypto import Cipher

log = logging.getLogger(__name__)


class Database:
    """Motor, sesiones y cifrador: lo que necesitan los repositorios."""

    def __init__(self, *, url: str, cipher: Cipher, echo: bool = False) -> None:
        self.url = url
        self.cipher = cipher
        self._engine: AsyncEngine = create_async_engine(
            url, echo=echo, pool_pre_ping=True, future=True
        )
        self._sessions: async_sessionmaker[AsyncSession] = async_sessionmaker(
            self._engine, expire_on_commit=False
        )

    @property
    def engine(self) -> AsyncEngine:
        return self._engine

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        """Sesión con confirmación al salir y retroceso si algo falla."""
        async with self._sessions() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    async def ping(self) -> bool:
        from sqlalchemy import text

        try:
            async with self._engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
            return True
        except Exception as exc:  # la salud del servicio no debe caerse por esto
            log.warning("la base de datos no responde: %s", exc)
            return False

    async def dispose(self) -> None:
        await self._engine.dispose()


def normalize_url(url: str) -> str:
    """Acepta la forma `postgresql://` habitual y la traduce al driver asíncrono."""
    if url.startswith("postgresql+asyncpg://"):
        return url
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+asyncpg://", 1)
    return url
