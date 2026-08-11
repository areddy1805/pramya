"""Knowledge layer: document parsing (Phase 2.1).

Phase 2.2 adds LlamaIndex ingestion, chunking, embedding, and retrieval —
not yet. Application code depends on ``parse_document_with_timeout`` and
``ParsedDocument``; parsers are deterministic and untrusted-input-safe.
"""

from app.knowledge.parsing import (
    MAX_DOCX_UNCOMPRESSED_BYTES,
    MIME_DOCX,
    MIME_MARKDOWN,
    MIME_PDF,
    MIME_PLAIN,
    ParsedDocument,
    parse_document,
    parse_document_with_timeout,
)

__all__ = [
    "MAX_DOCX_UNCOMPRESSED_BYTES",
    "MIME_DOCX",
    "MIME_MARKDOWN",
    "MIME_PDF",
    "MIME_PLAIN",
    "ParsedDocument",
    "parse_document",
    "parse_document_with_timeout",
]
