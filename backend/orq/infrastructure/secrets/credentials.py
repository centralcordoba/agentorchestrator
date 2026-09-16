"""Credenciales de git tomadas de la bóveda."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from ...application.ports import AuditLog, GitCredential, SecretVault
from ...domain.audit import AuditAction
from ...domain.secrets import SecretKind
from ..git.credentials import ConfiguredCredentialStore

log = logging.getLogger(__name__)


class VaultCredentialStore:
    """Implementa `CredentialStore` con la bóveda por delante y la configuración detrás."""

    def __init__(
        self,
        vault: SecretVault,
        *,
        fallback: ConfiguredCredentialStore | None = None,
        audit: AuditLog | None = None,
        scope: str = "",
    ) -> None:
        self._vault = vault
        self._fallback = fallback
        self._audit = audit
        self._scope = scope

    def for_scope(self, scope: str) -> "VaultCredentialStore":
        """Misma bóveda, mirando primero los secretos de un requerimiento concreto."""
        return VaultCredentialStore(
            self._vault, fallback=self._fallback, audit=self._audit, scope=scope
        )

    async def git_credential(self, host: str) -> GitCredential | None:
        ahora = datetime.now(timezone.utc)
        secreto = await self._vault.reveal(
            SecretKind.GIT_TOKEN, host, scope=self._scope, at=ahora
        )
        if secreto is not None:
            await self._record(secreto.metadata.id, host, "bóveda")
            return GitCredential(
                username=secreto.username or "x-access-token", token=secreto.value
            )

        if self._fallback is not None:
            credencial = await self._fallback.git_credential(host)
            if credencial is not None:
                log.info(
                    "credencial de %s tomada de la configuración; conviene guardarla en la bóveda",
                    host,
                )
                await self._record("", host, "configuración")
                return credencial
        return None

    async def _record(self, secret_id: str, host: str, origen: str) -> None:
        if self._audit is None:
            return
        try:
            await self._audit.append(
                at=datetime.now(timezone.utc),
                actor="sistema",
                action=AuditAction.SECRETO_USADO,
                target=secret_id or f"git:{host}",
                detail=f"credencial de git para {host} ({origen})",
            )
        except Exception:  # pragma: no cover - la auditoría no puede tumbar una clonación
            log.exception("no se pudo registrar el uso de la credencial de %s", host)
