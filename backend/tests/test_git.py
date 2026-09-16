"""Repositorios git de verdad: diff, mapa del cambio, caché y limpieza (ORQ-22).

No hay dobles del cliente de git: las pruebas crean un repositorio local con commits reales y lo
clonan. Es lo único que demuestra que el diff, los números de línea y el `head_sha` son correctos,
que es de lo que depende que un hallazgo apunte a una línea que existe.
"""
from __future__ import annotations

import asyncio
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

from orq.application.ports import GitCredential
from orq.application.use_cases import (
    ConnectRepoCommand,
    CreateRequirementCommand,
    NewAttachment,
    StartRunCommand,
)
from orq.domain.code_review import BlobUrl, analyze_diff
from orq.domain.diff import added_lines, change_map, parse_diff, symbols_of
from orq.domain.enums import (
    AgentId,
    AttachmentKind,
    FileStatus,
    PhiClassification,
    RunStatus,
    Severity,
)
from orq.infrastructure.git import (
    GitClient,
    GitError,
    GitRepoAnalyzer,
    GitRepoConnector,
    GitService,
    RepoSpec,
    Workspace,
    host_of,
    leftovers,
    owner_and_name,
    parse_tokens,
    provider_of,
    strip_credentials,
    web_url,
)
from orq.infrastructure.ai.git_tools import GitToolRegistry

from .conftest import make_container, run_async

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git no está instalado")

ORIGINAL = """def conciliar(pago):
    return registrar(pago)
"""

MODIFICADO = '''API_KEY = "supersecreto12345"


def conciliar(pago):
    """Concilia el pago del portal aunque llegue fuera de horario."""
    # TODO: revisar el cierre de caja
    return registrar(pago, fuera_de_horario=True)


def cerrar_caja(dia):
    return dia
'''

SQL = "DELETE FROM conciliacion;\nSELECT * FROM pagos;\n"


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, check=True
    ).stdout


