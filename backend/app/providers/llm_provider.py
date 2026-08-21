"""Interfaz de proveedor LLM.

Dos modos de uso:

1. `complete_json(request)` — modo "reglas": el agente ya decidió con código y el LLM solo
   redacta un resumen auditable (JSON con `summary`, `facts_used`, `caveats`).

2. `chat(...)` — modo "llm": el agente razona con el modelo en un bucle de herramientas.
   El modelo puede invocar funciones (calcular indicadores, pedir más historial, retar a otro
   agente...) y termina devolviendo un JSON que cumple el esquema del agente. Los números
   siempre proceden de las herramientas (código determinista), nunca del modelo.
"""
from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional


class LLMError(RuntimeError):
    """Fallo del proveedor LLM (red, cuota, rechazo, salida inválida...)."""


# ------------------------------------------------------------------ modo reglas
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

# ------------------------------------------------------------------ modo llm
AGENT_SYSTEM_PROMPT = (
    "Eres un agente analista dentro de una demo educativa sobre sistemas multiagente. "
    "Trabajas con otros agentes intercambiando mensajes; tu salida la leerán otros agentes y se "
    "mostrará en una traza de observabilidad.\n\n"
    "Reglas estrictas:\n"
    "1. Los ÚNICOS datos válidos son los del bloque <facts> y los resultados de tus herramientas. "
    "Nunca inventes precios, indicadores, fechas ni fuentes. Si te falta información, usa una "
    "herramienta para obtenerla; si no existe herramienta para ello, dilo en `caveats`.\n"
    "2. Antes de fijar una postura, consulta las herramientas de cálculo disponibles. "
    "Cada elemento de `evidence` debe citar el nombre EXACTO de un hecho (clave de <facts> o de un "
    "resultado de herramienta) y lo que observas en él.\n"
    "3. Sé honesto con la incertidumbre: la confianza (0-1) debe reflejar cuántas evidencias "
    "apuntan en la misma dirección. Con señales mixtas, elige NEUTRAL/ESPERAR.\n"
    "4. Esto es una señal experimental derivada de datos históricos, no asesoramiento financiero. "
    "No uses lenguaje imperativo hacia personas.\n"
    "5. Responde en español. Cuando termines, tu ÚLTIMO mensaje debe ser únicamente un objeto JSON "
    "que cumpla el esquema indicado, sin texto adicional ni bloques de código."
)


@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]       # JSON Schema de los argumentos


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class ChatMessage:
    """Mensaje de conversación independiente del proveedor."""

    role: str                                   # "user" | "assistant" | "tool"
    content: Optional[str] = None
    tool_calls: list[ToolCall] = field(default_factory=list)   # solo assistant
    tool_call_id: Optional[str] = None                         # solo tool
    tool_name: Optional[str] = None                            # solo tool


@dataclass
class LLMTurn:
    """Resultado de un turno del modelo: o pide herramientas, o entrega la salida final."""

    assistant: ChatMessage
    tool_calls: list[ToolCall]
    output: Optional[dict[str, Any]]
    usage: Optional[dict[str, Any]] = None


class LLMProvider(ABC):
    name: str = "abstract"
    supports_tools: bool = False

    @abstractmethod
    async def complete_json(self, request: LLMRequest) -> dict[str, Any]:
        """Devuelve un dict que cumple `request.schema` o lanza LLMError."""

    async def chat(
        self,
        *,
        task: str,
        system: str,
        messages: list[ChatMessage],
        tools: list[ToolSpec],
        schema: dict[str, Any],
    ) -> LLMTurn:
        """Un turno de conversación con herramientas. Lanza LLMError si falla."""
        raise LLMError(f"El proveedor {self.name} no soporta el modo de agentes con herramientas.")


class ThrottledLLMProvider(LLMProvider):
    """Limita el número de llamadas simultáneas a un proveedor real (cuotas / límites de tasa).

    Varios símbolos y agentes trabajan en paralelo; sin este límite, una ejecución de 5 símbolos
    puede lanzar 6-10 peticiones a la vez.
    """

    def __init__(self, inner: LLMProvider, max_concurrency: int) -> None:
        self._inner = inner
        self._sem = asyncio.Semaphore(max(1, max_concurrency))
        self.name = inner.name
        self.supports_tools = inner.supports_tools

    async def complete_json(self, request: LLMRequest) -> dict[str, Any]:
        async with self._sem:
            return await self._inner.complete_json(request)

    async def chat(self, **kwargs: Any) -> LLMTurn:
        async with self._sem:
            return await self._inner.chat(**kwargs)


# ------------------------------------------------------------------ coste
def with_cost(
    usage: dict[str, Any],
    *,
    provider_cost_usd: Optional[float] = None,
    price_input_per_mtok: Optional[float] = None,
    price_output_per_mtok: Optional[float] = None,
    mock: bool = False,
) -> dict[str, Any]:
    """Completa un dict de uso con `cost_usd` y `cost_source`.

    Prioridad: coste informado por el proveedor → estimación por precios conocidos → desconocido.
    """
    from ..config import settings

    usage = dict(usage)
    if mock:
        usage.update({"cost_usd": 0.0, "cost_source": "mock"})
        return usage
    if provider_cost_usd is not None:
        usage.update({"cost_usd": round(float(provider_cost_usd), 6), "cost_source": "provider"})
        return usage
    pin = settings.llm_price_input_per_mtok if settings.llm_price_input_per_mtok is not None else price_input_per_mtok
    pout = settings.llm_price_output_per_mtok if settings.llm_price_output_per_mtok is not None else price_output_per_mtok
    tin, tout = usage.get("input_tokens"), usage.get("output_tokens")
    if pin is not None and pout is not None and isinstance(tin, (int, float)) and isinstance(tout, (int, float)):
        usage.update({
            "cost_usd": round(tin / 1e6 * pin + tout / 1e6 * pout, 6),
            "cost_source": "estimated",
            "price_input_per_mtok": pin,
            "price_output_per_mtok": pout,
        })
        return usage
    usage.update({"cost_usd": None, "cost_source": "unknown"})
    return usage


# ------------------------------------------------------------------ utilidades
def render_agent_prompt(task: str, instructions: str, facts: dict[str, Any], schema: dict[str, Any]) -> str:
    import json

    return (
        f"Tarea: {task}\n\n"
        f"Instrucciones:\n{instructions}\n\n"
        f"<facts>\n{json.dumps(facts, ensure_ascii=False, indent=2, default=str)}\n</facts>\n\n"
        "Cuando hayas terminado de usar herramientas, responde ÚNICAMENTE con un objeto JSON que cumpla "
        f"este esquema:\n{json.dumps(schema, ensure_ascii=False)}"
    )


def extract_json_object(text: str) -> Optional[dict[str, Any]]:
    """Extrae el primer objeto JSON del texto (tolera ```json ... ``` y prefijos)."""
    import json
    import re

    candidate = (text or "").strip()
    if candidate.startswith("```"):
        candidate = re.sub(r"^```[a-zA-Z]*\s*|\s*```$", "", candidate, flags=re.S).strip()
    attempts = [candidate]
    m = re.search(r"\{.*\}", candidate, re.S)
    if m:
        attempts.append(m.group(0))
    for attempt in attempts:
        if not attempt:
            continue
        try:
            obj = json.loads(attempt)
        except ValueError:
            continue
        if isinstance(obj, dict):
            return obj
    return None
