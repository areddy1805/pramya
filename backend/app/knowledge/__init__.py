"""Knowledge layer: parsing (2.1) + chunking/embedding/ingestion (2.2).

Application code depends on these deterministic components and the
InferenceRouter for embeddings — never direct provider calls.
"""

from app.knowledge.chunking import Chunk, chunk_text
from app.knowledge.ingestion import (
    DEFAULT_CHUNK_OVERLAP,
    DEFAULT_CHUNK_SIZE,
    DEFAULT_EMBED_BATCH_SIZE,
    IngestionService,
)
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
from app.knowledge.retrieval import (
    RRF_K,
    RetrievalResult,
    RetrievalService,
    RetrievedChunk,
)

__all__ = [
    "Chunk",
    "DEFAULT_CHUNK_OVERLAP",
    "DEFAULT_CHUNK_SIZE",
    "DEFAULT_EMBED_BATCH_SIZE",
    "IngestionService",
    "MAX_DOCX_UNCOMPRESSED_BYTES",
    "MIME_DOCX",
    "MIME_MARKDOWN",
    "MIME_PDF",
    "MIME_PLAIN",
    "ParsedDocument",
    "RRF_K",
    "RetrievalResult",
    "RetrievalService",
    "RetrievedChunk",
    "chunk_text",
    "parse_document",
    "parse_document_with_timeout",
]
