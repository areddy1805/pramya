"""Evaluation version registry (Phase 5.5): prompt hashing + versioning.

Every persisted evaluation references an evaluator version; the version
records the prompt hash + model policy so results are reproducible. This
module owns hashing + registry access; the interview service persists
evaluations with the current version id.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.debrief import EvaluationVersion
from app.repositories.misc import EvaluationVersionRepository

VERSION_NAME = "pramya-eval"


def prompt_hash(*contents: str | Path) -> str:
    """Deterministic SHA-256 over prompt file contents (or inline text)."""
    hasher = hashlib.sha256()
    for item in contents:
        text = item.read_text() if isinstance(item, Path) else item
        hasher.update(text.encode("utf-8"))
    return hasher.hexdigest()


class EvaluationVersionService:
    """Get-or-create the current evaluation version record."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = EvaluationVersionRepository(session)

    async def current(self, *, prompt_paths: list[Path] | None = None) -> EvaluationVersion:
        contents: list[str | Path] = list(prompt_paths) if prompt_paths else []
        digest = prompt_hash(*contents) if contents else prompt_hash("pramya-eval-1.0")
        existing = await self.repo.get_by_name(VERSION_NAME)
        if existing is not None:
            return existing
        record = EvaluationVersion(
            name=VERSION_NAME,
            version="1.0",
            prompt_hash=digest,
            model_policy={"default": "pramya-4b", "escalation": "deepseek-v4-flash"},
        )
        await self.repo.add(record)
        await self.session.commit()
        return record
