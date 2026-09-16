"""Contrato común de los proveedores de LLM."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Mapping, Protocol, runtime_checkable

from ....application.ports import ToolSpec
from ....domain.enums import AgentId, ProviderId

#: Ejecuta una herramienta ya autorizada y devuelve su resultado como texto.
ToolRunner = Callable[[str, dict[str, Any]], Awaitable[str]]


@dataclass(frozen=True, slots=True)
class ProviderRequest:
    agent_id: AgentId
    model: str
    system_prompt: str
    task_prompt: str
    context: dict[str, Any]
    output_schema: Mapping[str, Any]
    temperature: float = 0.0
    #: Vueltas máximas del bucle de herramientas.
    max_steps: int = 4
    max_output_tokens: int = 16_000
    timeout_s: float = 120.0
    tools: tuple[ToolSpec, ...] = ()
    run_tool: ToolRunner | None = None


@dataclass(frozen=True, slots=True)
class ProviderResponse:
    output: dict[str, Any]
    tokens_in: int = 0
    tokens_out: int = 0
    steps: int = 1
    #: Herramientas que el modelo pidió; la pasarela las valida contra el registro.
    tools_used: tuple[str, ...] = field(default=())


@runtime_checkable
class LLMProvider(Protocol):
    id: ProviderId

    async def complete(self, request: ProviderRequest) -> ProviderResponse: ...


def user_content(request: ProviderRequest) -> str:
    """Mensaje de usuario: plantilla de tarea del perfil más el contexto de la ejecución.

    El contexto ya viene preparado por el caso de uso. La redacción de PHI se aplica antes de
    llegar aquí (ORQ-20); este módulo no la reimplementa.
    """
    import json

    context = json.dumps(request.context, ensure_ascii=False, indent=2, default=str)
    return (
        f"{request.task_prompt}\n\n"
        f"<contexto>\n{context}\n</contexto>\n\n"
        "Responde únicamente con el JSON que exige tu esquema de salida."
    )
