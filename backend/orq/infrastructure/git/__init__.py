"""Acceso a los repositorios del cliente. Solo este paquete ejecuta `git`."""
from __future__ import annotations

from .client import (
    ConnectedRepo,
    GitClient,
    GitError,
    GitLimits,
    RepoSpec,
    owner_and_name,
    provider_of,
    strip_credentials,
    web_url,
)
from .analysis import GitRepoAnalyzer, GitRepoConnector
from .credentials import ConfiguredCredentialStore, host_of, parse_tokens
from .service import GitService
from .workspace import Workspace, clean_leftovers, leftovers

__all__ = [
    "ConfiguredCredentialStore",
    "ConnectedRepo",
    "GitClient",
    "GitError",
    "GitRepoAnalyzer",
    "GitRepoConnector",
    "GitLimits",
    "GitService",
    "RepoSpec",
    "Workspace",
    "clean_leftovers",
    "host_of",
    "leftovers",
    "owner_and_name",
    "parse_tokens",
    "provider_of",
    "strip_credentials",
    "web_url",
]
