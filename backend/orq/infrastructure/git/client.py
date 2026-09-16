"""Cliente de git: clonar, resolver el rango y calcular el diff, desde el servidor."""
from __future__ import annotations

import asyncio
import base64
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from ...application.ports import CredentialStore, GitCredential
from ...domain.diff import FileDiff, parse_diff
from ...domain.errors import DomainError
from ...domain.requirement import RepoCommit, RepoFile, RepoInfo
from .credentials import host_of
from .workspace import Workspace

log = logging.getLogger(__name__)

#: Separador dentro de una línea de `git log`: no aparece en mensajes de commit.
UNIT = "\x1f"

PROVIDERS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"(^|\.)github\.com$"), "github"),
    (re.compile(r"(^|\.)dev\.azure\.com$|\.visualstudio\.com$"), "azure"),
    (re.compile(r"(^|\.)gitlab\."), "gitlab"),
)


class GitError(DomainError):
    """Algo falló hablando con el repositorio. El mensaje ya viene limpio de credenciales."""


@dataclass(frozen=True, slots=True)
class RepoSpec:
    """Lo que la persona pide conectar."""

    url: str
    branch: str = ""
    base: str = ""
    last_commits: int = 0


@dataclass(frozen=True, slots=True)
class ConnectedRepo:
    """Resultado de conectar: la ficha del repositorio y el diff ya leído."""

    info: RepoInfo
    files: tuple[FileDiff, ...]


@dataclass(frozen=True, slots=True)
class GitLimits:
    """Topes para que un repositorio enorme no se lleve por delante la ejecución."""

    max_files: int = 300
    max_diff_bytes: int = 4_000_000
    clone_timeout_s: float = 300.0
    command_timeout_s: float = 120.0


def provider_of(url: str) -> str:
    host = host_of(url)
    for pattern, name in PROVIDERS:
        if pattern.search(host):
            return name
    return "git"


def web_url(url: str) -> str:
    """URL para abrir el repositorio en el navegador, sin credenciales ni `.git`."""
    limpio = strip_credentials(url.strip())
    if limpio.startswith("git@"):
        host, _, path = limpio[4:].partition(":")
        limpio = f"https://{host}/{path}"
    return limpio[:-4] if limpio.endswith(".git") else limpio


def strip_credentials(text: str) -> str:
    """Quita `usuario:token@` de cualquier URL que aparezca en un texto.

    Se aplica a **todo** mensaje de error de git antes de propagarlo: git repite la URL que le
    diste, y si alguien configura la credencial dentro de la URL acabaría en la pantalla.
    """
    return re.sub(r"(https?://)[^/\s@]+@", r"\1", text)


def owner_and_name(url: str) -> tuple[str, str]:
    """Organización y repositorio a partir de la URL. Vacíos si no se reconocen."""
    ruta = web_url(url).split("://", 1)[-1]
    partes = [p for p in ruta.split("/")[1:] if p and p not in ("_git", "_apis")]
    if len(partes) >= 2:
        return partes[-2], partes[-1]
    return ("", partes[-1] if partes else "")


