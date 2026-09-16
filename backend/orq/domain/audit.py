"""Auditoría encadenada."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

#: Hash de la entrada anterior cuando no hay ninguna.
GENESIS = "0" * 64


class AuditAction(str, Enum):
    REQUERIMIENTO_CREADO = "requerimiento_creado"
    CLASIFICACION_PHI = "clasificacion_phi"
    #: El guardarraíl encontró identificadores en un texto. Se registran los tipos, nunca el valor.
    PHI_DETECTADA = "phi_detectada"
    REPOSITORIO_CONECTADO = "repositorio_conectado"
    #: Bóveda de secretos (ORQ-18). El detalle describe; el valor no aparece nunca.
    SECRETO_GUARDADO = "secreto_guardado"
    SECRETO_REVOCADO = "secreto_revocado"
    SECRETO_USADO = "secreto_usado"
    PLAN_SUGERIDO = "plan_sugerido"
    EJECUCION_INICIADA = "ejecucion_iniciada"
    EJECUCION_CANCELADA = "ejecucion_cancelada"
    EJECUCION_REANUDADA = "ejecucion_reanudada"
    #: Identidad y acceso (ORQ-5). Nunca llevan la contraseña ni el testigo de sesión.
    SESION_INICIADA = "sesion_iniciada"
    SESION_CERRADA = "sesion_cerrada"
    ACCESO_FALLIDO = "acceso_fallido"
    USUARIO_CREADO = "usuario_creado"
    USUARIO_ACTUALIZADO = "usuario_actualizado"
    CONTRASENA_CAMBIADA = "contrasena_cambiada"
    AJUSTE_LOCAL = "ajuste_local"


@dataclass(frozen=True, slots=True)
class AuditEntry:
    """Una acción registrada. `detail` describe, nunca copia contenido con PHI."""

    at: datetime
    actor: str
    action: AuditAction
    target: str
    detail: str = ""
    prev_hash: str = GENESIS
    seq: int = 0

    @property
    def hash(self) -> str:
        return compute_hash(self)


def compute_hash(entry: AuditEntry) -> str:
    """Hash de la entrada, encadenado con la anterior."""
    payload = "|".join(
        (
            entry.prev_hash,
            entry.at.isoformat(),
            entry.actor,
            entry.action.value,
            entry.target,
            entry.detail,
        )
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def verify_chain(entries: list[AuditEntry], *, hashes: list[str] | None = None) -> int | None:
    """Comprueba la cadena. Devuelve el índice de la primera entrada alterada, o `None`.

    `hashes` son los hashes almacenados: si el recalculado no coincide, la fila se tocó.
    """
    previous = GENESIS
    for index, entry in enumerate(entries):
        if entry.prev_hash != previous:
            return index
        current = compute_hash(entry)
        if hashes is not None and hashes[index] != current:
            return index
        previous = current
    return None
