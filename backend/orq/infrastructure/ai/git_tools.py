"""Herramientas del agente Código sobre el repositorio conectado."""
from __future__ import annotations

import logging
from typing import Any

from ...application.ports import RequirementRepository, RunRepository, ToolSpec
from ...domain.agents import AGENTS
from ...domain.enums import AgentId
from ...domain.errors import ToolNotAllowedError
from ...domain.requirement import RepoInfo
from ..git import GitError, GitService

log = logging.getLogger(__name__)

#: Tope de caracteres de un diff devuelto de golpe. Más que esto no cabe en el contexto y además
#: dispara el coste: el agente pide archivo por archivo.
MAX_DIFF_CHARS = 60_000
MAX_FILE_CHARS = 40_000


SPECS: dict[str, ToolSpec] = {
    "git_diff": ToolSpec(
        name="git_diff",
        description=(
            "Diff del cambio revisado. Sin argumentos devuelve el diff completo (recortado si es "
            "muy grande); con «file», solo el de ese archivo."
        ),
        input_schema={
            "type": "object",
            "properties": {"file": {"type": "string", "description": "Ruta del archivo"}},
            "additionalProperties": False,
        },
    ),
    "list_files": ToolSpec(
        name="list_files",
        description="Archivos que toca el cambio, con su estado y cuántas líneas se añaden y quitan.",
        input_schema={"type": "object", "properties": {}, "additionalProperties": False},
    ),
    "read_file": ToolSpec(
        name="read_file",
        description=(
            "Contenido completo de un archivo en el commit revisado. Sirve para ver el contexto "
            "que el diff no enseña."
        ),
        input_schema={
            "type": "object",
            "properties": {"path": {"type": "string", "description": "Ruta del archivo"}},
            "required": ["path"],
            "additionalProperties": False,
        },
    ),
    "search_code": ToolSpec(
        name="search_code",
        description=(
            "Busca un texto o expresión regular en todo el repositorio en el commit revisado. "
            "Devuelve archivo, línea y el texto encontrado."
        ),
        input_schema={
            "type": "object",
            "properties": {"pattern": {"type": "string", "description": "Texto o regex"}},
            "required": ["pattern"],
            "additionalProperties": False,
        },
    ),
}


class GitToolRegistry:
    """Implementa el puerto `ToolRegistry` con el repositorio de la ejecución."""

    def __init__(
        self,
        *,
        git: GitService,
        runs: RunRepository,
        requirements: RequirementRepository,
    ) -> None:
        self._git = git
        self._runs = runs
        self._requirements = requirements

    def specs_for(self, agent_id: AgentId) -> tuple[ToolSpec, ...]:
        """Solo las que el agente declara y aquí están implementadas."""
        return tuple(SPECS[name] for name in AGENTS[agent_id].tools if name in SPECS)

    async def execute(
        self, agent_id: AgentId, tool: str, arguments: dict[str, Any], *, run_id: str = ""
    ) -> str:
        if tool not in AGENTS[agent_id].tools:
            raise ToolNotAllowedError(
                f"{AGENTS[agent_id].label} no tiene autorizada la herramienta «{tool}»."
            )
        if tool not in SPECS:
            raise ToolNotAllowedError(f"No hay ninguna implementación de «{tool}» registrada.")

        repo = await self._repo_for(run_id)
        if repo is None:
            return (
                "No hay repositorio conectado en este requerimiento, así que no se puede leer el "
                "código. Trabaja con lo que haya en el contexto y dilo en tu informe."
            )

        try:
            if tool == "git_diff":
                return await self._diff(repo, str(arguments.get("file") or ""))
            if tool == "list_files":
                return self._files(repo)
            if tool == "read_file":
                return await self._read(run_id, repo, str(arguments.get("path") or ""))
            if tool == "search_code":
                return await self._search(run_id, repo, str(arguments.get("pattern") or ""))
        except GitError as error:
            # Un fallo de la herramienta no tumba al agente: se le cuenta y sigue con lo que tiene.
            log.warning("la herramienta %s falló: %s", tool, error)
            return f"No se pudo ejecutar «{tool}»: {error}"
        raise ToolNotAllowedError(f"No hay ninguna implementación de «{tool}» registrada.")

    async def _repo_for(self, run_id: str) -> RepoInfo | None:
        if not run_id:
            return None
        run = await self._runs.get(run_id)
        if run is None:
            return None
        requirement = await self._requirements.get(run.requirement_id)
        return requirement.repo if requirement is not None else None

    async def _diff(self, repo: RepoInfo, file: str) -> str:
        files = await self._git.diff_for(repo)
        if file:
            encontrado = next((f for f in files if f.path == file), None)
            if encontrado is None:
                return f"«{file}» no está entre los archivos del cambio."
            return encontrado.patch or "El archivo no tiene diff (binario o demasiado grande)."
        texto = "\n".join(f"--- {f.path}\n{f.patch}" for f in files if f.has_patch)
        if len(texto) > MAX_DIFF_CHARS:
            return (
                texto[:MAX_DIFF_CHARS]
                + f"\n… diff recortado. Pide archivo por archivo con git_diff(file=…)."
            )
        return texto or "El cambio no tiene diff legible."

    def _files(self, repo: RepoInfo) -> str:
        if not repo.files:
            return "El cambio no tiene archivos."
        lineas = [
            f"{f.status.value:9s} +{f.additions:<5} -{f.deletions:<5} {f.path}"
            for f in repo.files
        ]
        if repo.files_truncated:
            lineas.append("… la lista está recortada: el cambio tiene más archivos.")
        return "\n".join(lineas)

    async def _read(self, run_id: str, repo: RepoInfo, path: str) -> str:
        if not path:
            return "Falta la ruta del archivo."
        workspace = await self._git.workspace_for(run_id, repo)
        contenido = await self._git.read_file(workspace, repo.head_sha, path)
        if len(contenido) > MAX_FILE_CHARS:
            return contenido[:MAX_FILE_CHARS] + "\n… archivo recortado."
        return contenido

    async def _search(self, run_id: str, repo: RepoInfo, pattern: str) -> str:
        if not pattern:
            return "Falta el patrón de búsqueda."
        workspace = await self._git.workspace_for(run_id, repo)
        return await self._git.grep(workspace, repo.head_sha, pattern)
