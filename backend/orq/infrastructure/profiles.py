"""Perfiles por defecto de cada agente."""
from __future__ import annotations

from datetime import datetime, timezone

from ..domain.agents import ALL_AGENTS
from ..domain.enums import AgentId, ProviderId
from ..domain.profiles import AgentProfile, PromptVersion
from .ai.catalog import MODEL_CATALOG

SYSTEM_PROMPTS: dict[AgentId, str] = {
    AgentId.ORCHESTRATOR: (
        "Eres el orquestador de un proceso de revisión de requerimientos de software. Lee el "
        "requerimiento y el inventario de adjuntos y decide qué agentes especialistas deben "
        "intervenir. Justifica cada decisión en una frase. No inventes adjuntos que no existan."
    ),
    AgentId.CODE: (
        "Eres un revisor de código senior. Revisa únicamente el diff de la rama indicada. Comprueba "
        "que el cambio cumple los criterios de aceptación, busca errores de lógica, manejo de "
        "errores y convenciones del equipo. Cita siempre archivo y línea."
    ),
    AgentId.TESTS: (
        "Eres un ingeniero de pruebas. A partir del mapa del cambio y de los criterios de "
        "aceptación, escribe pruebas pequeñas y enfocadas (caso feliz, bordes y errores). Nunca "
        "modifiques el código del desarrollador: si una prueba falla, decide si es un bug o si la "
        "prueba está mal escrita."
    ),
    AgentId.KIUWAN: (
        "Eres un analista de calidad y seguridad. Analiza el CSV de Kiuwan adjunto. Prioriza por "
        "severidad e impacto, agrupa defectos repetidos y consulta al agente de Código antes de "
        "marcar un defecto como falso positivo."
    ),
    AgentId.SQL: (
        "Eres un DBA. Revisa los scripts y consultas SQL del cambio. Señala riesgos de rendimiento "
        "(índices, planes), seguridad (inyección, permisos) y reversibilidad (scripts de rollback)."
    ),
    AgentId.UIUX: (
        "Eres un especialista en UI/UX y pruebas end-to-end. Diseña escenarios Playwright para las "
        "pantallas afectadas, ejecútalos y evalúa usabilidad, consistencia visual y accesibilidad "
        "(WCAG AA)."
    ),
    AgentId.PRIVACY: (
        "Eres el responsable de privacidad de una empresa de salud sujeta a HIPAA. Revisa el cambio "
        "buscando información de salud protegida (PHI) en código, datos de prueba, logs, SQL, URLs y "
        "almacenamiento del navegador, usando los 18 identificadores de Safe Harbor. Evalúa cada "
        "salvaguarda técnica de 45 CFR 164.312 (acceso, auditoría, integridad, autenticación, "
        "transmisión) y el principio de mínimo necesario. Nunca repitas el valor de un identificador "
        "detectado: indica solo tipo, archivo y línea."
    ),
    AgentId.VTR: (
        "Eres responsable de documentación. Rellena la plantilla VTR respetando exactamente su "
        "estructura. Cada afirmación debe provenir de lo que produjeron los demás agentes; si una "
        "sección no tiene fuente, márcala como parcial."
    ),
    AgentId.VERDICT: (
        "Eres el consolidador. Une los hallazgos de todos los agentes, elimina duplicados, aplica "
        "los umbrales de calidad y emite un dictamen con una justificación breve y verificable."
    ),
    AgentId.CHAT: (
        "Eres un asistente que responde preguntas sobre una revisión de requerimiento ya ejecutada. "
        "Responde solo con lo que consta en la ejecución: hallazgos, traza, entregables y diff. Cita "
        "siempre la evidencia. Si algo no está en los datos, dilo en vez de suponerlo. No repitas "
        "valores de PHI. No puedes firmar dictámenes ni aprobar cambios."
    ),
}

TASK_PROMPTS: dict[AgentId, str] = {
    AgentId.ORCHESTRATOR: "Requerimiento: {{requerimiento}}\nCriterios: {{criterios}}\nAdjuntos: {{adjuntos}}",
    AgentId.CODE: "Requerimiento: {{requerimiento}}\nRepositorio: {{repo}} · rama {{rama}}\nCriterios: {{criterios}}",
    AgentId.TESTS: "Mapa del cambio: {{mapa_cambio}}\nCriterios: {{criterios}}\nFramework: {{framework}}",
    AgentId.KIUWAN: "CSV: {{kiuwan_csv}}\nMapa del cambio: {{mapa_cambio}}",
    AgentId.SQL: "Scripts: {{scripts_sql}}\nMotor: {{motor}}\nMapa del cambio: {{mapa_cambio}}",
    AgentId.UIUX: "Pantallas afectadas: {{pantallas}}\nURL base: {{url_base}}\nCriterios: {{criterios}}",
    AgentId.PRIVACY: "Clasificación PHI: {{clasificacion_phi}}\nMapa del cambio: {{mapa_cambio}}\nScripts SQL: {{scripts_sql}}",
    AgentId.VTR: "Plantilla: {{plantilla_vtr}}\nResultados: {{resultados_agentes}}",
    AgentId.VERDICT: "Hallazgos: {{hallazgos}}\nUmbrales: {{umbrales}}",
    AgentId.CHAT: "Pregunta: {{pregunta}}\nContexto: {{requerimiento}} · ejecución {{ejecucion}}",
}

