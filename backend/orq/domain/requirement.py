"""Requerimiento y lo que cuelga de él: adjuntos y repositorio conectado."""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime

from .enums import AttachmentKind, FileStatus, PhiClassification
from .errors import DomainError


@dataclass(frozen=True, slots=True)
class RepoFile:
    path: str
    status: FileStatus
    additions: int = 0
    deletions: int = 0
    has_patch: bool = False


@dataclass(frozen=True, slots=True)
class RepoCommit:
    sha: str
    message: str
    author: str
    date: str
    url: str = ""


@dataclass(frozen=True, slots=True)
class RepoInfo:
    """Repositorio conectado de verdad. La conexión real se implementa en ORQ-22."""

    provider: str
    owner: str
    name: str
    full_name: str
    html_url: str
    default_branch: str
    branch: str
    base: str
    head_sha: str
    description: str = ""
    range_label: str = ""
    compare_url: str = ""
    ahead_by: int = 0
    commits: tuple[RepoCommit, ...] = ()
    files: tuple[RepoFile, ...] = ()
    files_truncated: bool = False
    languages: dict[str, int] = field(default_factory=dict)
    fetched_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class Attachment:
    id: str
    kind: AttachmentKind
    name: str
    added_by: str
    added_at: datetime
    detail: str = ""
    #: Presente solo si el repositorio se conectó de verdad.
    repo: RepoInfo | None = None


@dataclass(slots=True)
class Requirement:
    """Agregado raíz. Las ejecuciones viven en su propio repositorio, no aquí dentro."""

    id: str
    title: str
    description: str
    owner: str
    created_at: datetime
    acceptance_criteria: tuple[str, ...] = ()
    phi: PhiClassification = PhiClassification.DESCONOCIDO
    phi_set_by: str = ""
    attachments: tuple[Attachment, ...] = ()

    def __post_init__(self) -> None:
        if not self.title.strip():
            raise DomainError("El requerimiento necesita un título.")
        if not self.owner.strip():
            raise DomainError("El requerimiento necesita un responsable.")

    def has_attachment(self, kind: AttachmentKind) -> bool:
        return any(a.kind == kind for a in self.attachments)

    def attachment(self, kind: AttachmentKind) -> Attachment | None:
        return next((a for a in self.attachments if a.kind == kind), None)

    @property
    def repo(self) -> RepoInfo | None:
        """Información del repositorio, solo si se conectó de verdad."""
        attachment = self.attachment(AttachmentKind.REPO)
        return attachment.repo if attachment else None

    @property
    def handles_phi(self) -> bool:
        """Sin clasificar se trata como «sí»: el agente de Privacidad es obligatorio."""
        return self.phi != PhiClassification.NO

    def with_attachment(self, attachment: Attachment) -> "Requirement":
        if any(a.id == attachment.id for a in self.attachments):
            raise DomainError(f"El adjunto {attachment.id} ya existe en el requerimiento.")
        return replace(self, attachments=self.attachments + (attachment,))

    def with_repo(self, attachment: Attachment) -> "Requirement":
        """Conecta o reconecta el repositorio.

        Se sustituye en vez de añadirse: un requerimiento revisa **un** cambio. Reconectar a otra
        rama o a un commit posterior reemplaza la ficha; las ejecuciones ya hechas conservan el
        `head_sha` que revisaron, que vive en su propia traza.
        """
        if attachment.kind is not AttachmentKind.REPO:
            raise DomainError("with_repo solo acepta un adjunto de tipo repositorio.")
        otros = tuple(a for a in self.attachments if a.kind is not AttachmentKind.REPO)
        return replace(self, attachments=otros + (attachment,))

    def classified_as(self, phi: PhiClassification, *, by: str) -> "Requirement":
        return replace(self, phi=phi, phi_set_by=by)
