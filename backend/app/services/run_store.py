"""Almacén de ejecuciones y sus eventos.

En memoria para la operación normal y, si se indica una carpeta, persistido en JSON
(un archivo por ejecución) para poder reabrir trazas después de reiniciar el servidor.
"""
from __future__ import annotations

import json
import logging
import os
from collections import OrderedDict
from pathlib import Path
from typing import Optional

from ..models import Event, RunStatus, RunSummary, SymbolResult, now

log = logging.getLogger(__name__)


class RunStore:
    def __init__(self, max_runs: int = 50, persist_dir: Optional[str] = None) -> None:
        self._runs: "OrderedDict[str, RunSummary]" = OrderedDict()
        self._events: dict[str, list[Event]] = {}
        self._seq: dict[str, int] = {}
        self._max_runs = max_runs
        self._dir: Optional[Path] = Path(persist_dir) if persist_dir else None
        if self._dir:
            try:
                self._dir.mkdir(parents=True, exist_ok=True)
                self._load()
            except OSError as e:
                log.warning("No se pudo usar la carpeta de ejecuciones %s: %s (solo memoria)", self._dir, e)
                self._dir = None

    # ------------------------------------------------------------- persistencia
    def _load(self) -> None:
        assert self._dir is not None
        files = sorted(self._dir.glob("run_*.json"), key=lambda p: p.stat().st_mtime)[-self._max_runs :]
        for path in files:
            try:
                with path.open(encoding="utf-8") as fh:
                    data = json.load(fh)
                run = RunSummary.model_validate(data["run"])
                events = [Event.model_validate(e) for e in data.get("events", [])]
            except Exception as e:  # archivo corrupto o de una versión anterior: se ignora
                log.warning("Ejecución ignorada (%s): %s", path.name, e)
                continue
            self._runs[run.run_id] = run
            self._events[run.run_id] = events
            self._seq[run.run_id] = max((e.seq for e in events), default=0)
        if files:
            log.info("Cargadas %d ejecuciones desde %s", len(self._runs), self._dir)

    def save(self, run_id: str) -> None:
        if not self._dir or run_id not in self._runs:
            return
        path = self._dir / f"{run_id}.json"
        tmp = path.with_suffix(".json.tmp")
        payload = {
            "run": self._runs[run_id].model_dump(mode="json"),
            "events": [e.model_dump(mode="json") for e in self._events.get(run_id, [])],
        }
        try:
            with tmp.open("w", encoding="utf-8") as fh:
                json.dump(payload, fh, ensure_ascii=False)
            os.replace(tmp, path)
        except OSError as e:
            log.warning("No se pudo guardar la ejecución %s: %s", run_id, e)

    def _delete_file(self, run_id: str) -> None:
        if self._dir:
            try:
                (self._dir / f"{run_id}.json").unlink(missing_ok=True)
            except OSError:
                pass

    # --------------------------------------------------------------- memoria
    def create(self, run: RunSummary) -> None:
        self._runs[run.run_id] = run
        self._events[run.run_id] = []
        self._seq[run.run_id] = 0
        while len(self._runs) > self._max_runs:
            old_id, _ = self._runs.popitem(last=False)
            self._events.pop(old_id, None)
            self._seq.pop(old_id, None)
            self._delete_file(old_id)

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
            self.save(run_id)

    def set_result(self, run_id: str, result: SymbolResult) -> None:
        self._runs[run_id].results[result.symbol] = result
