"""Puerta única a los repositorios del cliente."""
from __future__ import annotations

import asyncio
import logging
from collections import OrderedDict

from ...domain.diff import FileDiff
from ...domain.requirement import RepoInfo
from .client import ConnectedRepo, GitClient, GitError, RepoSpec
from .workspace import Workspace

log = logging.getLogger(__name__)


class GitService:
    def __init__(self, client: GitClient | None = None, *, cache_size: int = 8) -> None:
        self._client = client or GitClient()
        self._cache_size = max(1, cache_size)
        self._diffs: OrderedDict[str, tuple[FileDiff, ...]] = OrderedDict()
        self._urls: dict[str, str] = {}
        self._diff_locks: dict[str, asyncio.Lock] = {}
        self._workspaces: dict[str, Workspace] = {}
        self._workspace_locks: dict[str, asyncio.Lock] = {}
        self.clones = 0

    async def connect(self, spec: RepoSpec) -> ConnectedRepo:
        """Conecta un repositorio y deja su diff en la caché."""
        self.clones += 1
        connected = await self._client.connect(spec)
        self._remember(connected.info, connected.files, spec.url)
        return connected

    async def diff_for(self, repo: RepoInfo) -> tuple[FileDiff, ...]:
        """Diff del cambio. Solo se clona si no está en la caché."""
        cached = self._diffs.get(repo.head_sha)
        if cached is not None:
            self._diffs.move_to_end(repo.head_sha)
            return cached

        lock = self._diff_locks.setdefault(repo.head_sha, asyncio.Lock())
        async with lock:
            cached = self._diffs.get(repo.head_sha)
            if cached is not None:
                return cached
            connected = await self.connect(self._spec_for(repo))
            if connected.info.head_sha != repo.head_sha:
                # La rama avanzó: se revisa lo que se congeló, no lo que hay ahora.
                log.warning(
                    "la rama %s avanzó desde que se conectó; se usa el diff recalculado",
                    repo.branch,
                )
            self._remember(repo, connected.files, self._url_for(repo))
            return connected.files

    async def workspace_for(self, run_id: str, repo: RepoInfo) -> Workspace:
        """Copia de trabajo de la ejecución. Una sola, compartida por sus agentes."""
        existente = self._workspaces.get(run_id)
        if existente is not None and not existente.closed:
            return existente

        lock = self._workspace_locks.setdefault(run_id, asyncio.Lock())
        async with lock:
            existente = self._workspaces.get(run_id)
            if existente is not None and not existente.closed:
                return existente
            workspace = await self._client.clone(self._url_for(repo), repo.branch)
            self.clones += 1
            self._workspaces[run_id] = workspace
            return workspace

    async def read_file(self, workspace: Workspace, sha: str, path: str) -> str:
        return await self._client.read_file(workspace, sha, path)

    async def grep(self, workspace: Workspace, sha: str, pattern: str) -> str:
        return await self._client.grep(workspace, sha, pattern)

    async def release(self, run_id: str) -> None:
        """Borra la copia de trabajo de una ejecución. Idempotente."""
        workspace = self._workspaces.pop(run_id, None)
        self._workspace_locks.pop(run_id, None)
        if workspace is not None:
            await workspace.close()

    async def release_all(self) -> None:
        """Al apagar: no se deja nada del cliente en el disco."""
        for run_id in list(self._workspaces):
            await self.release(run_id)

    def _remember(self, repo: RepoInfo, files: tuple[FileDiff, ...], url: str) -> None:
        self._diffs[repo.head_sha] = files
        self._urls[repo.head_sha] = url
        self._diffs.move_to_end(repo.head_sha)
        while len(self._diffs) > self._cache_size:
            viejo, _ = self._diffs.popitem(last=False)
            self._urls.pop(viejo, None)
            self._diff_locks.pop(viejo, None)

    def _url_for(self, repo: RepoInfo) -> str:
        """URL de clonado. La conocida al conectar manda: puede llevar host corporativo."""
        conocida = self._urls.get(repo.head_sha)
        if conocida:
            return conocida
        if not repo.html_url:
            raise GitError(f"No se sabe de dónde clonar {repo.full_name or 'el repositorio'}.")
        return repo.html_url

    def _spec_for(self, repo: RepoInfo) -> RepoSpec:
        return RepoSpec(url=self._url_for(repo), branch=repo.branch, base=repo.base)