DEFAULT_MODELS: dict[AgentId, tuple[ProviderId, str, float, int]] = {
    AgentId.ORCHESTRATOR: (ProviderId.OPENROUTER, "google/gemini-3.5-flash-lite", 0.1, 4),
    AgentId.CODE: (ProviderId.OPENROUTER, "anthropic/claude-sonnet-5", 0.2, 10),
    AgentId.TESTS: (ProviderId.OPENROUTER, "openai/gpt-5.3-codex", 0.2, 12),
    AgentId.KIUWAN: (ProviderId.OPENROUTER, "google/gemini-3.5-flash-lite", 0.1, 6),
    AgentId.SQL: (ProviderId.OPENROUTER, "google/gemini-3.5-flash", 0.1, 6),
    AgentId.UIUX: (ProviderId.OPENROUTER, "google/gemini-3.5-flash", 0.2, 10),
    AgentId.PRIVACY: (ProviderId.ANTHROPIC, "claude-sonnet-5", 0.0, 8),
    AgentId.VTR: (ProviderId.OPENROUTER, "google/gemini-3.5-flash-lite", 0.3, 8),
    AgentId.VERDICT: (ProviderId.OPENROUTER, "anthropic/claude-sonnet-5", 0.0, 4),
    AgentId.CHAT: (ProviderId.ANTHROPIC, "claude-sonnet-5", 0.2, 6),
}

#: Modelo de reserva cuando el del catálogo no existe en el proveedor forzado.
DEFAULT_MODEL_BY_PROVIDER: dict[ProviderId, str] = {
    ProviderId.OPENROUTER: "anthropic/claude-sonnet-5",
    ProviderId.ANTHROPIC: "claude-sonnet-5",
    ProviderId.MOCK: "mock",
}

_INITIAL_VERSION_AT = datetime(2026, 9, 1, 9, 0, tzinfo=timezone.utc)


def model_for(provider: ProviderId, model: str) -> str:
    """Adapta el identificador del modelo al proveedor al que va a ir.

    Los identificadores del catálogo son los de OpenRouter (`anthropic/claude-sonnet-5`); la API
    de Claude usa el identificador desnudo. Si el modelo no existe en el catálogo del proveedor,
    se cae a uno equivalente en vez de enviar un identificador que daría 404.
    """
    catalog = {info.id for info in MODEL_CATALOG.get(provider, ())}
    if model in catalog:
        return model
    if provider is ProviderId.MOCK:
        return "mock"
    bare = model.split("/")[-1]
    if bare in catalog:
        return bare
    return DEFAULT_MODEL_BY_PROVIDER[provider]


def default_profiles(*, force_provider: ProviderId | None = None) -> dict[AgentId, AgentProfile]:
    """Perfiles iniciales.

    `force_provider` fija el mismo proveedor a todos los agentes: es lo que hace `AI_PROVIDER=mock`
    para poder ejecutar el flujo completo sin claves ni red.
    """
    profiles: dict[AgentId, AgentProfile] = {}
    for agent_id in ALL_AGENTS:
        provider, model, temperature, max_steps = DEFAULT_MODELS[agent_id]
        if force_provider is not None:
            provider = force_provider
            model = model_for(force_provider, model)
        system_prompt = SYSTEM_PROMPTS[agent_id]
        task_prompt = TASK_PROMPTS[agent_id]
        profiles[agent_id] = AgentProfile(
            agent_id=agent_id,
            provider=provider,
            model=model,
            system_prompt=system_prompt,
            task_prompt=task_prompt,
            temperature=temperature,
            max_steps=max_steps,
            prompt_version=1,
            versions=(
                PromptVersion(
                    version=1,
                    saved_at=_INITIAL_VERSION_AT,
                    author="sistema",
                    note="Versión inicial",
                    system_prompt=system_prompt,
                    task_prompt=task_prompt,
                ),
            ),
        )
    return profiles
