"""Perfil de un agente: lo único configurable desde la UI."""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime

from .enums import AgentId, ProviderId
from .errors import DomainError
from .run import ProfileSnapshot


@dataclass(frozen=True, slots=True)
class PromptVersion:
    version: int
    saved_at: datetime
    author: str
    note: str
    system_prompt: str
    task_prompt: str


@dataclass(frozen=True, slots=True)
class AgentProfile:
    agent_id: AgentId
    provider: ProviderId
    model: str
    system_prompt: str
    task_prompt: str
    temperature: float = 0.1
    max_steps: int = 4
    prompt_version: int = 1
    versions: tuple[PromptVersion, ...] = ()

    def __post_init__(self) -> None:
        if not 0.0 <= self.temperature <= 2.0:
            raise DomainError("La temperatura debe estar entre 0 y 2.")
        if self.max_steps < 1:
            raise DomainError("El número máximo de pasos debe ser al menos 1.")
        if not self.model.strip():
            raise DomainError("El perfil necesita un modelo.")

    def snapshot(self) -> ProfileSnapshot:
        """Lo que se congela en la ejecución."""
        return ProfileSnapshot(
            provider=self.provider,
            model=self.model,
            prompt_version=self.prompt_version,
            temperature=self.temperature,
            max_steps=self.max_steps,
        )

    def with_prompt(
        self, *, system_prompt: str, task_prompt: str, author: str, note: str, at: datetime
    ) -> "AgentProfile":
        """Guarda una versión nueva del prompt conservando el historial."""
        version = self.prompt_version + 1
        entry = PromptVersion(
            version=version,
            saved_at=at,
            author=author,
            note=note,
            system_prompt=system_prompt,
            task_prompt=task_prompt,
        )
        return replace(
            self,
            system_prompt=system_prompt,
            task_prompt=task_prompt,
            prompt_version=version,
            versions=self.versions + (entry,),
        )

    def with_model(self, *, provider: ProviderId, model: str) -> "AgentProfile":
        return replace(self, provider=provider, model=model)

    def restored(self, snapshot: ProfileSnapshot) -> "AgentProfile":
        """Reconstruye el perfil tal como quedó congelado en una ejecución.

        Reanudar una ejecución con el prompt de hoy la falsearía: el resultado no sería el de la
        configuración que se firmó. Si la versión ya no está en el historial, se dice en vez de
        continuar con otra.
        """
        version = next((v for v in self.versions if v.version == snapshot.prompt_version), None)
        if version is None:
            raise DomainError(
                f"No se conserva la versión {snapshot.prompt_version} del prompt de "
                f"{self.agent_id.value}: la ejecución no se puede reanudar con fidelidad."
            )
        return replace(
            self,
            provider=snapshot.provider,
            model=snapshot.model,
            temperature=snapshot.temperature,
            max_steps=snapshot.max_steps,
            system_prompt=version.system_prompt,
            task_prompt=version.task_prompt,
            prompt_version=version.version,
        )
