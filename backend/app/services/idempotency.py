"""Idempotency service — answer submission / write dedupe (task 1.6)."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.errors import DuplicateSubmissionError
from app.models.idempotency import IdempotencyRecord
from app.repositories.misc import IdempotencyRepository


def make_idempotency_key(*, scope: str, payload: dict[str, Any]) -> str:
    """Deterministic key from scope + canonical payload JSON."""
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(f"{scope}:{canonical}".encode()).hexdigest()


class IdempotencyService:
    """Records processed keys; duplicate (scope, key) raises 409."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.records = IdempotencyRepository(session)

    async def check_and_record(
        self, *, scope: str, key: str, payload: dict[str, Any] | None = None
    ) -> IdempotencyRecord:
        existing = await self.records.get_by_scope_key(scope, key)
        if existing is not None:
            raise DuplicateSubmissionError(
                f"request with idempotency key {key} already processed in scope {scope}",
                details={"scope": scope, "key": key},
            )
        record = IdempotencyRecord(scope=scope, key=key, payload=payload)
        await self.records.add(record)
        return record

    async def is_duplicate(self, *, scope: str, key: str) -> bool:
        return await self.records.get_by_scope_key(scope, key) is not None
