"""Prompt tree resolution (plan §10, §23).

Prompts live in the repo-root ``prompts/`` tree. Services resolve them via
this module so resolution is CWD-independent (backend runs from
``backend/``; tests run from repo root). Every prompt is a versioned text
file; ``evaluation_version.prompt_hash`` records which prompt was used.
"""

from __future__ import annotations

from pathlib import Path

# backend/app/services -> backend/app -> backend -> repo root
_REPO_ROOT = Path(__file__).resolve().parents[3]


def prompt_path(relative: str) -> Path:
    """Resolve ``relative`` (e.g. 'candidate_analysis/resume_extraction.txt')."""
    candidates = [
        _REPO_ROOT / "prompts" / relative,
        Path("prompts") / relative,
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def load_prompt(relative: str, *, fallback: str) -> str:
    path = prompt_path(relative)
    if path.exists():
        return path.read_text()
    return fallback
