"""Evidence ledger repository."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select

from app.domain.enums import EvidenceStatus
from app.models.evidence import Evidence
from app.repositories.base import BaseRepository


class EvidenceRepository(BaseRepository[Evidence]):
    model = Evidence

    async def list_for_user(
        self,
        user_id: int,
        *,
        competency_id: int | None = None,
        status: EvidenceStatus | None = None,
        profile_id: int | None = None,
        limit: int = 200,
        offset: int = 0,
    ) -> Sequence[Evidence]:
        stmt = select(Evidence).where(Evidence.user_id == user_id)
        if profile_id is not None:
            stmt = stmt.where(Evidence.profile_id == profile_id)
        if competency_id is not None:
            stmt = stmt.where(Evidence.competency_id == competency_id)
        if status is not None:
            stmt = stmt.where(Evidence.status == status)
        return (
            await self.session.scalars(stmt.order_by(Evidence.id).limit(limit).offset(offset))
        ).all()
