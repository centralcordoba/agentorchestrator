"""Catálogo: definición de los agentes, modelos disponibles y perfiles."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query

from ...domain.agents import AGENTS, AGENT_ORDER, ALL_AGENTS
from ...domain.policies import PROVIDER_BAA
from ...infrastructure.ai.catalog import MODEL_CATALOG
from ..container import Container
from ..deps import current_user, get_container
from ..schemas import (
    ERROR_RESPONSES,
    AgentCatalogOut,
    AgentDefinitionOut,
    AgentProfileOut,
    ModelCatalogOut,
    ModelInfoOut,
    ProviderCatalogOut,
)

router = APIRouter(prefix="/catalog", tags=["catálogo"], responses=ERROR_RESPONSES)


def _plain(value: Any) -> Any:
    """Los esquemas del registro son de solo lectura: se copian para serializarlos."""
    from collections.abc import Mapping

    if isinstance(value, Mapping):
        return {k: _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    return value


@router.get("/agents", response_model=AgentCatalogOut)
def agents(user=Depends(current_user)) -> AgentCatalogOut:
    """Definición de cada agente. El esquema y las herramientas son de solo lectura."""
    return AgentCatalogOut(
        order=[a.value for a in AGENT_ORDER],
        all=[a.value for a in ALL_AGENTS],
        agents={
            agent_id.value: AgentDefinitionOut(
                id=definition.id.value,
                label=definition.label,
                short=definition.short,
                role=definition.role,
                optional=definition.optional,
                depends_on=[d.value for d in definition.depends_on],
                tools=list(definition.tools),
                output_schema=_plain(dict(definition.output_schema)),
                requires_attachment=(
                    definition.requires_attachment.value
                    if definition.requires_attachment
                    else None
                ),
                processes_phi=definition.processes_phi,
            )
            for agent_id, definition in AGENTS.items()
        },
    )


@router.get("/models", response_model=ModelCatalogOut)
def models(user=Depends(current_user)) -> ModelCatalogOut:
    """Modelos y precios estimados por proveedor, con la señal de BAA."""
    return ModelCatalogOut(
        providers={
            provider.value: ProviderCatalogOut(
                baa=PROVIDER_BAA.get(provider),
                models=[
                    ModelInfoOut(
                        id=m.id, label=m.label, in_per_m=m.in_per_m, out_per_m=m.out_per_m
                    )
                    for m in infos
                ],
            )
            for provider, infos in MODEL_CATALOG.items()
        }
    )


@router.get("/profiles", response_model=dict[str, AgentProfileOut])
async def profiles(
    requirement_id: str | None = Query(None, alias="requirementId"),
    user=Depends(current_user),
    container: Container = Depends(get_container),
) -> dict[str, AgentProfileOut]:
    """Perfiles efectivos: los globales, o los del requerimiento si se indica."""
    effective = await container.list_profiles()(requirement_id)
    return {
        agent_id.value: AgentProfileOut.from_domain(profile)
        for agent_id, profile in effective.items()
    }
