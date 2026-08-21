"""Interfaz de proveedor LLM.

Los agentes no llaman al LLM "en abierto": envían hechos estructurados y piden un
JSON que cumpla un esquema. Así la salida es auditable y no hay razonamiento oculto
que mostrar.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


class LLMError(RuntimeError):
    """Fallo del proveedor LLM (red, cuota, rechazo, salida inválida...)."""


@dataclass
class LLMRequest:
    agent: str                       # agente que hace la petición
    task: str                        # identificador de la tarea (para el mock y la trazabilidad)
    instructions: str                # qué debe hacer, en lenguaje natural
    facts: dict[str, Any]            # ÚNICA fuente de datos permitida
    schema: dict[str, Any]           # JSON Schema de la respuesta
    extra: dict[str, Any] = field(default_factory=dict)


# Esquema común para explicaciones resumidas y auditables.
EXPLANATION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "summary": {
            "type": "string",
            "description": "Explicación breve (2-4 frases) basada SOLO en los hechos dados.",
        },
        "facts_used": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Claves exactas de los hechos utilizados en el resumen.",
        },
        "caveats": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Limitaciones o advertencias relevantes (máx. 3).",
        },
    },
    "required": ["summary", "facts_used", "caveats"],
    "additionalProperties": False,
}

SYSTEM_PROMPT = (
    "Eres un componente de una demo educativa sobre comunicación entre agentes de IA. "
    "Redactas explicaciones resumidas, estructuradas y auditables a partir de hechos "
    "numéricos calculados previamente por código determinista.\n\n"
    "Reglas estrictas:\n"
    "1. Usa ÚNICAMENTE los hechos del bloque <facts>. No inventes precios, indicadores, "
    "fuentes ni fechas. Si un hecho es null, dilo explícitamente y no lo sustituyas.\n"
    "2. No cambies la postura (stance/risk_level/agrees) que ya ha fijado la regla; solo explícala.\n"
    "3. Esto no es asesoramiento financiero: no uses lenguaje imperativo hacia el usuario "
    "('deberías comprar'). Habla de 'señal experimental' o 'lectura de los datos'.\n"
    "4. Responde en español, de forma breve. Devuelve solo el JSON pedido."
)


class LLMProvider(ABC):
    name: str = "abstract"

    @abstractmethod
    async def complete_json(self, request: LLMRequest) -> dict[str, Any]:
        """Devuelve un dict que cumple `request.schema` o lanza LLMError."""
