"""Registro de herramientas ejecutables."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from ...application.ports import ToolSpec
from ...domain.agents import AGENTS
from ...domain.enums import AgentId
from ...domain.errors import ToolNotAllowedError

ToolHandler = Callable[[AgentId, dict[str, Any]], Awaitable[str]]


@dataclass(frozen=True, slots=True)
class RegisteredTool:
    spec: ToolSpec
    handler: ToolHandler


class InMemoryToolRegistry:
    """Implementa el puerto `ToolRegistry`."""

    def __init__(self) -> None:
        self._tools: dict[str, RegisteredTool] = {}

    def register(
        self,
        name: str,
        *,
        description: str,
        input_schema: dict[str, Any],
        handler: ToolHandler,
    ) -> None:
        """Registra una herramienta que al menos un agente declara.

        Registrar una herramienta que nadie declara sería código muerto y, peor, una puerta
        abierta: se rechaza.
        """
        if not any(name in definition.tools for definition in AGENTS.values()):
            raise ToolNotAllowedError(f"Ningún agente declara la herramienta «{name}».")
        self._tools[name] = RegisteredTool(
            spec=ToolSpec(name=name, description=description, input_schema=input_schema),
            handler=handler,
        )

    def specs_for(self, agent_id: AgentId) -> tuple[ToolSpec, ...]:
        declared = AGENTS[agent_id].tools
        return tuple(self._tools[name].spec for name in declared if name in self._tools)

    async def execute(
        self, agent_id: AgentId, tool: str, arguments: dict[str, Any], *, run_id: str = ""
    ) -> str:
        if tool not in AGENTS[agent_id].tools:
            raise ToolNotAllowedError(
                f"{AGENTS[agent_id].label} no tiene autorizada la herramienta «{tool}»."
            )
        registered = self._tools.get(tool)
        if registered is None:
            raise ToolNotAllowedError(f"No hay ninguna implementación de «{tool}» registrada.")
        return await registered.handler(agent_id, arguments)

    def __len__(self) -> int:
        return len(self._tools)
