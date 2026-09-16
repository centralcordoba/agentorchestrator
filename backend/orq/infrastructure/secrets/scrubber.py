"""Tachado de secretos en todo lo que se escribe."""
from __future__ import annotations

import logging

MASK = "«secreto»"

#: Por debajo de esto, tachar haría ilegible cualquier texto (y no es un secreto serio).
MIN_LENGTH = 8


class SecretScrubber:
    """Valores activos en memoria, para tacharlos de cualquier texto."""

    def __init__(self) -> None:
        self._values: set[str] = set()

    def remember(self, *values: str) -> None:
        for value in values:
            limpio = (value or "").strip()
            if len(limpio) >= MIN_LENGTH:
                self._values.add(limpio)

    def forget(self, *values: str) -> None:
        for value in values:
            self._values.discard((value or "").strip())

    def clear(self) -> None:
        self._values.clear()

    def __len__(self) -> int:
        return len(self._values)

    def scrub(self, text: str) -> str:
        """Tacha todos los valores conocidos.

        Los más largos primero: si un secreto contiene a otro, sustituir antes el corto dejaría
        media cadena del largo a la vista.
        """
        if not text or not self._values:
            return text
        resultado = text
        for value in sorted(self._values, key=len, reverse=True):
            if value in resultado:
                resultado = resultado.replace(value, MASK)
        return resultado

    def contains_secret(self, text: str) -> bool:
        """¿Este texto lleva algún valor sin tachar? Lo usan las pruebas y los asertos."""
        return any(value in text for value in self._values)

    def logging_filter(self) -> logging.Filter:
        """Filtro para el logger raíz: tacha el mensaje y los argumentos de cada registro."""
        scrubber = self

        class _Filtro(logging.Filter):
            def filter(self, record: logging.LogRecord) -> bool:
                # Se formatea aquí: si se dejaran los argumentos sueltos, el `Formatter` los
                # uniría después y el secreto volvería a aparecer.
                try:
                    mensaje = record.getMessage()
                except Exception:  # pragma: no cover - argumentos mal formados
                    return True
                limpio = scrubber.scrub(mensaje)
                if limpio != mensaje:
                    record.msg = limpio
                    record.args = ()
                if record.exc_text:
                    record.exc_text = scrubber.scrub(record.exc_text)
                return True

        return _Filtro()

    def install(self, logger: logging.Logger | None = None) -> logging.Filter:
        """Engancha el filtro al logger raíz. Devuelve el filtro por si hay que quitarlo."""
        destino = logger or logging.getLogger()
        filtro = self.logging_filter()
        destino.addFilter(filtro)
        # `addFilter` en el raíz no alcanza a lo que emiten sus hijos: se engancha también a
        # cada manejador, por donde pasa todo lo que llega a salir.
        for handler in destino.handlers:
            handler.addFilter(filtro)
        return filtro
