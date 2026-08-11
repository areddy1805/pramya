"""Unit tests: document upload validation + idempotency key (no DB)."""

import pytest

from app.domain.enums import DocumentKind
from app.domain.errors import ValidationFailedError
from app.services.document import DocumentService, content_hash
from app.services.idempotency import make_idempotency_key


def test_content_hash_sha256() -> None:
    assert content_hash(b"hello") == content_hash(b"hello")
    assert content_hash(b"hello") != content_hash(b"world")
    assert len(content_hash(b"x")) == 64


def test_upload_validation_accepts_pdf() -> None:
    # validate_upload is pure — no session/storage needed
    DocumentService._validate_upload(
        kind=DocumentKind.RESUME,
        filename="r.pdf",
        mime="application/pdf",
        size=1024,
    )


def test_upload_validation_rejects_script() -> None:
    with pytest.raises(ValidationFailedError):
        DocumentService._validate_upload(
            kind=DocumentKind.RESUME,
            filename="r.pdf",
            mime="application/x-sh",
            size=1024,
        )


def test_upload_validation_rejects_oversize() -> None:
    with pytest.raises(ValidationFailedError):
        DocumentService._validate_upload(
            kind=DocumentKind.RESUME,
            filename="r.pdf",
            mime="application/pdf",
            size=5 * 1024 * 1024 + 1,
        )


def test_upload_validation_rejects_empty() -> None:
    with pytest.raises(ValidationFailedError):
        DocumentService._validate_upload(
            kind=DocumentKind.RESUME,
            filename="r.pdf",
            mime="application/pdf",
            size=0,
        )


def test_idempotency_key_deterministic() -> None:
    payload = {"question_id": 7, "text": "answer"}
    assert make_idempotency_key(scope="interview:1", payload=payload) == make_idempotency_key(
        scope="interview:1", payload=payload
    )
    assert make_idempotency_key(scope="interview:1", payload=payload) != make_idempotency_key(
        scope="interview:2", payload=payload
    )
    assert make_idempotency_key(scope="interview:1", payload=payload) != make_idempotency_key(
        scope="interview:1", payload={"question_id": 8, "text": "answer"}
    )
