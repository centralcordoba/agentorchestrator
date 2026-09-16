"""Grafo de dependencias de una ejecución."""
from __future__ import annotations

from .agents import AGENTS, AGENT_ORDER
from .enums import AgentId
from .errors import DomainError

#: Va antes que todos.
FIRST = AgentId.ORCHESTRATOR
#: Va después de todos.
LAST = AgentId.VERDICT


def dependencies_of(agent_id: AgentId, enabled: frozenset[AgentId]) -> frozenset[AgentId]:
    """Dependencias efectivas dentro de los agentes activos de esta ejecución."""
    declared = set(AGENTS[agent_id].depends_on)
    if agent_id is not FIRST:
        declared.add(FIRST)
    if agent_id is LAST:
        declared.update(a for a in enabled if a is not LAST)
    return frozenset(declared & enabled)


def execution_waves(enabled: tuple[AgentId, ...]) -> tuple[tuple[AgentId, ...], ...]:
    """Agrupa los agentes en oleadas: todo lo que hay en una puede correr en paralelo.

    Un agente entra en una oleada cuando todas sus dependencias activas ya salieron. Las
    dependencias desactivadas no bloquean: el agente trabaja con menos contexto y el plan ya
    avisó de ello.
    """
    pending = set(enabled)
    if unknown := pending - set(AGENTS):
        raise DomainError(f"Agentes desconocidos en la ejecución: {sorted(a for a in unknown)}")

    active = frozenset(pending)
    waves: list[tuple[AgentId, ...]] = []
    done: set[AgentId] = set()

    while pending:
        ready = [a for a in pending if dependencies_of(a, active) <= done]
        if not ready:
            # No puede pasar con el catálogo actual; si pasara, es un ciclo mal declarado.
            raise DomainError(
                "Hay un ciclo de dependencias entre agentes: " + ", ".join(sorted(a.value for a in pending))
            )
        # Se conserva el orden del catálogo para que la traza sea siempre igual de legible.
        wave = tuple(a for a in AGENT_ORDER if a in ready)
        waves.append(wave)
        done.update(wave)
        pending -= set(wave)

    return tuple(waves)


def missing_dependencies(agent_id: AgentId, completed: frozenset[AgentId]) -> tuple[AgentId, ...]:
    """Dependencias declaradas que no produjeron resultado: el agente trabaja degradado."""
    return tuple(d for d in AGENTS[agent_id].depends_on if d not in completed)