@pytest.fixture(scope="module")
def origen(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Repositorio local con dos ramas y un cambio conocido."""
    path = tmp_path_factory.mktemp("origen")
    _git(path, "init", "-q", "-b", "main")
    _git(path, "config", "user.email", "demo@ejemplo.org")
    _git(path, "config", "user.name", "Demo")
    (path / "src").mkdir()
    (path / "src" / "pagos.py").write_text(ORIGINAL, encoding="utf-8")
    _git(path, "add", "-A")
    _git(path, "commit", "-qm", "inicial")

    _git(path, "checkout", "-qb", "feature/conciliacion")
    (path / "src" / "pagos.py").write_text(MODIFICADO, encoding="utf-8")
    (path / "db").mkdir()
    (path / "db" / "limpieza.sql").write_text(SQL, encoding="utf-8")
    _git(path, "add", "-A")
    _git(path, "commit", "-qm", "conciliacion fuera de horario")
    return path


@pytest.fixture
def spec(origen: Path) -> RepoSpec:
    return RepoSpec(url=origen.as_uri(), branch="feature/conciliacion", base="main")


def test_the_diff_is_read_with_real_line_numbers(spec: RepoSpec) -> None:
    conectado = run_async(GitClient().connect(spec))
    pagos = next(f for f in conectado.files if f.path.endswith("pagos.py"))

    numeros = {l.line: l.text for l in added_lines(pagos.patch)}

    # La credencial literal está en la primera línea del archivo nuevo, y ahí tiene que apuntar.
    assert numeros[1].startswith("API_KEY")
    assert all(n >= 1 for n in numeros)
    assert conectado.info.head_sha and len(conectado.info.head_sha) == 40


def test_statuses_and_counts_come_from_the_diff(spec: RepoSpec) -> None:
    conectado = run_async(GitClient().connect(spec))
    por_ruta = {f.path: f for f in conectado.files}

    assert por_ruta["db/limpieza.sql"].status is FileStatus.ADDED
    assert por_ruta["src/pagos.py"].status is FileStatus.MODIFIED
    assert por_ruta["src/pagos.py"].additions > por_ruta["src/pagos.py"].deletions
    assert conectado.info.ahead_by == 1
    assert conectado.info.commits[0].message == "conciliacion fuera de horario"


def test_a_missing_branch_says_so(origen: Path) -> None:
    with pytest.raises(GitError) as error:
        run_async(GitClient().connect(RepoSpec(url=origen.as_uri(), branch="no-existe")))

    assert "no-existe" in str(error.value)


def test_comparing_a_branch_with_itself_is_refused(origen: Path) -> None:
    with pytest.raises(GitError) as error:
        run_async(
            GitClient().connect(RepoSpec(url=origen.as_uri(), branch="main", base="main"))
        )

    assert "mismo commit" in str(error.value)


def test_every_finding_points_to_a_line_that_exists(spec: RepoSpec, origen: Path) -> None:
    """El criterio de la tarea: los enlaces se resuelven contra el repositorio."""
    conectado = run_async(GitClient().connect(spec))
    findings = analyze_diff(conectado.files, blob_url=BlobUrl("github", "https://x/y", conectado.info.head_sha))

    con_linea = [f for f in findings if f.file and f.line]
    assert con_linea, "las reglas no encontraron nada con archivo y línea"

    for finding in con_linea:
        contenido = _git(origen, "show", f"{conectado.info.head_sha}:{finding.file}").split("\n")
        assert 1 <= finding.line <= len(contenido), (
            f"{finding.title} apunta a {finding.file}:{finding.line} y el archivo tiene "
            f"{len(contenido)} líneas"
        )
        # Y además la línea es la que la regla dice haber encontrado.
        assert contenido[finding.line - 1].strip()


def test_the_link_is_pinned_to_the_reviewed_commit(spec: RepoSpec) -> None:
    conectado = run_async(GitClient().connect(spec))
    sha = conectado.info.head_sha
    enlace = BlobUrl("github", "https://github.com/acme/portal", sha)

    assert enlace("src/pagos.py", 1) == f"https://github.com/acme/portal/blob/{sha}/src/pagos.py#L1"
    assert "GC" + sha in BlobUrl("azure", "https://dev.azure.com/acme/_git/portal", sha)("a.py")
    assert BlobUrl("git", "https://interno/acme/portal", sha)("a.py") == ""  # sin plantilla, sin enlace


def test_the_deterministic_rules_find_what_is_there(spec: RepoSpec) -> None:
    conectado = run_async(GitClient().connect(spec))
    findings = analyze_diff(conectado.files)
    titulos = {f.title for f in findings}

    assert "Posible credencial escrita en el código" in titulos
    assert "DELETE sin WHERE" in titulos
    assert "TODO/FIXME añadido" in titulos
    assert "Cambio de código sin pruebas" in titulos
    criticos = [f for f in findings if f.severity is Severity.CRITICA]
    assert criticos and criticos[0].source is AgentId.CODE
    assert any(f.source is AgentId.SQL for f in findings)


def test_the_change_map_names_the_new_symbols(spec: RepoSpec) -> None:
    conectado = run_async(GitClient().connect(spec))
    pagos = next(f for f in conectado.files if f.path.endswith("pagos.py"))

    assert "cerrar_caja" in symbols_of(pagos)


def test_the_change_map_links_files_to_acceptance_criteria(spec: RepoSpec) -> None:
    conectado = run_async(GitClient().connect(spec))
    criterios = (
        "El pago se concilia aunque llegue fuera de horario",
        "El informe mensual de nóminas no cambia",
    )

    mapa = {e.file: e for e in change_map(conectado.files, criterios)}

    assert 0 in mapa["src/pagos.py"].criteria  # habla de pagos y conciliación
    assert 1 not in mapa["src/pagos.py"].criteria  # nada que ver con nóminas


def test_two_agents_share_the_diff_without_cloning_again(spec: RepoSpec) -> None:
    """Criterio de la tarea: la etapa intermedia no clona cinco veces."""
    servicio = GitService(GitClient())

    async def escenario() -> tuple[int, int]:
        conectado = await servicio.connect(spec)
        tras_conectar = servicio.clones
        # Cinco agentes pidiendo el diff a la vez, como en la oleada intermedia.
        resultados = await asyncio.gather(
            *(servicio.diff_for(conectado.info) for _ in range(5))
        )
        assert all(r == conectado.files for r in resultados)
        return tras_conectar, servicio.clones

    tras_conectar, al_final = run_async(escenario())

    assert tras_conectar == 1
    assert al_final == 1, "alguien volvió a clonar teniendo el diff en la caché"


def test_the_working_copy_is_removed_when_the_run_fails(spec: RepoSpec) -> None:
    servicio = GitService(GitClient())

    async def escenario() -> Path:
        conectado = await servicio.connect(spec)
        workspace = await servicio.workspace_for("RUN-001", conectado.info)
        path = workspace.path
        assert path.exists()
        try:
            raise RuntimeError("la ejecución revienta")
        except RuntimeError:
            await servicio.release("RUN-001")
        return path

    path = run_async(escenario())

    assert not path.exists()


def test_the_working_copy_is_removed_when_the_clone_is_cancelled(origen: Path) -> None:
    """Cancelar a media clonación no puede dejar código del cliente en el disco."""

    class Lento(GitClient):
        async def _clone_into(self, workspace: Workspace, url: str, branch: str) -> None:  # type: ignore[override]
            (workspace.path / "algo.txt").write_text("contenido", encoding="utf-8")
            raise asyncio.CancelledError

    async def escenario() -> int:
        antes = len(leftovers())
        with pytest.raises(asyncio.CancelledError):
            await Lento().clone(origen.as_uri())
        return len(leftovers()) - antes

    assert run_async(escenario()) == 0


def test_releasing_twice_is_not_an_error(spec: RepoSpec) -> None:
    servicio = GitService(GitClient())

    async def escenario() -> None:
        conectado = await servicio.connect(spec)
        await servicio.workspace_for("RUN-002", conectado.info)
        await servicio.release("RUN-002")
        await servicio.release("RUN-002")

    run_async(escenario())


def test_a_credential_never_prints_its_token() -> None:
    credencial = GitCredential(username="x-access-token", token="ghp_secretisimo")

    assert "ghp_secretisimo" not in repr(credencial)
    assert "ghp_secretisimo" not in str(credencial)
    assert "ghp_secretisimo" not in f"{credencial}"
    assert "***" in repr(credencial)


def test_tokens_are_read_per_host() -> None:
    credenciales = parse_tokens("github.com=ghp_uno, dev.azure.com=usuario:pat_dos, roto")

    assert credenciales["github.com"].token == "ghp_uno"
    assert credenciales["github.com"].username == "x-access-token"
    assert credenciales["dev.azure.com"].username == "usuario"
    assert "roto" not in credenciales


def test_the_token_goes_in_the_environment_not_the_command_line(origen: Path) -> None:
    """Si el token fuera en la URL acabaría en la lista de procesos y en `.git/config`."""

    class Store:
        async def git_credential(self, host: str) -> GitCredential:
            return GitCredential(username="u", token="pat_secretisimo")

    cliente = GitClient(credentials=Store())
    entorno = run_async(cliente._env_for("https://dev.azure.com/acme/_git/portal"))

    assert entorno["GIT_CONFIG_KEY_0"] == "http.extraheader"
    assert "pat_secretisimo" not in entorno["GIT_CONFIG_VALUE_0"]  # va en base64
    assert entorno["GIT_TERMINAL_PROMPT"] == "0"  # nunca se queda esperando una contraseña


def test_an_error_message_never_repeats_a_credential() -> None:
    sucio = "fatal: unable to access 'https://usuario:ghp_secreto@github.com/acme/portal.git/'"

    limpio = strip_credentials(sucio)

    assert "ghp_secreto" not in limpio
    assert "github.com/acme/portal" in limpio


def test_hosts_and_providers_are_recognised() -> None:
    assert host_of("git@github.com:acme/portal.git") == "github.com"
    assert host_of("https://dev.azure.com/acme/_git/portal") == "dev.azure.com"
    assert provider_of("https://github.com/acme/portal.git") == "github"
    assert provider_of("https://dev.azure.com/acme/_git/portal") == "azure"
    assert provider_of("https://git.interno.acme.es/portal.git") == "git"
    assert web_url("git@github.com:acme/portal.git") == "https://github.com/acme/portal"
    assert owner_and_name("https://github.com/acme/portal.git") == ("acme", "portal")


def test_a_run_reviews_the_real_change(settings, spec: RepoSpec, origen: Path) -> None:
    """La ejecución completa con repositorio conectado: entregables anclados en el diff."""
    servicio = GitService(GitClient())
    container = make_container(settings)
    container.supervisor._executor._repos = GitRepoAnalyzer(servicio)  # type: ignore[attr-defined]

    requirement = run_async(
        container.create_requirement()(
            CreateRequirementCommand(
                title="Conciliación fuera de horario",
                description="El pago no se concilia cuando llega fuera de horario.",
                owner="ana",
                acceptance_criteria=("El pago se concilia aunque llegue fuera de horario",),
                phi=PhiClassification.NO,
                # Sin plantilla el plan sale bloqueado y no llegaríamos a ejecutar.
                attachments=(
                    NewAttachment(kind=AttachmentKind.VTR_TEMPLATE, name="VTR-modelo.docx"),
                ),
            )
        )
    )
    requirement = run_async(
        ConnectRepoUseCase(container, servicio)(
            ConnectRepoCommand(
                requirement_id=requirement.id, url=spec.url, branch=spec.branch, base=spec.base
            )
        )
    )
    assert requirement.repo is not None
    assert requirement.repo.head_sha
    assert len(requirement.repo.files) == 2

    run_async(container.suggest_plan()(requirement.id))
    run = run_async(
        container.start_run()(
            StartRunCommand(requirement_id=requirement.id, started_by="ana", wait=True)
        )
    )
    assert run.status is RunStatus.COMPLETADA

    from orq.application.deliverables import build_deliverables

    code = build_deliverables(run).code
    assert code is not None
    # El mapa del cambio es el real, no lo que dijera el modelo simulado.
    assert {e.file for e in code.change_map} == {"src/pagos.py", "db/limpieza.sql"}
    titulos = {f.title for f in code.findings}
    assert "Posible credencial escrita en el código" in titulos

    # Y la copia de trabajo no sobrevive a la ejecución.
    run_async(servicio.release_all())


def ConnectRepoUseCase(container: Any, servicio: GitService) -> Any:
    """El contenedor de pruebas no trae git: se le enchufa el conector aquí."""
    from orq.application.use_cases import ConnectRepo

    return ConnectRepo(
        requirements=container.requirements,
        repos=GitRepoConnector(servicio),
        clock=container.clock,
        ids=container.ids,
        audit=container.audit,
    )


def test_the_code_agent_only_gets_the_tools_it_declares() -> None:
    registro = GitToolRegistry(git=GitService(GitClient()), runs=None, requirements=None)  # type: ignore[arg-type]

    nombres = {spec.name for spec in registro.specs_for(AgentId.CODE)}
    assert nombres == {"git_diff", "list_files", "read_file", "search_code"}
    # El agente de Kiuwan declara otras: no le corresponde ninguna de estas.
    assert registro.specs_for(AgentId.KIUWAN) == ()


def test_parse_diff_handles_renames_and_binaries() -> None:
    texto = (
        "diff --git a/viejo.py b/nuevo.py\n"
        "similarity index 90%\n"
        "rename from viejo.py\n"
        "rename to nuevo.py\n"
        "--- a/viejo.py\n"
        "+++ b/nuevo.py\n"
        "@@ -1,2 +1,2 @@\n"
        " def f():\n"
        "-    return 1\n"
        "+    return 2\n"
        "diff --git a/logo.png b/logo.png\n"
        "new file mode 100644\n"
        "Binary files /dev/null and b/logo.png differ\n"
    )

    archivos = {f.path: f for f in parse_diff(texto)}

    assert archivos["nuevo.py"].status is FileStatus.RENAMED
    assert archivos["nuevo.py"].old_path == "viejo.py"
    assert archivos["nuevo.py"].additions == 1
    assert archivos["logo.png"].binary is True
    assert archivos["logo.png"].has_patch is False


def test_findings_about_files_outside_the_change_are_discarded(settings, spec: RepoSpec) -> None:
    """Un modelo puede citar una ruta plausible que no existe; eso no puede llegar al dictamen."""
    from orq.application.ports import AgentResult, AgentRequest
    from orq.domain.run import Usage

    class GatewayQueInventa:
        """Devuelve un hallazgo sobre un archivo que no está en el cambio."""

        def __init__(self) -> None:
            from orq.infrastructure.ai.gateway import AIGateway

            self._real = AIGateway()

        async def run_agent(self, request: AgentRequest) -> AgentResult:
            result = await self._real.run_agent(request)
            if request.agent_id is not AgentId.CODE:
                return result
            output = dict(result.output)
            output["findings"] = [
                {
                    "severity": "alta",
                    "title": "Hallazgo sobre un archivo inventado",
                    "detail": "",
                    "file": "src/no/existe.py",
                    "line": 88,
                },
                {
                    "severity": "media",
                    "title": "Hallazgo sobre un archivo del cambio",
                    "detail": "",
                    "file": "src/pagos.py",
                    "line": 1,
                },
            ]
            return AgentResult(
                agent_id=result.agent_id,
                output=output,
                usage=result.usage or Usage(),
                steps=result.steps,
                calls=result.calls,
            )

    servicio = GitService(GitClient())
    container = make_container(settings, gateway=GatewayQueInventa())
    container.supervisor._executor._repos = GitRepoAnalyzer(servicio)  # type: ignore[attr-defined]

    requirement = run_async(
        container.create_requirement()(
            CreateRequirementCommand(
                title="Conciliación",
                description="Ajuste de la conciliación.",
                owner="ana",
                phi=PhiClassification.NO,
                attachments=(
                    NewAttachment(kind=AttachmentKind.VTR_TEMPLATE, name="VTR-modelo.docx"),
                ),
            )
        )
    )
    requirement = run_async(
        ConnectRepoUseCase(container, servicio)(
            ConnectRepoCommand(
                requirement_id=requirement.id, url=spec.url, branch=spec.branch, base=spec.base
            )
        )
    )
    run_async(container.suggest_plan()(requirement.id))
    run = run_async(
        container.start_run()(
            StartRunCommand(requirement_id=requirement.id, started_by="ana", wait=True)
        )
    )

    from orq.application.deliverables import build_deliverables

    code = build_deliverables(run).code
    assert code is not None
    archivos = {f.file for f in code.findings if f.file}
    assert "src/no/existe.py" not in archivos, "un hallazgo sobre un archivo inventado llegó al informe"
    assert "src/pagos.py" in archivos

    eventos = run_async(container.runs.events(run.id))
    descartes = [e for e in eventos if e.type.value == "guardrail_applied" and "descartado" in e.title]
    assert descartes, "el descarte tiene que quedar en la traza, no en silencio"
    assert descartes[0].data["discarded"] == 1

    run_async(servicio.release_all())
