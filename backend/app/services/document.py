"""Document service: upload validation, content hashing, storage keys, status."""

from __future__ import annotations

import hashlib
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import DocumentKind, DocumentStatus
from app.domain.errors import NotFoundError, ValidationFailedError
from app.models.document import Document
from app.repositories.document import DocumentRepository

# Allowed upload types: pdf, docx, txt, md (plan §19, §23).
_ALLOWED_MIME: dict[DocumentKind, set[str]] = {
    DocumentKind.RESUME: {
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "text/plain",
        "text/markdown",
    },
    DocumentKind.JD: {
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "text/plain",
        "text/markdown",
    },
    DocumentKind.DEBRIEF: {"text/plain", "text/markdown"},
    DocumentKind.TRANSCRIPT: {"text/plain", "text/markdown"},
}

_MAX_SIZE_MB = 5


def content_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class DocumentService:
    def __init__(
        self,
        session: AsyncSession,
        *,
        storage_dir: Path | None = None,
        max_size_mb: int = _MAX_SIZE_MB,
    ) -> None:
        self.session = session
        self.documents = DocumentRepository(session)
        self.storage_dir = storage_dir
        self.max_size_mb = max_size_mb

    async def upload(
        self,
        *,
        user_id: int,
        kind: DocumentKind,
        filename: str,
        mime: str,
        data: bytes,
    ) -> Document:
        self.validate_upload(kind=kind, filename=filename, mime=mime, size=len(data))
        digest = content_hash(data)

        existing = await self.documents.get_by_hash(user_id, digest)
        if existing:
            raise ValidationFailedError(
                "document with identical content already uploaded",
                details={"document_id": existing.id},
            )

        storage_key = None
        if self.storage_dir is not None:
            storage_key = await self._store(data, kind, digest, filename)

        doc = Document(
            user_id=user_id,
            kind=kind,
            filename=filename,
            mime=mime,
            size=len(data),
            content_hash=digest,
            storage_key=storage_key,
            status=DocumentStatus.PENDING,
        )
        await self.documents.add(doc)
        return doc

    def validate_upload(self, *, kind: DocumentKind, filename: str, mime: str, size: int) -> None:
        DocumentService._validate_upload(
            kind=kind, filename=filename, mime=mime, size=size, max_size_mb=self.max_size_mb
        )

    @staticmethod
    def _validate_upload(
        *,
        kind: DocumentKind,
        filename: str,
        mime: str,
        size: int,
        max_size_mb: int = _MAX_SIZE_MB,
    ) -> None:
        if kind not in _ALLOWED_MIME:
            raise ValidationFailedError(f"unsupported document kind: {kind}")
        if mime not in _ALLOWED_MIME[kind]:
            raise ValidationFailedError(
                f"unsupported file type for {kind.value}: {mime}",
                details={"allowed": sorted(_ALLOWED_MIME[kind])},
            )
        if size <= 0:
            raise ValidationFailedError("empty file")
        if size > max_size_mb * 1024 * 1024:
            raise ValidationFailedError(
                f"file exceeds {max_size_mb}MB limit", details={"size": size}
            )
        if not filename.strip():
            raise ValidationFailedError("filename required")

    async def get_document(self, user_id: int, document_id: int) -> Document:
        doc = await self.documents.get_or_raise(document_id, name="document")
        if doc.user_id != user_id:
            raise NotFoundError("document not found")
        return doc

    async def list_documents(
        self, user_id: int, *, kind: DocumentKind | None = None
    ) -> list[Document]:
        return list(await self.documents.list_for_user(user_id, kind=kind))

    async def delete_document(self, user_id: int, document_id: int) -> None:
        doc = await self.get_document(user_id, document_id)
        await self.documents.delete(doc)
        if self.storage_dir is not None and doc.storage_key:
            path = self.storage_dir / doc.storage_key
            path.unlink(missing_ok=True)

    async def _store(self, data: bytes, kind: DocumentKind, digest: str, filename: str) -> str:
        assert self.storage_dir is not None
        subdir = self.storage_dir / kind.value
        subdir.mkdir(parents=True, exist_ok=True)
        ext = Path(filename).suffix.lower()
        key = f"{digest}{ext}"
        (subdir / key).write_bytes(data)
        return str(Path(kind.value) / key)
