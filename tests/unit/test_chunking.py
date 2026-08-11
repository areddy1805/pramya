"""Chunking unit tests (Phase 2.2): deterministic, overlap, hard-split."""

from __future__ import annotations

import pytest

from app.knowledge.chunking import chunk_text


def test_empty_and_whitespace_only() -> None:
    assert chunk_text("") == []
    assert chunk_text("   \n\n  ") == []


def test_single_paragraph_single_chunk() -> None:
    text = "Hello world."
    chunks = chunk_text(text)
    assert len(chunks) == 1
    assert chunks[0].content == "Hello world."
    assert chunks[0].index == 0
    assert chunks[0].char_start == 0
    assert chunks[0].char_end == len(text)


def test_multiple_paragraphs_kept_ordered() -> None:
    text = "\n\n".join(f"paragraph {i}" for i in range(5))
    chunks = chunk_text(text, chunk_size=10_000)
    assert len(chunks) == 1
    assert "paragraph 0" in chunks[0].content
    assert "paragraph 4" in chunks[0].content


def test_split_into_multiple_chunks_and_overlap() -> None:
    # 10 paragraphs of 200 chars each -> several chunks at chunk_size=300.
    paragraphs = ["w" * 200 for _ in range(10)]
    text = "\n\n".join(paragraphs)
    chunks = chunk_text(text, chunk_size=300, chunk_overlap=100)
    assert len(chunks) >= 2
    for chunk in chunks:
        assert len(chunk.content) <= 300
        assert chunk.content  # non-empty
    # Overlap: adjacent chunks share trailing text.
    overlap_text = chunks[0].content.split("\n\n")[-1]
    assert overlap_text in chunks[1].content


def test_deterministic_same_input_same_output() -> None:
    text = "\n\n".join(f"Section {i} " + "x" * 150 for i in range(8))
    a = chunk_text(text, chunk_size=400, chunk_overlap=100)
    b = chunk_text(text, chunk_size=400, chunk_overlap=100)
    assert [c.content for c in a] == [c.content for c in b]
    assert [c.char_start for c in a] == [c.char_start for c in b]


def test_hard_split_oversized_paragraph() -> None:
    text = " ".join(["word" for _ in range(500)])  # ~2500 chars
    chunks = chunk_text(text, chunk_size=200, chunk_overlap=0)
    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk.content) <= 200
    # All words preserved across pieces.
    joined = " ".join(c.content for c in chunks)
    assert joined.split() == text.split()


def test_char_offsets_are_non_decreasing() -> None:
    text = "\n\n".join(f"p{i} " + "y" * 100 for i in range(6))
    chunks = chunk_text(text, chunk_size=250, chunk_overlap=50)
    starts = [c.char_start for c in chunks]
    ends = [c.char_end for c in chunks]
    assert starts == sorted(starts)
    assert all(s <= e for s, e in zip(starts, ends, strict=True))


def test_invalid_params() -> None:
    with pytest.raises(ValueError):
        chunk_text("abc", chunk_size=0)
    with pytest.raises(ValueError):
        chunk_text("abc", chunk_overlap=-1)
