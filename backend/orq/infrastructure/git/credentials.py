"""Credenciales de git por host."""
from __future__ import annotations

import logging
from urllib.parse import urlsplit

from ...application.ports import GitCredential

log = logging.getLogger(__name__)


def host_of(url: str) -> str:
    """Host de una URL de repositorio, tanto HTTPS como SSH (`git@host:org/repo`)."""
    texto = url.strip()
    if texto.startswith("git@"):
        return texto[4:].split(":", 1)[0].lower()
    partes = urlsplit(texto if "://" in texto else f"https://{texto}")
    return (partes.hostname or "").lower()


def parse_tokens(raw: str) -> dict[str, GitCredential]:
    """Lee `host=token` o `host=usuario:token`, separados por comas.

    Formato deliberadamente simple: es configuración de una sola máquina hasta que exista la
    bóveda. Un valor mal escrito se ignora con un aviso, sin decir qué había.
    """
    credenciales: dict[str, GitCredential] = {}
    for parte in raw.split(","):
        parte = parte.strip()
        if not parte:
            continue
        host, _, valor = parte.partition("=")
        host = host.strip().lower()
        if not host or not valor:
            log.warning("entrada de GIT_TOKENS ignorada: falta el host o el valor")
            continue
        usuario, sep, token = valor.partition(":")
        if sep:
            credenciales[host] = GitCredential(username=usuario.strip(), token=token.strip())
        else:
            # Sin usuario: es un token personal. El usuario da igual, pero git exige uno.
            credenciales[host] = GitCredential(username="x-access-token", token=valor.strip())
    return credenciales


class ConfiguredCredentialStore:
    """Implementa el puerto `CredentialStore` con lo que hay en la configuración."""

    def __init__(self, tokens: str = "") -> None:
        self._por_host = parse_tokens(tokens)
        if self._por_host:
            log.info(
                "credenciales de git configuradas para: %s", ", ".join(sorted(self._por_host))
            )

    async def git_credential(self, host: str) -> GitCredential | None:
        return self._por_host.get(host.lower())

    @property
    def hosts(self) -> tuple[str, ...]:
        """Hosts con credencial. Se puede enseñar: son nombres, no secretos."""
        return tuple(sorted(self._por_host))