class GitClient:
    """Ejecuta `git` en una copia de trabajo efímera."""

    def __init__(
        self,
        *,
        credentials: CredentialStore | None = None,
        limits: GitLimits | None = None,
        clone_filter: str = "blob:none",
    ) -> None:
        self._credentials = credentials
        self._limits = limits or GitLimits()
        self._clone_filter = clone_filter

    async def connect(self, spec: RepoSpec) -> ConnectedRepo:
        """Clona, resuelve el rango y devuelve la ficha con el diff. Borra la copia al salir."""
        async with await self.clone(spec.url, spec.branch) as workspace:
            return await self.describe(workspace, spec)

    async def clone(self, url: str, branch: str = "") -> Workspace:
        """Copia de trabajo lista. **Quien la abre es responsable de cerrarla.**"""
        workspace = Workspace.create()
        try:
            await self._clone_into(workspace, url, branch)
        except BaseException:
            # También al cancelar: un `CancelledError` no puede dejar código del cliente en disco.
            await workspace.close()
            raise
        return workspace

    async def describe(self, workspace: Workspace, spec: RepoSpec) -> ConnectedRepo:
        """Ficha y diff de una copia ya clonada."""
        branch = spec.branch or await self._default_branch(workspace)
        head_sha = await self._rev_parse(workspace, branch)
        base = await self._resolve_base(workspace, spec, branch, head_sha)
        base_sha = await self._rev_parse(workspace, base)

        if base_sha == head_sha:
            raise GitError(
                "La base y la rama apuntan al mismo commit: no hay nada que comparar. "
                "Elige otra base o compara los últimos commits."
            )

        files, truncated = await self._diff(workspace, base_sha, head_sha)
        if not files:
            raise GitError("No hay diferencias entre la base y la rama elegida.")

        commits = await self._commits(workspace, base_sha, head_sha)
        url = spec.url
        owner, name = owner_and_name(url)
        html = web_url(url)
        provider = provider_of(url)
        etiqueta = (
            f"{spec.base}…{branch}"
            if spec.base
            else f"últimos {len(commits)} commit(s) de {branch}"
        )

        info = RepoInfo(
            provider=provider,
            owner=owner,
            name=name,
            full_name=f"{owner}/{name}" if owner else name,
            html_url=html,
            default_branch=await self._default_branch(workspace),
            branch=branch,
            base=spec.base or base_sha[:12],
            head_sha=head_sha,
            range_label=etiqueta,
            compare_url=_compare_url(provider, html, base_sha, head_sha),
            ahead_by=len(commits),
            commits=commits[:10],
            files=tuple(
                RepoFile(
                    path=f.path,
                    status=f.status,
                    additions=f.additions,
                    deletions=f.deletions,
                    has_patch=f.has_patch,
                )
                for f in files
            ),
            files_truncated=truncated,
            fetched_at=datetime.now(timezone.utc),
        )
        return ConnectedRepo(info=info, files=files)

    async def read_file(self, workspace: Workspace, sha: str, path: str) -> str:
        """Contenido de un archivo en un commit concreto."""
        return await self._git(workspace, "show", f"{sha}:{path}")

    async def grep(self, workspace: Workspace, sha: str, pattern: str, limit: int = 60) -> str:
        """Busca un patrón en el árbol del commit. Devuelve `archivo:línea:texto`."""
        salida = await self._git(
            workspace,
            "grep",
            "--no-color",
            "-n",
            "-I",
            "-i",
            "-e",
            pattern,
            sha,
            check=False,
        )
        lineas = [l.replace(f"{sha}:", "", 1) for l in salida.split("\n") if l.strip()]
        if len(lineas) > limit:
            lineas = lineas[:limit] + [f"… {len(lineas) - limit} coincidencia(s) más, recortadas."]
        return "\n".join(lineas) or "Sin coincidencias."

    async def list_files(self, workspace: Workspace, sha: str, limit: int = 500) -> str:
        salida = await self._git(workspace, "ls-tree", "-r", "--name-only", sha)
        rutas = [l for l in salida.split("\n") if l.strip()]
        if len(rutas) > limit:
            rutas = rutas[:limit] + [f"… {len(rutas) - limit} archivo(s) más, recortados."]
        return "\n".join(rutas)

    async def _clone_into(self, workspace: Workspace, url: str, branch: str) -> None:
        argumentos = ["clone", "--no-tags", "--quiet"]
        if self._clone_filter:
            argumentos += [f"--filter={self._clone_filter}"]
        argumentos += [url, str(workspace.path)]
        try:
            await self._git(
                workspace, *argumentos, url=url, cwd=None, timeout=self._limits.clone_timeout_s
            )
        except GitError as error:
            # No todos los servidores admiten clonado parcial. Si es eso, se reintenta entero.
            if not self._clone_filter or "filter" not in str(error).lower():
                raise
            log.info("el servidor no admite clonado parcial: se clona entero")
            await self._git(
                workspace,
                "clone",
                "--no-tags",
                "--quiet",
                url,
                str(workspace.path),
                url=url,
                cwd=None,
                timeout=self._limits.clone_timeout_s,
            )

    async def _default_branch(self, workspace: Workspace) -> str:
        salida = await self._git(
            workspace, "symbolic-ref", "--short", "refs/remotes/origin/HEAD", check=False
        )
        if salida.strip():
            return salida.strip().removeprefix("origin/")
        return (await self._git(workspace, "rev-parse", "--abbrev-ref", "HEAD")).strip()

    async def _rev_parse(self, workspace: Workspace, ref: str) -> str:
        for candidato in (ref, f"origin/{ref}"):
            salida = await self._git(workspace, "rev-parse", "--verify", f"{candidato}^{{commit}}", check=False)
            if salida.strip():
                return salida.strip()
        raise GitError(f"No existe la rama o el commit «{ref}» en el repositorio.")

    async def _resolve_base(
        self, workspace: Workspace, spec: RepoSpec, branch: str, head_sha: str
    ) -> str:
        if spec.base:
            return spec.base
        cuantos = spec.last_commits or 1
        salida = await self._git(
            workspace, "rev-parse", "--verify", f"{head_sha}~{cuantos}", check=False
        )
        if salida.strip():
            return salida.strip()
        raise GitError(
            f"La rama «{branch}» no tiene {cuantos + 1} commits para comparar. "
            "Elige una rama base."
        )

    async def _diff(
        self, workspace: Workspace, base_sha: str, head_sha: str
    ) -> tuple[tuple[FileDiff, ...], bool]:
        texto = await self._git(
            workspace,
            "diff",
            "--no-color",
            "--find-renames",
            "--unified=3",
            f"{base_sha}...{head_sha}",
        )
        recortado = False
        if len(texto) > self._limits.max_diff_bytes:
            # Se corta por un `diff --git` para no partir un hunk por la mitad.
            corte = texto.rfind("\ndiff --git ", 0, self._limits.max_diff_bytes)
            texto = texto[: corte if corte > 0 else self._limits.max_diff_bytes]
            recortado = True
        archivos = parse_diff(texto)
        if len(archivos) > self._limits.max_files:
            archivos = archivos[: self._limits.max_files]
            recortado = True
        return archivos, recortado

    async def _commits(
        self, workspace: Workspace, base_sha: str, head_sha: str
    ) -> tuple[RepoCommit, ...]:
        salida = await self._git(
            workspace,
            "log",
            f"--format=%H{UNIT}%s{UNIT}%an{UNIT}%aI",
            "-n",
            "50",
            f"{base_sha}..{head_sha}",
        )
        commits: list[RepoCommit] = []
        for linea in salida.split("\n"):
            if not linea.strip():
                continue
            partes = linea.split(UNIT)
            if len(partes) != 4:
                continue
            commits.append(
                RepoCommit(sha=partes[0], message=partes[1], author=partes[2], date=partes[3])
            )
        return tuple(commits)

    async def _git(
        self,
        workspace: Workspace,
        *args: str,
        url: str = "",
        cwd: str | None = "",
        check: bool = True,
        timeout: float | None = None,
    ) -> str:
        """Ejecuta git. `check=False` devuelve texto vacío en vez de fallar."""
        entorno = await self._env_for(url)
        proceso = await asyncio.create_subprocess_exec(
            "git",
            *args,
            cwd=(str(workspace.path) if cwd == "" else cwd),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=entorno,
        )
        try:
            salida, error = await asyncio.wait_for(
                proceso.communicate(), timeout or self._limits.command_timeout_s
            )
        except (asyncio.TimeoutError, asyncio.CancelledError):
            proceso.kill()
            await proceso.wait()
            raise
        if proceso.returncode != 0:
            if not check:
                return ""
            detalle = strip_credentials(error.decode("utf-8", "replace").strip())
            raise GitError(_friendly(detalle, args[0] if args else "git"))
        return salida.decode("utf-8", "replace")

    async def _env_for(self, url: str) -> dict[str, str]:
        """Entorno para git, con la credencial si la hay.

        El token va en `GIT_CONFIG_VALUE_0`: no aparece en la lista de procesos ni se escribe en
        `.git/config`, que es lo que pasaría si se metiera en la URL.
        """
        import os

        entorno = dict(os.environ)
        # Sin esto git espera a que alguien escriba la contraseña y el proceso se cuelga.
        entorno["GIT_TERMINAL_PROMPT"] = "0"
        entorno["GCM_INTERACTIVE"] = "never"
        entorno.pop("GIT_ASKPASS", None)
        entorno.pop("SSH_ASKPASS", None)

        credencial = await self._credential_for(url)
        if credencial is not None:
            basico = base64.b64encode(
                f"{credencial.username}:{credencial.token}".encode()
            ).decode()
            entorno["GIT_CONFIG_COUNT"] = "1"
            entorno["GIT_CONFIG_KEY_0"] = "http.extraheader"
            entorno["GIT_CONFIG_VALUE_0"] = f"Authorization: Basic {basico}"
        return entorno

    async def _credential_for(self, url: str) -> GitCredential | None:
        if not url or self._credentials is None:
            return None
        host = host_of(url)
        if not host:
            return None
        return await self._credentials.git_credential(host)


