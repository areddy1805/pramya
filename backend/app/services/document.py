"""Document service: upload validation, content hashing, storage keys, status.

Phase 2.1: upload establishes the document (PENDING), runs parsing
(PARSING), and transitions to PARSED (with parsed_at) or FAILED. Parsed
content is returned in-memory as a handoff to Phase 2.2 ingestion — never
persisted (schema has no parsed_text column by design).
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import DocumentKind, DocumentStatus
from app.domain.errors import NotFoundError, ValidationFailedError
from app.knowledge.parsing import ParsedDocument, parse_document_with_timeout
from app.models.document import Document
from app.observability import record_event
from app.repositories.document import DocumentRepository
from app.repositories.user import CandidateProfileRepository

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


def sanitize_suffix(suffix: str) -> str:
    """Defense-in-depth: storage keys derive from a content digest plus a
    whitelisted extension, never from a client-supplied filename (Phase I)."""
    if not suffix or len(suffix) > 10:
        return ""
    if not all(c.isalnum() or c == "." for c in suffix):
        return ""
    return suffix


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
        max_pages: int = 50,
        parse_timeout_seconds: float = 30.0,
    ) -> None:
        self.session = session
        self.documents = DocumentRepository(session)
        self.profiles = CandidateProfileRepository(session)
        self.storage_dir = storage_dir
        self.max_size_mb = max_size_mb
        self.max_pages = max_pages
        self.parse_timeout_seconds = parse_timeout_seconds

    async def _require_profile(self, user_id: int, profile_id: int) -> None:
        """Ownership check: the profile must belong to the user."""
        profile = await self.profiles.get_for_user(user_id, profile_id)
        if profile is None:
            raise NotFoundError("candidate profile not found")

    async def upload(
        self,
        *,
        user_id: int,
        kind: DocumentKind,
        filename: str,
        mime: str,
        data: bytes,
        profile_id: int | None = None,
    ) -> tuple[Document, ParsedDocument]:
        """Establish the document, parse it, and transition status.

        Returns ``(document, parsed)`` on success; on parse failure the
        document is left in FAILED state and ValidationFailedError is raised
        with actionable details. Parsed text is the in-memory handoff to
        ingestion.

        ``profile_id`` is the owning career profile (production callers
        always pass it); when omitted (legacy internal/test callers) the
        document is attributed to the user's default profile and dedup is
        user-scoped. Identical content within the same (user, profile) is
        rejected with ValidationFailedError carrying details.document_id
        — the API layer translates that into an idempotent dedup response.
        """
        if profile_id is not None:
            await self._require_profile(user_id, profile_id)
        else:
            default = await self.profiles.get_by_user(user_id)
            profile_id = default.id if default is not None else None
        self.validate_upload(kind=kind, filename=filename, mime=mime, size=len(data))
        digest = content_hash(data)

        existing = await self.documents.get_by_hash(user_id, digest, profile_id=profile_id)
        if existing and existing.status != DocumentStatus.FAILED:
            raise ValidationFailedError(
                "document with identical content already uploaded",
                details={"document_id": existing.id, "profile_id": profile_id},
            )

        storage_key = None
        if self.storage_dir is not None:
            storage_key = await self._store(data, kind, digest, filename)

        doc = Document(
            user_id=user_id,
            profile_id=profile_id,
            kind=kind,
            filename=filename,
            mime=mime,
            size=len(data),
            content_hash=digest,
            storage_key=storage_key,
            status=DocumentStatus.PENDING,
        )
        await self.documents.add(doc)

        doc.status = DocumentStatus.PARSING
        await self.documents.flush()
        try:
            parsed = await parse_document_with_timeout(
                data=data,
                kind=kind,
                mime=mime,
                filename=filename,
                content_hash=digest,
                max_pages=self.max_pages,
                timeout_seconds=self.parse_timeout_seconds,
            )
        except ValidationFailedError:
            doc.status = DocumentStatus.FAILED
            await self.documents.flush()
            raise
        except TimeoutError as exc:
            doc.status = DocumentStatus.FAILED
            await self.documents.flush()
            raise ValidationFailedError(
                "document parsing timed out",
                details={"filename": filename, "timeout_seconds": self.parse_timeout_seconds},
            ) from exc

        doc.status = DocumentStatus.PARSED
        doc.parsed_at = datetime.now(UTC)
        await self.documents.flush()
        record_event(
            "resume_uploaded" if kind == DocumentKind.RESUME else "document_uploaded",
            user_id=user_id,
            profile_id=profile_id,
            document_id=doc.id,
            kind=kind.value,
            status=doc.status.value,
        )
        return doc, parsed

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

    async def get_document(
        self, user_id: int, document_id: int, *, profile_id: int | None = None
    ) -> Document:
        doc = await self.documents.get_or_raise(document_id, name="document")
        if doc.user_id != user_id:
            raise NotFoundError("document not found")
        if profile_id is not None and doc.profile_id != profile_id:
            # Document exists but belongs to a different profile of this
            # user: treat as not found (isolation, no data leak).
            raise NotFoundError("document not found")
        return doc

    async def list_documents(
        self,
        user_id: int,
        *,
        kind: DocumentKind | None = None,
        profile_id: int | None = None,
    ) -> list[Document]:
        return list(await self.documents.list_for_user(user_id, kind=kind, profile_id=profile_id))

    async def delete_document(
        self, user_id: int, document_id: int, *, profile_id: int | None = None
    ) -> None:
        doc = await self.get_document(user_id, document_id, profile_id=profile_id)
        await self.documents.delete(doc)
        if self.storage_dir is not None and doc.storage_key:
            path = self.storage_dir / doc.storage_key
            path.unlink(missing_ok=True)
        record_event(
            "document_deleted",
            user_id=user_id,
            profile_id=profile_id,
            document_id=document_id,
            kind=str(doc.kind),
        )

    async def read_stored_bytes(
        self, user_id: int, document_id: int, *, profile_id: int | None = None
    ) -> bytes:
        """Read a document's stored upload bytes (used for re-parse/index)."""
        doc = await self.get_document(user_id, document_id, profile_id=profile_id)
        if self.storage_dir is None or not doc.storage_key:
            raise ValidationFailedError(
                "document content not retained (storage disabled)",
                details={"document_id": document_id},
            )
        path = self.storage_dir / doc.storage_key
        if not path.exists():
            raise NotFoundError("stored document content missing")
        return path.read_bytes()

    async def _store(self, data: bytes, kind: DocumentKind, digest: str, filename: str) -> str:
        assert self.storage_dir is not None
        subdir = self.storage_dir / kind.value
        subdir.mkdir(parents=True, exist_ok=True)
        ext = sanitize_suffix(Path(filename).suffix.lower())
        key = f"{digest}{ext}"
        (subdir / key).write_bytes(data)
        return str(Path(kind.value) / key)
