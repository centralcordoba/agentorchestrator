"""Políticas de cumplimiento. Reglas puras que ninguna capa superior puede saltarse."""
from __future__ import annotations

from dataclasses import dataclass

from .agents import AGENTS
from .enums import AgentId, PhiClassification, ProviderId, Severity, Verdict
from .findings import Finding, count_by_severity
from .run import Usage

#: ¿El proveedor tiene BAA firmado con la organización? `None` = no aplica (mock, sin red).
#: Suposición de diseño heredada del prototipo: Claude API con organización HIPAA; OpenRouter no
#: publica BAA. Antes de uso real hay que confirmarlo con el contrato (ORQ-21).
PROVIDER_BAA: dict[ProviderId, bool | None] = {
    ProviderId.ANTHROPIC: True,
    ProviderId.OPENROUTER: False,
    ProviderId.MOCK: None,
}


@dataclass(frozen=True, slots=True)
class RunBudget:
    """Techo de gasto de una ejecución. `0` = sin límite.

    Existe para que un bucle de herramientas descontrolado no se coma el presupuesto del mes.
    El panel y las alertas de consumo son ORQ-29; esto es el corte duro.
    """

    max_tokens: int = 0
    max_cost_usd: float = 0.0

    def exceeded_by(self, usage: Usage) -> str | None:
        """Motivo del corte, o `None` si todavía hay margen."""
        total_tokens = usage.tokens_in + usage.tokens_out
        if self.max_tokens and total_tokens > self.max_tokens:
            return f"La ejecución superó el límite de {self.max_tokens} tokens ({total_tokens})."
        if self.max_cost_usd and usage.cost_usd > self.max_cost_usd:
            return (
                f"La ejecución superó el presupuesto de {self.max_cost_usd:.2f} USD "
                f"({usage.cost_usd:.4f})."
            )
        return None


def handles_phi(phi: PhiClassification) -> bool:
    """Sin clasificar se trata como «sí»."""
    return phi is not PhiClassification.NO


def provider_allowed_for_phi(provider: ProviderId) -> bool:
    """Solo un proveedor con BAA puede procesar contenido con PHI.

    `mock` no sale de la máquina, así que se permite: es el proveedor de pruebas.
    """
    if provider is ProviderId.MOCK:
        return True
    return PROVIDER_BAA.get(provider) is True


def check_agent_provider(agent_id: AgentId, provider: ProviderId, phi: PhiClassification) -> str | None:
    """Devuelve el motivo del bloqueo, o `None` si el agente puede ejecutarse.

    Un agente que no procesa contenido del cliente (Orquestador, Dictamen) trabaja con
    metadatos y resultados ya redactados, así que no exige BAA.
    """
    if not handles_phi(phi):
        return None
    if not AGENTS[agent_id].processes_phi:
        return None
    if provider_allowed_for_phi(provider):
        return None
    return (
        f"{AGENTS[agent_id].label} procesaría contenido con PHI a través de "
        f"«{provider.value}», que no tiene BAA firmado."
    )


def privacy_required(phi: PhiClassification, enabled_agents: tuple[AgentId, ...]) -> bool:
    """¿Falta el agente de Privacidad siendo obligatorio?"""
    return handles_phi(phi) and AgentId.PRIVACY not in enabled_agents


def verdict_from_findings(findings: tuple[Finding, ...]) -> Verdict:
    """Umbrales del dictamen. Deterministas: los mismos hallazgos dan siempre el mismo veredicto."""
    counts = count_by_severity(findings)
    if counts[Severity.CRITICA] > 0:
        return Verdict.RECHAZADO
    if counts[Severity.ALTA] >= 3:
        return Verdict.RECHAZADO
    if counts[Severity.ALTA] > 0 or counts[Severity.MEDIA] > 0:
        return Verdict.APROBADO_CON_OBSERVACIONES
    return Verdict.APROBADO


def apply_phi_guardrail(
    verdict: Verdict, *, phi: PhiClassification, privacy_executed: bool
) -> tuple[Verdict, str | None]:
    """Con PHI y sin informe de Privacidad, el dictamen no puede ser APROBADO.

    Devuelve el veredicto ya corregido y el guardarraíl aplicado, si lo hubo.
    """
    if verdict is Verdict.APROBADO and handles_phi(phi) and not privacy_executed:
        return (
            Verdict.APROBADO_CON_OBSERVACIONES,
            "El requerimiento puede tocar PHI y no hay informe del agente de Privacidad: "
            "no puede aprobarse sin observaciones.",
        )
    return verdict, None