def _compare_url(provider: str, html_url: str, base_sha: str, head_sha: str) -> str:
    if provider == "github":
        return f"{html_url}/compare/{base_sha}...{head_sha}"
    if provider == "gitlab":
        return f"{html_url}/-/compare/{base_sha}...{head_sha}"
    if provider == "azure":
        return f"{html_url}/branchCompare?baseVersion=GC{base_sha}&targetVersion=GC{head_sha}"
    return html_url


_FRIENDLY: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(r"Authentication failed|could not read Username|invalid credentials", re.I),
        "El repositorio pide credenciales y la guardada no sirve. Revisa el token de ese host "
        "en Gobierno → Bóveda de secretos.",
    ),
    (
        re.compile(r"Repository not found|not found|does not exist", re.I),
        "No se encontró el repositorio. Comprueba la URL y, si es privado, que haya credencial.",
    ),
    (
        re.compile(r"Could not resolve host|unable to access|Connection timed out", re.I),
        "No se pudo contactar con el servidor del repositorio.",
    ),
)


def _friendly(detalle: str, orden: str) -> str:
    for pattern, mensaje in _FRIENDLY:
        if pattern.search(detalle):
            return mensaje
    return f"git {orden} falló: {detalle[:300]}" if detalle else f"git {orden} falló."
