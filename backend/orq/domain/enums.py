"""Enumeraciones del dominio."""
from __future__ import annotations

from enum import Enum


class AgentId(str, Enum):
    """Agentes gobernados. `CHAT` no participa en el flujo de revisión."""

    ORCHESTRATOR = "orchestrator"
    CODE = "code"
    TESTS = "tests"
    KIUWAN = "kiuwan"
    SQL = "sql"
    UIUX = "uiux"
    PRIVACY = "privacy"
    VTR = "vtr"
    VERDICT = "verdict"
    CHAT = "chat"


class PhiClassification(str, Enum):
    """¿El requerimiento puede tocar PHI? `DESCONOCIDO` se trata como `SI`."""

    SI = "si"
    NO = "no"
    DESCONOCIDO = "desconocido"


class ProviderId(str, Enum):
    OPENROUTER = "openrouter"
    ANTHROPIC = "anthropic"
    MOCK = "mock"


class AttachmentKind(str, Enum):
    REPO = "repo"
    VTR_TEMPLATE = "vtr_template"
    KIUWAN_CSV = "kiuwan_csv"
    SQL = "sql"


class FileStatus(str, Enum):
    ADDED = "added"
    MODIFIED = "modified"
    REMOVED = "removed"
    RENAMED = "renamed"


class Severity(str, Enum):
    CRITICA = "critica"
    ALTA = "alta"
    MEDIA = "media"
    BAJA = "baja"
    INFO = "info"


class AgentRunStatus(str, Enum):
    PENDIENTE = "pendiente"
    TRABAJANDO = "trabajando"
    COMPLETADO = "completado"
    OMITIDO = "omitido"
    FALLIDO = "fallido"


class RunStatus(str, Enum):
    """Estado de la ejecución completa."""

    EN_CURSO = "en_curso"
    COMPLETADA = "completada"
    CANCELADA = "cancelada"
    FALLIDA = "fallida"


class TraceEventType(str, Enum):
    RUN_STARTED = "run_started"
    AGENT_STARTED = "agent_started"
    LLM_CALL = "llm_call"
    TOOL_CALLED = "tool_called"
    MESSAGE_SENT = "message_sent"
    GUARDRAIL_APPLIED = "guardrail_applied"
    AGENT_COMPLETED = "agent_completed"
    AGENT_SKIPPED = "agent_skipped"
    AGENT_FAILED = "agent_failed"
    AGENT_DEGRADED = "agent_degraded"
    PHI_REDACTED = "phi_redacted"
    RUN_COMPLETED = "run_completed"
    RUN_CANCELLED = "run_cancelled"


class Verdict(str, Enum):
    APROBADO = "APROBADO"
    APROBADO_CON_OBSERVACIONES = "APROBADO_CON_OBSERVACIONES"
    RECHAZADO = "RECHAZADO"


class PhiIdentifier(str, Enum):
    """Tipos de identificador de paciente. Se registra el tipo; nunca el valor."""

    NOMBRE = "nombre"
    FECHA = "fecha"
    TELEFONO = "telefono"
    EMAIL = "email"
    SSN = "ssn"
    HISTORIA_CLINICA = "historia_clinica"
    AFILIADO = "afiliado"
    DIRECCION = "direccion"
    DOCUMENTO = "documento"
    DATO_PACIENTE = "dato_paciente"


class PhiWhere(str, Enum):
    """Dónde apareció el identificador: cambia la gravedad y la recomendación."""

    DATOS_PRUEBA = "datos_prueba"
    LOG = "log"
    SQL = "sql"
    CODIGO = "codigo"
    URL = "url"
    ALMACENAMIENTO_LOCAL = "almacenamiento_local"


class SafeguardId(str, Enum):
    """Salvaguardas técnicas de 45 CFR 164.312."""

    ACCESO = "acceso"
    AUDITORIA = "auditoria"
    INTEGRIDAD = "integridad"
    AUTENTICACION = "autenticacion"
    TRANSMISION = "transmision"


class WarningLevel(str, Enum):
    BLOQUEO = "bloqueo"
    AVISO = "aviso"
