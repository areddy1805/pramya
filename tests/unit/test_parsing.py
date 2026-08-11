"""Unit tests: document parsing (Phase 2.1) — pdf/docx/md/txt, guards.

No DB, no live services: parsers are pure functions over bytes.
"""

from __future__ import annotations

from io import BytesIO

import pytest
from docx import Document as DocxDocument
from pypdf import PdfWriter

from app.domain.enums import DocumentKind
from app.domain.errors import ValidationFailedError
from app.knowledge.parsing import (
    MIME_DOCX,
    MIME_MARKDOWN,
    MIME_PDF,
    MIME_PLAIN,
    parse_document,
    parse_document_with_timeout,
)

KIND = DocumentKind.RESUME
HASH = "a" * 64


def _minimal_pdf(text: str) -> bytes:
    """Build a minimal single-page PDF with one text line (valid xref)."""
    stream = b"BT /F1 24 Tf 72 720 Td (" + text.encode("latin-1") + b") Tj ET"
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>"
        ),
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    body = bytearray()
    offsets: list[int] = []
    for i, obj in enumerate(objects, start=1):
        offsets.append(len(body))
        body += f"{i} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref_offset = len(body)
    body += b"xref\n0 6\n0000000000 65535 f \n"
    for off in offsets:
        body += f"{off:010d} 00000 n \n".encode()
    body += (
        b"trailer\n<< /Size 6 /Root 1 0 R >>\n"
        + f"startxref\n{xref_offset}\n".encode()
        + b"%%EOF\n"
    )
    return bytes(body)


def _docx_bytes(text: str) -> bytes:
    doc = DocxDocument()
    doc.add_paragraph(text)
    buf = BytesIO()
    doc.save(buf)
    return buf.getvalue()


# --- text -------------------------------------------------------------------


def test_parse_text_utf8() -> None:
    parsed = parse_document(
        data=b"Senior engineer\nPython",
        kind=KIND,
        mime=MIME_PLAIN,
        filename="resume.txt",
        content_hash=HASH,
        max_pages=50,
    )
    assert parsed.format == "text"
    assert parsed.content == "Senior engineer\nPython"
    assert parsed.page_count == 1
    assert parsed.mime == MIME_PLAIN


def test_parse_text_latin1_fallback() -> None:
    parsed = parse_document(
        data="caf\xe9".encode("latin-1"),
        kind=KIND,
        mime=MIME_PLAIN,
        filename="resume.txt",
        content_hash=HASH,
        max_pages=50,
    )
    assert parsed.content == "café"


# --- markdown ---------------------------------------------------------------


def test_parse_markdown_extracts_heading_and_inline() -> None:
    parsed = parse_document(
        data=b"# Alex\n\nSenior **engineer** at [Acme](https://acme.example)",
        kind=KIND,
        mime=MIME_MARKDOWN,
        filename="resume.md",
        content_hash=HASH,
        max_pages=50,
    )
    assert parsed.format == "markdown"
    assert "Alex" in parsed.content
    assert "Senior" in parsed.content
    assert "engineer" in parsed.content  # inline emphasis text kept


def test_parse_markdown_code_block() -> None:
    parsed = parse_document(
        data=b"```python\nprint('hi')\n```",
        kind=KIND,
        mime=MIME_MARKDOWN,
        filename="note.md",
        content_hash=HASH,
        max_pages=50,
    )
    assert "print('hi')" in parsed.content


# --- docx -------------------------------------------------------------------


def test_parse_docx_extracts_paragraphs() -> None:
    parsed = parse_document(
        data=_docx_bytes("Lead engineer with 5 years of Python"),
        kind=KIND,
        mime=MIME_DOCX,
        filename="resume.docx",
        content_hash=HASH,
        max_pages=50,
    )
    assert parsed.format == "docx"
    assert "Lead engineer" in parsed.content


