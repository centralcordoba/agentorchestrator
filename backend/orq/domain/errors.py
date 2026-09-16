"""Errores del dominio. La capa de API los traduce a códigos HTTP; el dominio no los conoce."""
from __future__ import annotations


class DomainError(Exception):
    """Regla de negocio incumplida."""


class NotFoundError(DomainError):
    """La entidad pedida no existe."""


class PlanBlockedError(DomainError):
    """El plan no se puede ejecutar: faltan adjuntos o se incumple una política obligatoria."""

    def __init__(self, reasons: list[str]) -> None:
        self.reasons = reasons
        super().__init__(" · ".join(reasons))


class PolicyViolationError(DomainError):
    """Se intentó algo que una política de cumplimiento prohíbe (PHI, BAA, permisos)."""


class ToolNotAllowedError(DomainError):
    """Un agente intentó usar una herramienta que su definición no declara."""


class InvalidAgentOutputError(DomainError):
    """La salida del agente no cumple su esquema declarado."""


class BudgetExceededError(DomainError):
    """La ejecución agotó su presupuesto de tokens o de dinero."""


class ProviderError(DomainError):
    """Fallo del proveedor de IA: red, cuota, rechazo o salida inservible."""


class ProviderNotConfiguredError(ProviderError):
    """Al proveedor le faltan credenciales o no está implementado."""


class ProviderRefusalError(ProviderError):
    """El modelo se negó a responder (clasificador de seguridad del proveedor)."""
