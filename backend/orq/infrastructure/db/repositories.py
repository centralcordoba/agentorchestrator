"""Repositorios sobre PostgreSQL."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert

from ...domain.audit import GENESIS, AuditEntry
from ...domain.enums import AgentId
from ...domain.plan import Plan
from ...domain.profiles import AgentProfile
from ...domain.requirement import Requirement
from ...domain.run import Run, TraceEvent
from . import mappers as m
from . import schema as s
from .engine import Database

log = logging.getLogger(__name__)


class _Repository:
    def __init__(self, database: Database) -> None:
        self._db = database
        self._cipher = database.cipher


class PostgresRequirementRepository(_Repository):
    async def add(self, requirement: Requirement) -> None:
        await self.save(requirement)

    async def save(self, requirement: Requirement) -> None:
        row = m.requirement_row(requirement, self._cipher)
        async with self._db.session() as session:
            statement = insert(s.requirements).values(**row)
            await session.execute(
                statement.on_conflict_do_update(
                    index_elements=[s.requirements.c.id],
                    set_={k: statement.excluded[k] for k in row if k != "id"},
                )
            )
            await session.execute(
                sa.delete(s.attachments).where(s.attachments.c.requirement_id == requirement.id)
            )
            rows = m.attachment_rows(requirement, self._cipher)
            if rows:
                await session.execute(sa.insert(s.attachments), rows)

    async def get(self, requirement_id: str) -> Requirement | None:
        async with self._db.session() as session:
            row = (
                await session.execute(
                    sa.select(s.requirements).where(s.requirements.c.id == requirement_id)
                )
            ).mappings().first()
            if row is None:
                return None
            attachments = (
                (
                    await session.execute(
                        sa.select(s.attachments)
                        .where(s.attachments.c.requirement_id == requirement_id)
                        .order_by(s.attachments.c.added_at, s.attachments.c.id)
                    )
                )
                .mappings()
                .all()
            )
        return m.requirement_from_rows(row, list(attachments), self._cipher)

    async def count(self) -> int:
        async with self._db.session() as session:
            return int(
                (
                    await session.execute(
                        sa.select(sa.func.count()).select_from(s.requirements)
                    )
                ).scalar_one()
            )

    async def list(self, *, limit: int | None = None, offset: int = 0) -> list[Requirement]:
        query = sa.select(s.requirements).order_by(s.requirements.c.created_at.desc())
        if offset:
            query = query.offset(offset)
        if limit is not None:
            query = query.limit(limit)
        async with self._db.session() as session:
            rows = (await session.execute(query)).mappings().all()
            if not rows:
                return []
            ids = [r["id"] for r in rows]
            attachments = (
                (
                    await session.execute(
                        sa.select(s.attachments)
                        .where(s.attachments.c.requirement_id.in_(ids))
                        .order_by(s.attachments.c.added_at, s.attachments.c.id)
                    )
                )
                .mappings()
                .all()
            )
        by_requirement: dict[str, list] = {}
        for attachment in attachments:
            by_requirement.setdefault(attachment["requirement_id"], []).append(attachment)
        return [
            m.requirement_from_rows(row, by_requirement.get(row["id"], []), self._cipher)
            for row in rows
        ]

    async def delete(self, requirement_id: str) -> bool:
        """Borra el requerimiento y, en cascada, todo lo que cuelga de él."""
        async with self._db.session() as session:
            result = await session.execute(
                sa.delete(s.requirements).where(s.requirements.c.id == requirement_id)
            )
        return bool(result.rowcount)

    async def set_retention(self, requirement_id: str, until: datetime | None) -> None:
        async with self._db.session() as session:
            await session.execute(
                sa.update(s.requirements)
                .where(s.requirements.c.id == requirement_id)
                .values(retention_until=until)
            )


class PostgresPlanRepository(_Repository):
    async def get(self, requirement_id: str) -> Plan | None:
        async with self._db.session() as session:
            row = (
                await session.execute(
                    sa.select(s.plans).where(s.plans.c.requirement_id == requirement_id)
                )
            ).mappings().first()
        return m.plan_from_row(row, self._cipher) if row else None

    async def save(self, requirement_id: str, plan: Plan) -> None:
        row = m.plan_row(requirement_id, plan, self._cipher)
        async with self._db.session() as session:
            statement = insert(s.plans).values(**row)
            await session.execute(
                statement.on_conflict_do_update(
                    index_elements=[s.plans.c.requirement_id],
                    set_={k: statement.excluded[k] for k in row if k != "requirement_id"},
                )
            )


class PostgresRunRepository(_Repository):
    def __init__(self, database: Database) -> None:
        super().__init__(database)
        self._seq: dict[str, int] = {}

    async def add(self, run: Run) -> None:
        await self.save(run)

    async def save(self, run: Run) -> None:
        """Guarda la ejecución entera: cabecera, estado por agente y llamadas.

        Los perfiles congelados se escriben al crear y **no se vuelven a tocar**: el `UPDATE` no
        los incluye.
        """
        header = m.run_row(run)
        async with self._db.session() as session:
            statement = insert(s.runs).values(**header)
            immutable = {"id", "requirement_id", "started_by", "started_at", "profiles", "enabled_agents"}
            await session.execute(
                statement.on_conflict_do_update(
                    index_elements=[s.runs.c.id],
                    set_={k: statement.excluded[k] for k in header if k not in immutable},
                )
            )

            executions = m.execution_rows(run, self._cipher)
            for row in executions:
                execution_statement = insert(s.run_executions).values(**row)
                await session.execute(
                    execution_statement.on_conflict_do_update(
                        index_elements=[s.run_executions.c.run_id, s.run_executions.c.agent_id],
                        set_={
                            k: execution_statement.excluded[k]
                            for k in row
                            if k not in {"run_id", "agent_id"}
                        },
                    )
                )

            # Las llamadas son un registro de solo anexado: se escriben las que falten.
            calls = m.call_rows(run)
            if calls:
                already = (
                    await session.execute(
                        sa.select(sa.func.count())
                        .select_from(s.llm_calls)
                        .where(s.llm_calls.c.run_id == run.id)
                    )
                ).scalar_one()
                if len(calls) > already:
                    await session.execute(sa.insert(s.llm_calls), calls[already:])

    async def get(self, run_id: str) -> Run | None:
        async with self._db.session() as session:
            row = (
                await session.execute(sa.select(s.runs).where(s.runs.c.id == run_id))
            ).mappings().first()
            if row is None:
                return None
            executions = (
                (
                    await session.execute(
                        sa.select(s.run_executions).where(s.run_executions.c.run_id == run_id)
                    )
                )
                .mappings()
                .all()
            )
            calls = (
                (
                    await session.execute(
                        sa.select(s.llm_calls)
                        .where(s.llm_calls.c.run_id == run_id)
                        .order_by(s.llm_calls.c.id)
                    )
                )
                .mappings()
                .all()
            )
        return m.run_from_rows(row, list(executions), list(calls), self._cipher)

    async def list_for_requirement(
        self, requirement_id: str, *, limit: int | None = None, offset: int = 0
    ) -> list[Run]:
        return await self._list(
            s.runs.c.requirement_id == requirement_id, limit=limit, offset=offset
        )

    async def count_for_requirement(self, requirement_id: str) -> int:
        async with self._db.session() as session:
            return int(
                (
                    await session.execute(
                        sa.select(sa.func.count())
                        .select_from(s.runs)
                        .where(s.runs.c.requirement_id == requirement_id)
                    )
                ).scalar_one()
            )

    async def list_unfinished(self) -> list[Run]:
        return await self._list(s.runs.c.status == "en_curso")

    async def _list(
        self,
        condition: sa.ColumnElement[bool],
        *,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[Run]:
        query = sa.select(s.runs.c.id).where(condition).order_by(s.runs.c.started_at.desc())
        if offset:
            query = query.offset(offset)
        if limit is not None:
            query = query.limit(limit)
        async with self._db.session() as session:
            ids = (await session.execute(query)).scalars().all()
        runs = []
        for run_id in ids:
            run = await self.get(run_id)
            if run is not None:
                runs.append(run)
        return runs

    async def append_event(self, event: TraceEvent) -> None:
        async with self._db.session() as session:
            await session.execute(
                sa.insert(s.trace_events).values(**m.event_row(event, self._cipher))
            )

    async def events(self, run_id: str, *, after_seq: int = 0) -> list[TraceEvent]:
        async with self._db.session() as session:
            rows = (
                (
                    await session.execute(
                        sa.select(s.trace_events)
                        .where(s.trace_events.c.run_id == run_id, s.trace_events.c.seq > after_seq)
                        .order_by(s.trace_events.c.seq)
                    )
                )
                .mappings()
                .all()
            )
        return [m.event_from_row(row, self._cipher) for row in rows]

    async def next_seq(self, run_id: str) -> int:
        """Siguiente número de secuencia de la traza.

        Se reserva en memoria porque los agentes de una oleada emiten a la vez: leer el máximo de
        la tabla en cada evento haría que dos corrutinas pidieran el mismo número. El contador
        arranca desde lo que ya hay guardado, así que reanudar una ejecución sigue la numeración.
        Es correcto mientras la ejecución viva en un proceso, que es como funciona el supervisor.
        """
        cached = self._seq.get(run_id)
        if cached is None:
            async with self._db.session() as session:
                stored = (
                    await session.execute(
                        sa.select(sa.func.max(s.trace_events.c.seq)).where(
                            s.trace_events.c.run_id == run_id
                        )
                    )
                ).scalar()
            cached = int(stored or 0)
        cached += 1
        self._seq[run_id] = cached
        return cached


class PostgresProfileRepository(_Repository):
    def __init__(self, database: Database, *, seed: dict[AgentId, AgentProfile] | None = None) -> None:
        super().__init__(database)
        self._seed = seed or {}

    async def ensure_seeded(self) -> None:
        """Escribe los perfiles iniciales si la tabla está vacía."""
        if not self._seed:
            return
        async with self._db.session() as session:
            count = (
                await session.execute(
                    sa.select(sa.func.count())
                    .select_from(s.agent_profiles)
                    .where(s.agent_profiles.c.scope == s.GLOBAL_SCOPE)
                )
            ).scalar_one()
            if count:
                return
            now = datetime.now(timezone.utc)
            await session.execute(
                sa.insert(s.agent_profiles),
                [m.profile_row(s.GLOBAL_SCOPE, profile, now) for profile in self._seed.values()],
            )

    async def defaults(self) -> dict[AgentId, AgentProfile]:
        return await self._scope(s.GLOBAL_SCOPE)

    async def effective(self, requirement_id: str) -> dict[AgentId, AgentProfile]:
        merged = await self.defaults()
        merged.update(await self._scope(requirement_id))
        return merged

    async def _scope(self, scope: str) -> dict[AgentId, AgentProfile]:
        async with self._db.session() as session:
            rows = (
                (
                    await session.execute(
                        sa.select(s.agent_profiles).where(s.agent_profiles.c.scope == scope)
                    )
                )
                .mappings()
                .all()
            )
        return {AgentId(row["agent_id"]): m.profile_from_row(row) for row in rows}

    async def save_default(self, profile: AgentProfile) -> None:
        await self._upsert(s.GLOBAL_SCOPE, profile)

    async def save_override(self, requirement_id: str, profile: AgentProfile) -> None:
        await self._upsert(requirement_id, profile)

    async def _upsert(self, scope: str, profile: AgentProfile) -> None:
        row = m.profile_row(scope, profile, datetime.now(timezone.utc))
        async with self._db.session() as session:
            statement = insert(s.agent_profiles).values(**row)
            await session.execute(
                statement.on_conflict_do_update(
                    index_elements=[s.agent_profiles.c.scope, s.agent_profiles.c.agent_id],
                    set_={k: statement.excluded[k] for k in row if k not in {"scope", "agent_id"}},
                )
            )


class PostgresIdGenerator(_Repository):
    """Identificadores legibles con el contador en la base.

    Con persistencia no vale un contador en memoria: al reiniciar el servicio volvería a
    `REQ-001` y pisaría requerimientos ya guardados. El incremento es atómico, así que dos
    procesos nunca reparten el mismo número.
    """

    async def new_id(self, prefix: str) -> str:
        async with self._db.session() as session:
            statement = insert(s.id_counters).values(prefix=prefix, value=1)
            value = (
                await session.execute(
                    statement.on_conflict_do_update(
                        index_elements=[s.id_counters.c.prefix],
                        set_={"value": s.id_counters.c.value + 1},
                    ).returning(s.id_counters.c.value)
                )
            ).scalar_one()
        return f"{prefix}-{int(value):03d}"


class PostgresAuditLog(_Repository):
    """Registro de solo anexado.

    No hay método de modificación ni de borrado: no es un descuido, es el contrato. Cada entrada
    encadena el hash de la anterior, así que alterar una fila rompe la verificación.
    """

    async def append(
        self, *, at: datetime, actor: str, action, target: str, detail: str = ""
    ) -> AuditEntry:
        async with self._db.session() as session:
            previous = (
                await session.execute(
                    sa.select(s.audit_entries.c.hash).order_by(s.audit_entries.c.seq.desc()).limit(1)
                )
            ).scalar()
            entry = AuditEntry(
                at=at,
                actor=actor,
                action=action,
                target=target,
                detail=detail,
                prev_hash=previous or GENESIS,
            )
            result = await session.execute(
                sa.insert(s.audit_entries).values(**m.audit_row(entry)).returning(s.audit_entries.c.seq)
            )
            seq = result.scalar_one()
        return AuditEntry(
            at=entry.at,
            actor=entry.actor,
            action=entry.action,
            target=entry.target,
            detail=entry.detail,
            prev_hash=entry.prev_hash,
            seq=int(seq),
        )

    async def list(
        self, *, target: str | None = None, limit: int = 200, offset: int = 0
    ) -> list[AuditEntry]:
        condition = s.audit_entries.c.target == target if target else sa.true()
        query = (
            sa.select(s.audit_entries)
            .where(condition)
            .order_by(s.audit_entries.c.seq)
            .offset(offset)
            .limit(limit)
        )
        async with self._db.session() as session:
            rows = (await session.execute(query)).mappings().all()
        return [m.audit_from_row(row) for row in rows]

    async def count(self, *, target: str | None = None) -> int:
        condition = s.audit_entries.c.target == target if target else sa.true()
        async with self._db.session() as session:
            return int(
                (
                    await session.execute(
                        sa.select(sa.func.count()).select_from(s.audit_entries).where(condition)
                    )
                ).scalar_one()
            )

    async def stored_hashes(self, limit: int = 200) -> list[str]:
        async with self._db.session() as session:
            rows = (
                (
                    await session.execute(
                        sa.select(s.audit_entries.c.hash)
                        .order_by(s.audit_entries.c.seq)
                        .limit(limit)
                    )
                )
                .scalars()
                .all()
            )
        return list(rows)
