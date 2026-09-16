"""Retención y borrado."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import sqlalchemy as sa

from . import schema as s
from .engine import Database

log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class PurgeResult:
    requirements: int
    runs: int
    events: int

    @property
    def anything(self) -> bool:
        return bool(self.requirements or self.runs or self.events)


class RetentionService:
    def __init__(self, database: Database, *, default_days: int = 0) -> None:
        self._db = database
        self._default_days = default_days

    def due_date(self, created_at: datetime) -> datetime | None:
        """Fecha de purga por defecto. `0` días = sin caducidad automática."""
        if not self._default_days:
            return None
        return created_at + timedelta(days=self._default_days)

    async def purge_expired(self, *, now: datetime | None = None) -> PurgeResult:
        """Borra los requerimientos cuya retención venció, con todo lo que cuelga de ellos."""
        now = now or datetime.now(timezone.utc)
        async with self._db.session() as session:
            expired = (
                (
                    await session.execute(
                        sa.select(s.requirements.c.id).where(
                            s.requirements.c.retention_until.is_not(None),
                            s.requirements.c.retention_until <= now,
                        )
                    )
                )
                .scalars()
                .all()
            )
            if not expired:
                return PurgeResult(0, 0, 0)

            run_ids = (
                (
                    await session.execute(
                        sa.select(s.runs.c.id).where(s.runs.c.requirement_id.in_(expired))
                    )
                )
                .scalars()
                .all()
            )
            events = 0
            if run_ids:
                events = (
                    await session.execute(
                        sa.select(sa.func.count())
                        .select_from(s.trace_events)
                        .where(s.trace_events.c.run_id.in_(run_ids))
                    )
                ).scalar_one()

            # El borrado en cascada de la clave foránea se lleva adjuntos, plan, ejecuciones,
            # llamadas y traza.
            await session.execute(sa.delete(s.requirements).where(s.requirements.c.id.in_(expired)))

        log.info("purga de retención: %s requerimiento(s), %s ejecución(es)", len(expired), len(run_ids))
        return PurgeResult(requirements=len(expired), runs=len(run_ids), events=int(events))
