"""Almacén en memoria de ejecuciones y sus eventos (suficiente para una demo)."""
from __future__ import annotations

from collections import OrderedDict
from typing import Optional

from ..models import Event, RunStatus, RunSummary, SymbolResult, now


class RunStore:
    def __init__(self, max_runs: int = 50) -> None:
        self._runs: "OrderedDict[str, RunSummary]" = OrderedDict()
        self._events: dict[str, list[Event]] = {}
        self._seq: dict[str, int] = {}
        self._max_runs = max_runs

    def create(self, run: RunSummary) -> None:
        self._runs[run.run_id] = run
        self._events[run.run_id] = []
        self._seq[run.run_id] = 0
        while len(self._runs) > self._max_runs:
            old_id, _ = self._runs.popitem(last=False)
            self._events.pop(old_id, None)
            self._seq.pop(old_id, None)

    def get(self, run_id: str) -> Optional[RunSummary]:
        return self._runs.get(run_id)

    def list(self) -> list[RunSummary]:
        return list(reversed(self._runs.values()))

    def next_seq(self, run_id: str) -> int:
        self._seq[run_id] = self._seq.get(run_id, 0) + 1
        return self._seq[run_id]

    def append_event(self, event: Event) -> None:
        self._events.setdefault(event.run_id, []).append(event)

    def events(self, run_id: str, after_seq: int = 0) -> list[Event]:
        return [e for e in self._events.get(run_id, []) if e.seq > after_seq]

    def set_status(self, run_id: str, status: RunStatus) -> None:
        run = self._runs[run_id]
        run.status = status
        if status in (RunStatus.COMPLETED, RunStatus.FAILED):
            run.finished_at = now()

    def set_result(self, run_id: str, result: SymbolResult) -> None:
        self._runs[run_id].results[result.symbol] = result
