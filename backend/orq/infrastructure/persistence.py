"""Persistencia en memoria (pruebas y arranque sin base de datos)."""
from __future__ import annotations

from datetime import datetime

from ..domain.audit import GENESIS, AuditAction, AuditEntry
from ..domain.enums import AgentId
from ..domain.plan import Plan
from ..domain.profiles import AgentProfile
from ..domain.requirement import Requirement
from ..domain.run import Run, TraceEvent


class InMemoryRequirementRepository:
    def __init__(self) -> None:
        self._items: dict[str, Requirement] = {}

    async def add(self, requirement: Requirement) -> None:
        self._items[requirement.id] = requirement

    async def get(self, requirement_id: str) -> Requirement | None:
        return self._items.get(requirement_id)

    async def save(self, requirement: Requirement) -> None:
        self._items[requirement.id] = requirement

    async def list(self, *, limit: int | None = None, offset: int = 0) -> list[Requirement]:
        items = sorted(self._items.values(), key=lambda r: r.created_at, reverse=True)
        return items[offset : offset + limit] if limit is not None else items[offset:]

    async def count(self) -> int:
        return len(self._items)


class InMemoryPlanRepository:
    def __init__(self) -> None:
        self._items: dict[str, Plan] = {}

    async def get(self, requirement_id: str) -> Plan | None:
        return self._items.get(requirement_id)

    async def save(self, requirement_id: str, plan: Plan) -> None:
        self._items[requirement_id] = plan


class InMemoryRunRepository:
    def __init__(self) -> None:
        self._runs: dict[str, Run] = {}
        self._events: dict[str, list[TraceEvent]] = {}
        self._seq: dict[str, int] = {}

    async def add(self, run: Run) -> None:
        self._runs[run.id] = run
        self._events.setdefault(run.id, [])

    async def get(self, run_id: str) -> Run | None:
        return self._runs.get(run_id)

    async def save(self, run: Run) -> None:
        self._runs[run.id] = run

    async def list_for_requirement(
        self, requirement_id: str, *, limit: int | None = None, offset: int = 0
    ) -> list[Run]:
        runs = [r for r in self._runs.values() if r.requirement_id == requirement_id]
        runs.sort(key=lambda r: r.started_at, reverse=True)
        return runs[offset : offset + limit] if limit is not None else runs[offset:]

    async def count_for_requirement(self, requirement_id: str) -> int:
        return len([r for r in self._runs.values() if r.requirement_id == requirement_id])

    async def list_unfinished(self) -> list[Run]:
        """Ejecuciones que quedaron en curso, normalmente por una caída del servicio."""
        return [r for r in self._runs.values() if not r.is_finished]

    async def append_event(self, event: TraceEvent) -> None:
        self._events.setdefault(event.run_id, []).append(event)

    async def events(self, run_id: str, *, after_seq: int = 0) -> list[TraceEvent]:
        return [e for e in self._events.get(run_id, []) if e.seq > after_seq]

    async def next_seq(self, run_id: str) -> int:
        seq = self._seq.get(run_id, 0) + 1
        self._seq[run_id] = seq
        return seq


class InMemoryProfileRepository:
    """Perfiles globales y ajustes por requerimiento.

    Los ajustes por requerimiento se aplican al momento; cambiar el perfil **predeterminado**
    tendrá que pasar por control de cambios (ORQ-21), que todavía no existe.
    """

    def __init__(self, defaults: dict[AgentId, AgentProfile]) -> None:
        self._defaults = dict(defaults)
        self._overrides: dict[str, dict[AgentId, AgentProfile]] = {}

    async def defaults(self) -> dict[AgentId, AgentProfile]:
        return dict(self._defaults)

    async def effective(self, requirement_id: str) -> dict[AgentId, AgentProfile]:
        merged = dict(self._defaults)
        merged.update(self._overrides.get(requirement_id, {}))
        return merged

    async def save_default(self, profile: AgentProfile) -> None:
        self._defaults[profile.agent_id] = profile

    async def save_override(self, requirement_id: str, profile: AgentProfile) -> None:
        self._overrides.setdefault(requirement_id, {})[profile.agent_id] = profile


class InMemoryAuditLog:
    """Auditoría encadenada en memoria. Mismo contrato que la de base de datos: solo anexa."""

    def __init__(self) -> None:
        self._entries: list[AuditEntry] = []

    async def append(
        self, *, at: datetime, actor: str, action: AuditAction, target: str, detail: str = ""
    ) -> AuditEntry:
        previous = self._entries[-1].hash if self._entries else GENESIS
        entry = AuditEntry(
            at=at,
            actor=actor,
            action=action,
            target=target,
            detail=detail,
            prev_hash=previous,
            seq=len(self._entries) + 1,
        )
        self._entries.append(entry)
        return entry

    async def list(
        self, *, target: str | None = None, limit: int = 200, offset: int = 0
    ) -> list[AuditEntry]:
        entries = [e for e in self._entries if target is None or e.target == target]
        return entries[offset : offset + limit]

    async def count(self, *, target: str | None = None) -> int:
        return len([e for e in self._entries if target is None or e.target == target])

    async def stored_hashes(self, limit: int = 200) -> list[str]:
        return [e.hash for e in self._entries[:limit]]
