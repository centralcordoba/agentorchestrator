"""Puertos: lo que la aplicación necesita del exterior, expresado como interfaz."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping, Protocol, runtime_checkable

from ..domain.audit import AuditAction, AuditEntry
from ..domain.enums import AgentId, PhiClassification, PhiIdentifier
from ..domain.findings import ChangeMapEntry, Finding
from ..domain.identity import Session, User
from ..domain.plan import Plan
from ..domain.profiles import AgentProfile
from ..domain.requirement import RepoInfo, Requirement
from ..domain.run import LLMCall, ProfileSnapshot, Run, TraceEvent, Usage
from ..domain.secrets import NewSecret, SecretKind, SecretMetadata, SecretValue


# Asíncronos porque el motor lo es: una escritura no puede bloquear el bucle mientras otros
# agentes trabajan en paralelo.
@runtime_checkable
class RequirementRepository(Protocol):
    async def add(self, requirement: Requirement) -> None: ...

    async def get(self, requirement_id: str) -> Requirement | None: ...

    async def save(self, requirement: Requirement) -> None: ...

    async def list(self, *, limit: int | None = None, offset: int = 0) -> list[Requirement]: ...

    async def count(self) -> int: ...


@runtime_checkable
class PlanRepository(Protocol):
    async def get(self, requirement_id: str) -> Plan | None: ...

    async def save(self, requirement_id: str, plan: Plan) -> None: ...


@runtime_checkable
class RunRepository(Protocol):
    async def add(self, run: Run) -> None: ...

    async def get(self, run_id: str) -> Run | None: ...

    async def save(self, run: Run) -> None: ...

    async def list_for_requirement(
        self, requirement_id: str, *, limit: int | None = None, offset: int = 0
    ) -> list[Run]: ...

    async def count_for_requirement(self, requirement_id: str) -> int: ...

    async def list_unfinished(self) -> list[Run]: ...

    async def append_event(self, event: TraceEvent) -> None: ...

    async def events(self, run_id: str, *, after_seq: int = 0) -> list[TraceEvent]: ...

    async def next_seq(self, run_id: str) -> int: ...


@runtime_checkable
class AuditLog(Protocol):
    """Registro de solo anexado: no declara modificar ni borrar, y no es un olvido."""

    async def append(
        self, *, at: datetime, actor: str, action: AuditAction, target: str, detail: str = ""
    ) -> AuditEntry: ...

    async def list(
        self, *, target: str | None = None, limit: int = 200, offset: int = 0
    ) -> list[AuditEntry]: ...

    async def count(self, *, target: str | None = None) -> int: ...


@runtime_checkable
class ProfileRepository(Protocol):
    """Perfiles globales por agente y ajustes por requerimiento."""

    async def defaults(self) -> dict[AgentId, AgentProfile]: ...

    async def effective(self, requirement_id: str) -> dict[AgentId, AgentProfile]: ...

    async def save_default(self, profile: AgentProfile) -> None: ...

    async def save_override(self, requirement_id: str, profile: AgentProfile) -> None: ...


@runtime_checkable
class UserRepository(Protocol):
    """Personas. `credential_of` y `set_password` son el **único** camino al hash.

    `User` no tiene campo de contraseña, así que el hash no puede salir por accidente; estos dos
    métodos existen para el caso de uso de login y para el cambio de contraseña, y una prueba de
    arquitectura comprueba que nadie más los llama.
    """

    async def add(self, user: User, *, password_hash: str | None = None) -> None: ...

    async def save(self, user: User) -> None: ...

    async def get(self, user_id: str) -> User | None: ...

    async def by_email(self, email: str) -> User | None: ...

    async def list(self) -> list[User]: ...

    async def count(self) -> int: ...

    async def credential_of(self, user_id: str) -> str | None: ...

    async def set_password(self, user_id: str, password_hash: str) -> None: ...


@runtime_checkable
class SessionRepository(Protocol):
    """Sesiones abiertas. La clave es el hash del testigo, no el testigo."""

    async def add(self, session: Session) -> None: ...

    async def get(self, session_id: str) -> Session | None: ...

    async def save(self, session: Session) -> None: ...

    async def revoke(self, session_id: str, *, at: datetime) -> None: ...

    async def revoke_all_for(self, user_id: str, *, at: datetime) -> int: ...

    async def purge_before(self, cutoff: datetime) -> int: ...


@runtime_checkable
class Clock(Protocol):
    def now(self) -> datetime: ...


@runtime_checkable
class IdGenerator(Protocol):
    """Identificadores legibles (REQ-001, RUN-002…).

    Es asíncrono porque con persistencia el contador vive en la base: si se reiniciara en cada
    arranque, la aplicación pisaría requerimientos ya guardados.
    """

    async def new_id(self, prefix: str) -> str: ...


@runtime_checkable
class EventPublisher(Protocol):
    """Publica la traza. En ORQ-17 lo implementa el bus con WebSocket y replay."""

    async def publish(self, event: TraceEvent) -> None: ...


@dataclass(frozen=True, slots=True)
class GitCredential:
    """Credencial para hablar con un repositorio privado.

    Tiene `__repr__` propio a propósito: un `print`, un `log.debug(...)` o el volcado de una
    excepción no pueden enseñar el token. La bóveda que las guarda cifradas es ORQ-18.
    """

    username: str = ""
    token: str = ""

    def __repr__(self) -> str:  # pragma: no cover - trivial pero es la salvaguarda
        return f"GitCredential(username={self.username!r}, token='***')"

    def __str__(self) -> str:  # pragma: no cover - idem
        return self.__repr__()


@runtime_checkable
class CredentialStore(Protocol):
    """De dónde salen las credenciales. Nunca de la UI ni del navegador."""

    async def git_credential(self, host: str) -> GitCredential | None: ...


@runtime_checkable
class SecretVault(Protocol):
    """Bóveda de secretos (ORQ-18).

    Fíjate en las firmas: `list` devuelve **metadatos**, que no tienen campo para el valor, y
    `reveal` —lo único que lo devuelve— existe para que lo llame el backend cuando va a usarlo.
    Ningún router debería llamar a `reveal`; la prueba de arquitectura lo comprueba.
    """

    async def save(self, secret: NewSecret, *, at: datetime) -> SecretMetadata: ...

    async def list(self, *, scope: str | None = None) -> list[SecretMetadata]: ...

    async def get(self, secret_id: str) -> SecretMetadata | None: ...

    async def revoke(self, secret_id: str, *, at: datetime, by: str) -> SecretMetadata: ...

    async def reveal(
        self, kind: SecretKind, name: str, *, scope: str = "", at: datetime
    ) -> SecretValue | None: ...


@dataclass(frozen=True, slots=True)
class RepoAnalysis:
    """Lo que se sabe del cambio **sin preguntar a un modelo**: evidencia, no opinión."""

    change_map: tuple[ChangeMapEntry, ...] = ()
    findings: tuple[Finding, ...] = ()
    files: int = 0
    truncated: bool = False

    @property
    def empty(self) -> bool:
        return not self.change_map and not self.findings


@runtime_checkable
class RepoConnector(Protocol):
    """Conecta un repositorio y devuelve su ficha con el `head_sha` ya fijado."""

    async def connect(
        self, *, url: str, branch: str = "", base: str = "", last_commits: int = 0
    ) -> RepoInfo: ...


@runtime_checkable
class RepoAnalyzer(Protocol):
    """Diff y reglas deterministas de un repositorio conectado.

    `release` borra la copia de trabajo de la ejecución: el motor la llama siempre, también
    cuando la ejecución falla o se cancela.
    """

    async def analyze(
        self, *, run_id: str, repo: RepoInfo, criteria: tuple[str, ...] = ()
    ) -> RepoAnalysis: ...

    async def release(self, run_id: str) -> None: ...


@dataclass(frozen=True, slots=True)
class AgentRequest:
    """Todo lo que la capa de IA necesita para ejecutar un agente.

    El esquema de salida y las herramientas no viajan aquí: la pasarela los toma del registro
    del dominio, que no es editable.
    """

    run_id: str
    agent_id: AgentId
    profile: ProfileSnapshot
    system_prompt: str
    task_prompt: str
    context: dict[str, Any] = field(default_factory=dict)
    phi: PhiClassification = PhiClassification.DESCONOCIDO


@dataclass(frozen=True, slots=True)
class AgentResult:
    """Salida ya validada contra el esquema del agente."""

    agent_id: AgentId
    output: dict[str, Any]
    usage: Usage
    steps: int = 1
    tools_used: tuple[str, ...] = ()
    redactions: Mapping[PhiIdentifier, int] = field(default_factory=dict)
    calls: tuple[LLMCall, ...] = ()


@dataclass(frozen=True, slots=True)
class ToolSpec:
    """Herramienta ejecutable.

    El nombre tiene que estar declarado en la definición del agente; la pasarela lo comprueba.
    Las implementaciones reales llegan con cada agente (ORQ-22 y siguientes).
    """

    name: str
    description: str
    input_schema: dict[str, Any]


@runtime_checkable
class ToolRegistry(Protocol):
    """Herramientas disponibles para un agente, con su ejecución."""

    def specs_for(self, agent_id: AgentId) -> tuple[ToolSpec, ...]: ...

    async def execute(
        self, agent_id: AgentId, tool: str, arguments: dict[str, Any], *, run_id: str = ""
    ) -> str: ...


@runtime_checkable
class AgentGateway(Protocol):
    """Única puerta hacia un LLM. Ningún agente habla directo con un SDK."""

    async def run_agent(self, request: AgentRequest) -> AgentResult: ...
