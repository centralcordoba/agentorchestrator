"""Cifrado en reposo de las columnas con contenido del cliente."""
from __future__ import annotations

import json
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

from ...domain.errors import DomainError


class CipherError(DomainError):
    """La clave falta o no sirve para descifrar lo guardado."""


class Cipher:
    """Cifra y descifra los campos sensibles."""

    def __init__(self, key: str) -> None:
        if not key:
            raise CipherError(
                "Falta DB_ENCRYPTION_KEY: la base guarda contenido que puede incluir PHI y no se "
                "escribe en claro. Genera una con `Cipher.generate_key()`."
            )
        try:
            self._fernet = Fernet(key.encode("utf-8") if isinstance(key, str) else key)
        except (ValueError, TypeError) as exc:
            raise CipherError("DB_ENCRYPTION_KEY no es una clave Fernet válida.") from exc

    @staticmethod
    def generate_key() -> str:
        return Fernet.generate_key().decode("utf-8")

    def encrypt(self, value: str) -> bytes:
        return self._fernet.encrypt((value or "").encode("utf-8"))

    def decrypt(self, value: bytes | None) -> str:
        if value is None:
            return ""
        try:
            return self._fernet.decrypt(bytes(value)).decode("utf-8")
        except InvalidToken as exc:
            raise CipherError(
                "No se pudo descifrar una columna: la clave no es la que cifró estos datos."
            ) from exc

    def encrypt_json(self, value: Any) -> bytes:
        return self.encrypt(json.dumps(value, ensure_ascii=False, default=str))

    def decrypt_json(self, value: bytes | None, default: Any = None) -> Any:
        raw = self.decrypt(value)
        if not raw:
            return default
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise CipherError("Una columna cifrada no contenía JSON válido.") from exc
