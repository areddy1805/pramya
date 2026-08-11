"""Deterministic document chunking (Phase 2.2).

Plan §12 names LlamaIndex for ingestion, but the project's own principles
(boundary rules ADR-004/011, deterministic-first, no unnecessary deps) and
the verified LlamaIndex dedup gotcha (PROJECT_MEMORY: IngestionPipeline does
NOT dedupe against the vector store) point to a small deterministic chunker
owned by the knowledge layer. Chunking is pure text manipulation — no LLM,
no framework dependency. See DECISIONS.md for the deviation note.

Algorithm: greedy paragraph packing up to ``chunk_size`` chars with a
``chunk_overlap``-char carry-over window so retrieval has context on both
sides of a split. Deterministic for identical input.
"""

from __future__ import annotations

from dataclasses import dataclass, field

DEFAULT_CHUNK_SIZE = 1200
DEFAULT_CHUNK_OVERLAP = 200


@dataclass(frozen=True)
class Chunk:
    """One chunk of a document."""

    index: int
    content: str
    char_start: int
    char_end: int
    metadata: dict[str, object] = field(default_factory=lambda: {})


def _paragraphs(content: str) -> list[tuple[str, int]]:
    """Split content into (paragraph, char_offset) pairs on blank lines."""
    out: list[tuple[str, int]] = []
    offset = 0
    for para in content.split("\n\n"):
        text = para.strip()
        if text:
            out.append((text, offset + content[offset:].find(text)))
        offset += len(para) + 2
    return out


def chunk_text(
    content: str,
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[Chunk]:
    """Greedy paragraph-packing chunker.

    Each chunk is at most ``chunk_size`` characters; a paragraph longer than
    ``chunk_size`` is hard-split on word boundaries. The trailing
    ``chunk_overlap`` characters of a chunk are carried into the next one to
    preserve context across splits. Deterministic.
    """
    if not content.strip():
        return []
    if chunk_size <= 0 or chunk_overlap < 0:
        raise ValueError("chunk_size must be > 0 and chunk_overlap >= 0")

    paragraphs = _paragraphs(content)
    chunks: list[Chunk] = []
    buffer: list[str] = []
    buffer_len = 0
    start_offset = 0

    def flush() -> None:
        nonlocal buffer, buffer_len, start_offset
        if not buffer:
            return
        text = "\n\n".join(buffer)
        chunks.append(
            Chunk(
                index=len(chunks),
                content=text,
                char_start=start_offset,
                char_end=start_offset + len(text),
            )
        )
        # Carry overlap: trailing paragraphs up to chunk_overlap chars.
        carried: list[str] = []
        carried_len = 0
        for para in reversed(buffer):
            if carried_len + len(para) + 2 > chunk_overlap:
                break
            carried.insert(0, para)
            carried_len += len(para) + 2
        if carried and carried != buffer:
            overlap_len = sum(len(p) for p in carried) + 2 * (len(carried) - 1)
            buffer = carried
            buffer_len = overlap_len
            start_offset = max(0, start_offset + len(text) - overlap_len)
        else:
            buffer = []
            buffer_len = 0
            start_offset = 0

    for para, offset in paragraphs:
        if len(para) > chunk_size:
            flush()
            for piece in _hard_split(para, chunk_size):
                chunks.append(
                    Chunk(
                        index=len(chunks),
                        content=piece,
                        char_start=offset,
                        char_end=offset + len(piece),
                    )
                )
            start_offset = 0
            continue
        if buffer_len + len(para) + 2 > chunk_size and buffer:
            flush()
        if not buffer:
            start_offset = offset
        buffer.append(para)
        buffer_len += len(para) + 2
    flush()
    return chunks


def _hard_split(text: str, chunk_size: int) -> list[str]:
    """Split an oversized paragraph on word boundaries."""
    words = text.split(" ")
    pieces: list[str] = []
    current: list[str] = []
    current_len = 0
    for word in words:
        if current_len + len(word) + 1 > chunk_size and current:
            pieces.append(" ".join(current))
            current = [word]
            current_len = len(word)
        else:
            current.append(word)
            current_len += len(word) + 1
    if current:
        pieces.append(" ".join(current))
    return pieces
