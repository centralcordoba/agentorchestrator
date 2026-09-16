"""Copia de trabajo efímera de un repositorio del cliente."""
from __future__ import annotations

import asyncio
import logging
import os
import shutil
import stat
import tempfile
from pathlib import Path
from types import TracebackType

log = logging.getLogger(__name__)

#: Prefijo de los directorios temporales. Sirve para reconocerlos si algo quedara suelto.
PREFIX = "orq-repo-"


def _force_writable(func, path, _exc):  # type: ignore[no-untyped-def]
    """En Windows los objetos de `.git` quedan de solo lectura y `rmtree` falla."""
    os.chmod(path, stat.S_IWRITE)
    func(path)


class Workspace:
    """Directorio temporal con el repositorio clonado."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._closed = False

    @classmethod
    def create(cls) -> "Workspace":
        return cls(Path(tempfile.mkdtemp(prefix=PREFIX)))

    async def close(self) -> None:
        """Borra la copia. Es idempotente: llamarla dos veces no es un error."""
        if self._closed:
            return
        self._closed = True
        await asyncio.to_thread(shutil.rmtree, self.path, False, _force_writable)
        log.debug("copia de trabajo borrada: %s", self.path)

    @property
    def closed(self) -> bool:
        return self._closed

    async def __aenter__(self) -> "Workspace":
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.close()


def leftovers() -> tuple[Path, ...]:
    """Copias que quedaron de un proceso anterior que murió sin limpiar.

    La aplicación las borra al arrancar: un cierre brusco no puede dejar código del cliente en el
    disco indefinidamente.
    """
    base = Path(tempfile.gettempdir())
    try:
        return tuple(p for p in base.glob(f"{PREFIX}*") if p.is_dir())
    except OSError:  # pragma: no cover - el temporal siempre existe
        return ()


async def clean_leftovers() -> int:
    """Borra las copias huérfanas. Devuelve cuántas."""
    borradas = 0
    for path in leftovers():
        try:
            await asyncio.to_thread(shutil.rmtree, path, False, _force_writable)
            borradas += 1
        except OSError as error:  # pragma: no cover - carrera con otro proceso
            log.warning("no se pudo borrar la copia huérfana %s: %s", path, error)
    if borradas:
        log.info("se borraron %s copia(s) de trabajo huérfanas", borradas)
    return borradas
