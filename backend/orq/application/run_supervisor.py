"""Supervisor de ejecuciones en curso."""
from __future__ import annotations

import asyncio
import logging

from ..domain.enums import AgentId, RunStatus
from ..domain.plan import Plan
from ..domain.profiles import AgentProfile
from ..domain.requirement import Requirement
from ..domain.run import Run
from .ports import Clock, RunRepository
from .run_executor import RunExecutor

log = logging.getLogger(__name__)


class RunSupervisor:
    def __init__(self, *, executor: RunExecutor, runs: RunRepository, clock: Clock) -> None:
        self._executor = executor
        self._runs = runs
        self._clock = clock
        self._tasks: dict[str, asyncio.Task[Run]] = {}
        self._cancellations: dict[str, asyncio.Event] = {}

    def start(
        self,
        *,
        requirement: Requirement,
        plan: Plan,
        run: Run,
        profiles: dict[AgentId, AgentProfile],
    ) -> asyncio.Task[Run]:
        """Lanza la ejecución en segundo plano y devuelve de inmediato."""
        if run.id in self._tasks and not self._tasks[run.id].done():
            return self._tasks[run.id]
        self._prune()

        cancellation = asyncio.Event()
        self._cancellations[run.id] = cancellation
        task = asyncio.create_task(
            self._guarded(requirement, plan, run, profiles, cancellation), name=f"run:{run.id}"
        )
        self._tasks[run.id] = task
        return task

    async def _guarded(
        self,
        requirement: Requirement,
        plan: Plan,
        run: Run,
        profiles: dict[AgentId, AgentProfile],
        cancellation: asyncio.Event,
    ) -> Run:
        """Nada que ocurra dentro puede dejar la ejecución en un estado ambiguo."""
        try:
            return await self._executor.execute(
                requirement=requirement,
                plan=plan,
                run=run,
                profiles=profiles,
                cancellation=cancellation,
            )
        except asyncio.CancelledError:
            run.status = RunStatus.CANCELADA
            run.cancelled_at = self._clock.now()
            await self._runs.save(run)
            raise
        except Exception as exc:  # fallo del motor, no de un agente
            log.exception("la ejecución %s terminó en error", run.id)
            run.status = RunStatus.FALLIDA
            run.error = str(exc)
            run.finished_at = self._clock.now()
            await self._runs.save(run)
            return run
        finally:
            self._cancellations.pop(run.id, None)

    def is_running(self, run_id: str) -> bool:
        task = self._tasks.get(run_id)
        return task is not None and not task.done()

    def cancel(self, run_id: str) -> bool:
        """Pide la cancelación. El motor corta las llamadas en curso y cierra la ejecución."""
        cancellation = self._cancellations.get(run_id)
        if cancellation is None or not self.is_running(run_id):
            return False
        cancellation.set()
        return True

    async def wait(self, run_id: str, *, timeout: float | None = None) -> Run | None:
        """Espera a que termine. Devuelve `None` si esa ejecución no está en este proceso."""
        task = self._tasks.get(run_id)
        if task is None:
            return None
        try:
            return await asyncio.wait_for(asyncio.shield(task), timeout=timeout)
        except asyncio.CancelledError:
            return await self._runs.get(run_id)

    def _prune(self) -> None:
        """Suelta las ejecuciones ya terminadas para no acumularlas en memoria."""
        for run_id in [i for i, t in self._tasks.items() if t.done()]:
            del self._tasks[run_id]

    async def drain(self, *, timeout: float = 30.0) -> None:
        """Espera a las ejecuciones vivas. Se llama al apagar el servicio."""
        pending = [t for t in self._tasks.values() if not t.done()]
        if not pending:
            return
        await asyncio.wait(pending, timeout=timeout)
