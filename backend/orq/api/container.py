"""Composición de dependencias."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import timedelta

from ..application.ports import (
    AgentGateway,
    AuditLog,
    Clock,
    EventPublisher,
    IdGenerator,
    PlanRepository,
    ProfileRepository,
    RequirementRepository,
    RunRepository,
    SecretVault,
    SessionRepository,
    UserRepository,
)
from ..application.auth import (
    ChangePassword,
    CreateUser,
    CreateUserCommand,
    ListUsers,
    Login,
    Logout,
    ResolveSession,
    UpdateUser,
)
from ..application.run_executor import RunExecutor
from ..application.run_supervisor import RunSupervisor
from ..application.use_cases import (
    AddAttachment,
    CancelRun,
    ClassifyPhi,
    ConnectRepo,
    CreateRequirement,
    GetDeliverables,
    GetPlan,
    GetRequirement,
    GetRun,
    ListProfiles,
    ListRequirements,
    ListRuns,
    ListSecrets,
    ResumeInterruptedRuns,
    RevokeSecret,
    SaveSecret,
    StartRun,
    SuggestPlan,
    UpdatePlan,
)
from ..config import Settings, load_settings
from ..domain.identity import AuthProvider, LockPolicy, Role, SessionPolicy
from ..domain.policies import RunBudget
from ..infrastructure.ai.gateway import AIGateway, RetryPolicy
from ..infrastructure.auth import (
    InMemorySessionRepository,
    InMemoryUserRepository,
    PostgresSessionRepository,
    PostgresUserRepository,
)
from ..infrastructure.ai.git_tools import GitToolRegistry
from ..infrastructure.ai.tools import InMemoryToolRegistry
from ..infrastructure.git import (
    ConfiguredCredentialStore,
    GitClient,
    GitLimits,
    GitRepoAnalyzer,
    GitRepoConnector,
    GitService,
    clean_leftovers,
)
from ..infrastructure.db import (
    Cipher,
    Database,
    PostgresAuditLog,
    PostgresIdGenerator,
    PostgresPlanRepository,
    PostgresProfileRepository,
    PostgresRequirementRepository,
    PostgresRunRepository,
    RetentionService,
    normalize_url,
)
from ..infrastructure.events import InMemoryEventBus
from ..infrastructure.persistence import (
    InMemoryAuditLog,
    InMemoryPlanRepository,
    InMemoryProfileRepository,
    InMemoryRequirementRepository,
    InMemoryRunRepository,
)
from ..infrastructure.profiles import default_profiles
from ..infrastructure.secrets import (
    InMemorySecretVault,
    PostgresSecretVault,
    SecretScrubber,
    VaultCredentialStore,
)
from ..infrastructure.services import SequentialIdGenerator, SystemClock

log = logging.getLogger(__name__)


@dataclass(slots=True)
class Container:
    settings: Settings
    clock: Clock
    ids: IdGenerator
    events: EventPublisher
    gateway: AgentGateway
    requirements: RequirementRepository
    plans: PlanRepository
    runs: RunRepository
    profiles: ProfileRepository
    audit: AuditLog
    database: Database | None = None
    retention: RetentionService | None = None
    git: GitService | None = None
    vault: SecretVault | None = None
    scrubber: SecretScrubber | None = None
    users: UserRepository | None = None
    sessions: SessionRepository | None = None
    supervisor: RunSupervisor = field(init=False)

    def __post_init__(self) -> None:
        self.supervisor = RunSupervisor(
            executor=RunExecutor(
                runs=self.runs,
                events=self.events,
                clock=self.clock,
                gateway=self.gateway,
                repos=GitRepoAnalyzer(self.git) if self.git is not None else None,
                scrub=self.scrubber.scrub if self.scrubber is not None else None,
            ),
            runs=self.runs,
            clock=self.clock,
        )

    async def startup(self) -> None:
        """Deja la persistencia lista. Con base de datos, siembra los perfiles iniciales."""
        if isinstance(self.profiles, PostgresProfileRepository):
            await self.profiles.ensure_seeded()
        # Un cierre brusco pudo dejar copias de trabajo con código del cliente en el temporal.
        await clean_leftovers()
        if self.scrubber is not None:
            self.scrubber.install()
        # `prime` no pasa por `reveal`: cargar valores al arrancar no cuenta como usarlos.
        if self.vault is not None and hasattr(self.vault, "prime"):
            cargados = await self.vault.prime()  # type: ignore[attr-defined]
            if cargados:
                log.info("tachador de secretos cargado con %s valor(es) activos", cargados)
        await self._seed_admin()
        await self._purge_old_sessions()

    async def _seed_admin(self) -> None:
        """Crea la cuenta inicial si no hay ninguna.

        Sin esto no habría forma de entrar la primera vez. Se hace **solo cuando la tabla está
        vacía**: si ya hay cuentas, esta variable no puede resucitar un administrador.
        """
        if self.users is None or await self.users.count() > 0:
            return
        if not self.settings.admin_email or not self.settings.admin_password:
            log.warning(
                "No hay ninguna cuenta y falta ADMIN_EMAIL/ADMIN_PASSWORD: nadie podra entrar. "
                "Definelas y reinicia."
            )
            return
        user = await self.create_user().unchecked(
            CreateUserCommand(
                email=self.settings.admin_email,
                name="Administrador",
                role=Role.ADMINISTRADOR,
                password=self.settings.admin_password,
                provider=AuthProvider.LOCAL,
                # La contraseña viene del entorno, que acaba en el historial del terminal.
                must_change_password=True,
            )
        )
        log.info("cuenta inicial creada: %s (tendra que cambiar la contrasena)", user.email)

    async def _purge_old_sessions(self) -> None:
        """Borra sesiones que ya no pueden valer. La tabla no puede crecer sin fin."""
        if self.sessions is None:
            return
        corte = self.clock.now() - timedelta(minutes=self.settings.session_max_age_minutes)
        borradas = await self.sessions.purge_before(corte)
        if borradas:
            log.info("se borraron %s sesion(es) caducadas", borradas)

    async def shutdown(self) -> None:
        if self.git is not None:
            await self.git.release_all()
        if self.database is not None:
            await self.database.dispose()

    def create_requirement(self) -> CreateRequirement:
        return CreateRequirement(
            requirements=self.requirements, clock=self.clock, ids=self.ids, audit=self.audit
        )

    def get_requirement(self) -> GetRequirement:
        return GetRequirement(requirements=self.requirements)

    def list_requirements(self) -> ListRequirements:
        return ListRequirements(requirements=self.requirements)

    def suggest_plan(self) -> SuggestPlan:
        return SuggestPlan(
            requirements=self.requirements,
            plans=self.plans,
            clock=self.clock,
            gateway=self.gateway,
            profiles=self.profiles,
            audit=self.audit,
        )

    def get_plan(self) -> GetPlan:
        return GetPlan(requirements=self.requirements, plans=self.plans)

    def update_plan(self) -> UpdatePlan:
        return UpdatePlan(
            requirements=self.requirements,
            plans=self.plans,
            clock=self.clock,
            audit=self.audit,
        )

    def add_attachment(self) -> AddAttachment:
        return AddAttachment(
            requirements=self.requirements, clock=self.clock, ids=self.ids, audit=self.audit
        )

    def classify_phi(self) -> ClassifyPhi:
        return ClassifyPhi(
            requirements=self.requirements,
            plans=self.plans,
            clock=self.clock,
            audit=self.audit,
        )

    def start_run(self) -> StartRun:
        return StartRun(
            requirements=self.requirements,
            plans=self.plans,
            runs=self.runs,
            profiles=self.profiles,
            supervisor=self.supervisor,
            clock=self.clock,
            ids=self.ids,
            audit=self.audit,
        )

    def cancel_run(self) -> CancelRun:
        return CancelRun(
            runs=self.runs, supervisor=self.supervisor, clock=self.clock, audit=self.audit
        )

    def resume_runs(self) -> ResumeInterruptedRuns:
        return ResumeInterruptedRuns(
            requirements=self.requirements,
            plans=self.plans,
            runs=self.runs,
            profiles=self.profiles,
            supervisor=self.supervisor,
            clock=self.clock,
            audit=self.audit,
        )

    def get_run(self) -> GetRun:
        return GetRun(runs=self.runs)

    def list_runs(self) -> ListRuns:
        return ListRuns(runs=self.runs)

    def get_deliverables(self) -> GetDeliverables:
        return GetDeliverables(runs=self.runs)

    def list_profiles(self) -> ListProfiles:
        return ListProfiles(profiles=self.profiles)

    def save_secret(self) -> SaveSecret:
        return SaveSecret(vault=self._vault(), clock=self.clock, audit=self.audit)

    def list_secrets(self) -> ListSecrets:
        return ListSecrets(vault=self._vault(), clock=self.clock)

    def revoke_secret(self) -> RevokeSecret:
        return RevokeSecret(vault=self._vault(), clock=self.clock, audit=self.audit)

    def _vault(self) -> SecretVault:
        if self.vault is None:  # pragma: no cover - el contenedor real siempre la trae
            raise RuntimeError("No hay bóveda de secretos configurada.")
        return self.vault

    def _session_policy(self) -> SessionPolicy:
        return SessionPolicy(
            max_age=timedelta(minutes=self.settings.session_max_age_minutes),
            idle_timeout=timedelta(minutes=self.settings.session_idle_minutes),
        )

    def _lock_policy(self) -> LockPolicy:
        return LockPolicy(
            max_attempts=self.settings.login_max_attempts,
            lock_for=timedelta(minutes=self.settings.login_lock_minutes),
        )

    def login(self) -> Login:
        return Login(
            users=self._users(),
            sessions=self._sessions(),
            clock=self.clock,
            audit=self.audit,
            lock_policy=self._lock_policy(),
            session_policy=self._session_policy(),
        )

    def logout(self) -> Logout:
        return Logout(sessions=self._sessions(), clock=self.clock, audit=self.audit)

    def resolve_session(self) -> ResolveSession:
        return ResolveSession(
            users=self._users(),
            sessions=self._sessions(),
            clock=self.clock,
            policy=self._session_policy(),
        )

    def create_user(self) -> CreateUser:
        return CreateUser(
            users=self._users(), clock=self.clock, ids=self.ids, audit=self.audit
        )

    def list_users(self) -> ListUsers:
        return ListUsers(users=self._users())

    def update_user(self) -> UpdateUser:
        return UpdateUser(
            users=self._users(),
            sessions=self._sessions(),
            clock=self.clock,
            audit=self.audit,
        )

    def change_password(self) -> ChangePassword:
        return ChangePassword(
            users=self._users(),
            sessions=self._sessions(),
            clock=self.clock,
            audit=self.audit,
        )

    def _users(self) -> UserRepository:
        if self.users is None:  # pragma: no cover - el contenedor real siempre lo trae
            raise RuntimeError("No hay repositorio de usuarios configurado.")
        return self.users

    def _sessions(self) -> SessionRepository:
        if self.sessions is None:  # pragma: no cover
            raise RuntimeError("No hay repositorio de sesiones configurado.")
        return self.sessions

    def connect_repo(self) -> ConnectRepo:
        if self.git is None:  # pragma: no cover - el contenedor real siempre lo trae
            raise RuntimeError("No hay acceso a repositorios configurado.")
        return ConnectRepo(
            requirements=self.requirements,
            repos=GitRepoConnector(self.git),
            clock=self.clock,
            ids=self.ids,
            audit=self.audit,
        )


def build_gateway(
    settings: Settings, tools: object | None = None, scrubber: SecretScrubber | None = None
) -> AIGateway:
    """Pasarela de IA configurada: reintentos, tiempo máximo, presupuesto y herramientas."""
    return AIGateway(
        max_attempts=settings.ai_max_attempts,
        retry=RetryPolicy(
            attempts=settings.ai_retry_attempts, base_delay_s=settings.ai_retry_base_delay_s
        ),
        budget=RunBudget(
            max_tokens=settings.run_max_tokens, max_cost_usd=settings.run_max_cost_usd
        ),
        tools=tools or InMemoryToolRegistry(),  # type: ignore[arg-type]
        timeout_s=settings.ai_timeout_s,
        max_output_tokens=settings.ai_max_output_tokens,
        credentials=settings.credentials(),
        scrub=scrubber.scrub if scrubber is not None else None,
    )


def build_git(settings: Settings, credentials: object | None = None) -> GitService:
    """Acceso a los repositorios del cliente, con las credenciales del servidor.

    Las credenciales llegan de la bóveda (ORQ-18); `GIT_TOKENS` queda como respaldo para una
    máquina de desarrollo.
    """
    return GitService(
        GitClient(
            credentials=credentials or ConfiguredCredentialStore(settings.git_tokens),  # type: ignore[arg-type]
            limits=GitLimits(
                max_files=settings.git_max_files,
                max_diff_bytes=settings.git_max_diff_bytes,
                clone_timeout_s=settings.git_clone_timeout_s,
            ),
            clone_filter=settings.git_clone_filter,
        )
    )


def build_container(settings: Settings | None = None) -> Container:
    settings = settings or load_settings()
    seed = default_profiles(force_provider=settings.forced_provider)
    scrubber = SecretScrubber()

    if settings.database_url:
        # `Cipher` falla aquí si falta la clave: mejor no arrancar que escribir contenido en claro.
        database = Database(
            url=normalize_url(settings.database_url), cipher=Cipher(settings.db_encryption_key)
        )
        requirements = PostgresRequirementRepository(database)
        runs = PostgresRunRepository(database)
        ids = PostgresIdGenerator(database)
        audit = PostgresAuditLog(database)
        vault = PostgresSecretVault(database, ids=ids, scrubber=scrubber)
        users = PostgresUserRepository(database)
        sessions = PostgresSessionRepository(database)
        git = build_git(
            settings,
            VaultCredentialStore(
                vault,
                fallback=ConfiguredCredentialStore(settings.git_tokens),
                audit=audit,
            ),
        )
        return Container(
            settings=settings,
            clock=SystemClock(),
            ids=ids,
            events=InMemoryEventBus(),
            gateway=build_gateway(
                settings,
                GitToolRegistry(git=git, runs=runs, requirements=requirements),
                scrubber,
            ),
            requirements=requirements,
            plans=PostgresPlanRepository(database),
            runs=runs,
            profiles=PostgresProfileRepository(database, seed=seed),
            audit=audit,
            database=database,
            retention=RetentionService(database, default_days=settings.retention_days),
            git=git,
            vault=vault,
            scrubber=scrubber,
            users=users,
            sessions=sessions,
        )

    requirements = InMemoryRequirementRepository()
    runs = InMemoryRunRepository()
    audit = InMemoryAuditLog()
    vault = InMemorySecretVault(scrubber=scrubber)
    users = InMemoryUserRepository()
    sessions = InMemorySessionRepository()
    git = build_git(
        settings,
        VaultCredentialStore(
            vault, fallback=ConfiguredCredentialStore(settings.git_tokens), audit=audit
        ),
    )
    return Container(
        settings=settings,
        clock=SystemClock(),
        ids=SequentialIdGenerator(),
        events=InMemoryEventBus(),
        gateway=build_gateway(
            settings,
            GitToolRegistry(git=git, runs=runs, requirements=requirements),
            scrubber,
        ),
        requirements=requirements,
        plans=InMemoryPlanRepository(),
        runs=runs,
        profiles=InMemoryProfileRepository(seed),
        audit=audit,
        git=git,
        vault=vault,
        scrubber=scrubber,
        users=users,
        sessions=sessions,
    )