def test_parse_docx_bomb_guard(monkeypatch: pytest.MonkeyPatch) -> None:
    import app.knowledge.parsing as parsing

    monkeypatch.setattr(parsing, "MAX_DOCX_UNCOMPRESSED_BYTES", 10)
    with pytest.raises(ValidationFailedError) as exc:
        parse_document(
            data=_docx_bytes("tiny"),
            kind=KIND,
            mime=MIME_DOCX,
            filename="bomb.docx",
            content_hash=HASH,
            max_pages=50,
        )
    assert "uncompressed size" in str(exc.value)


def test_parse_docx_malformed() -> None:
    with pytest.raises(ValidationFailedError):
        parse_document(
            data=b"not a docx at all",
            kind=KIND,
            mime=MIME_DOCX,
            filename="broken.docx",
            content_hash=HASH,
            max_pages=50,
        )


# --- pdf --------------------------------------------------------------------


def test_parse_pdf_extracts_text() -> None:
    parsed = parse_document(
        data=_minimal_pdf("Hello Pramya"),
        kind=KIND,
        mime=MIME_PDF,
        filename="resume.pdf",
        content_hash=HASH,
        max_pages=50,
    )
    assert parsed.format == "pdf"
    assert "Hello Pramya" in parsed.content
    assert parsed.page_count == 1


def test_parse_pdf_page_limit() -> None:
    writer = PdfWriter()
    for _ in range(3):
        writer.add_blank_page(width=612, height=792)
    buf = BytesIO()
    writer.write(buf)
    with pytest.raises(ValidationFailedError) as exc:
        parse_document(
            data=buf.getvalue(),
            kind=KIND,
            mime=MIME_PDF,
            filename="long.pdf",
            content_hash=HASH,
            max_pages=2,
        )
    assert exc.value.details["pages"] == 3
    assert exc.value.details["max_pages"] == 2


def test_parse_pdf_no_extractable_text() -> None:
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    buf = BytesIO()
    writer.write(buf)
    with pytest.raises(ValidationFailedError) as exc:
        parse_document(
            data=buf.getvalue(),
            kind=KIND,
            mime=MIME_PDF,
            filename="blank.pdf",
            content_hash=HASH,
            max_pages=50,
        )
    assert "no extractable text" in str(exc.value)


def test_parse_pdf_malformed() -> None:
    with pytest.raises(ValidationFailedError):
        parse_document(
            data=b"%PDF-1.4 this is not a real pdf",
            kind=KIND,
            mime=MIME_PDF,
            filename="broken.pdf",
            content_hash=HASH,
            max_pages=50,
        )


# --- shared guards ----------------------------------------------------------


def test_parse_empty_data_rejected() -> None:
    with pytest.raises(ValidationFailedError):
        parse_document(
            data=b"",
            kind=KIND,
            mime=MIME_PLAIN,
            filename="empty.txt",
            content_hash=HASH,
            max_pages=50,
        )


def test_parse_unsupported_mime_rejected() -> None:
    with pytest.raises(ValidationFailedError):
        parse_document(
            data=b"#!/bin/sh",
            kind=KIND,
            mime="application/x-sh",
            filename="evil.sh",
            content_hash=HASH,
            max_pages=50,
        )


def test_parse_deterministic() -> None:
    data = b"# Alex\nSenior engineer"
    first = parse_document(
        data=data, kind=KIND, mime=MIME_MARKDOWN, filename="a.md", content_hash=HASH, max_pages=50
    )
    second = parse_document(
        data=data, kind=KIND, mime=MIME_MARKDOWN, filename="a.md", content_hash=HASH, max_pages=50
    )
    assert first.content == second.content


async def test_parse_timeout_bounded(monkeypatch: pytest.MonkeyPatch) -> None:
    import time

    import app.knowledge.parsing as parsing

    def slow_parse(**kwargs: object) -> object:
        time.sleep(1.0)
        return None

    monkeypatch.setattr(parsing, "parse_document", slow_parse)
    with pytest.raises(TimeoutError):
        await parse_document_with_timeout(
            data=b"x",
            kind=KIND,
            mime=MIME_PLAIN,
            filename="slow.txt",
            content_hash=HASH,
            max_pages=50,
            timeout_seconds=0.05,
        )
