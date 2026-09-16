"""Análisis determinista del repositorio conectado. Implementa el puerto `RepoAnalyzer`."""
from __future__ import annotations

import logging

from ...application.ports import RepoAnalysis
from ...domain.code_review import BlobUrl, analyze_diff
from ...domain.diff import change_map
from ...domain.requirement import RepoInfo
from .client import RepoSpec
from .service import GitService

log = logging.getLogger(__name__)


class GitRepoConnector:
    """Implementa el puerto `RepoConnector`."""

    def __init__(self, service: GitService) -> None:
        self._service = service

    async def connect(
        self, *, url: str, branch: str = "", base: str = "", last_commits: int = 0
    ) -> RepoInfo:
        connected = await self._service.connect(
            RepoSpec(url=url, branch=branch, base=base, last_commits=last_commits)
        )
        return connected.info


class GitRepoAnalyzer:
    def __init__(self, service: GitService) -> None:
        self._service = service

    async def analyze(
        self, *, run_id: str, repo: RepoInfo, criteria: tuple[str, ...] = ()
    ) -> RepoAnalysis:
        files = await self._service.diff_for(repo)
        enlace = BlobUrl(repo.provider, repo.html_url, repo.head_sha)
        return RepoAnalysis(
            change_map=change_map(files, criteria),
            findings=analyze_diff(files, blob_url=enlace, criteria_count=len(criteria)),
            files=len(files),
            truncated=repo.files_truncated,
        )

    async def release(self, run_id: str) -> None:
        await self._service.release(run_id)
