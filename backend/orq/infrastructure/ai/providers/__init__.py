"""Proveedores de LLM. Solo este paquete conoce un SDK o un endpoint de proveedor."""
from __future__ import annotations

from ....domain.enums import ProviderId
from .anthropic_provider import AnthropicProvider
from .base import LLMProvider, ProviderRequest, ProviderResponse, ToolRunner, user_content
from .mock import MockLLMProvider
from .openrouter_provider import DEFAULT_BASE_URL, OpenRouterProvider


def build_provider(
    provider_id: ProviderId,
    *,
    anthropic_api_key: str = "",
    openrouter_api_key: str = "",
    openrouter_base_url: str = DEFAULT_BASE_URL,
    mock_delay_ms: int = 0,
    mock_rich: bool = False,
) -> LLMProvider:
    """Crea el proveedor pedido. Las claves llegan de la configuración, nunca de la UI."""
    if provider_id is ProviderId.MOCK:
        return MockLLMProvider(delay_ms=mock_delay_ms, rich=mock_rich)
    if provider_id is ProviderId.ANTHROPIC:
        return AnthropicProvider(api_key=anthropic_api_key)
    if provider_id is ProviderId.OPENROUTER:
        return OpenRouterProvider(api_key=openrouter_api_key, base_url=openrouter_base_url)
    raise ValueError(f"Proveedor desconocido: {provider_id}")


__all__ = [
    "AnthropicProvider",
    "DEFAULT_BASE_URL",
    "LLMProvider",
    "MockLLMProvider",
    "OpenRouterProvider",
    "ProviderRequest",
    "ProviderResponse",
    "ToolRunner",
    "build_provider",
    "user_content",
]
