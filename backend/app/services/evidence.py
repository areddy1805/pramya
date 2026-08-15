"""Evidence service: read + user corrections (status transitions)."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import EvidenceSourceKind, EvidenceStatus
from app.domain.errors import NotFoundError, ValidationFailedError
from app.models.evidence import Evidence
from app.repositories.evidence import EvidenceRepository
from app.repositories.user import CandidateProfileRepository

# User corrections may move evidence between these statuses; the system may
# additionally use claimed→observed/demonstrated transitions with provenance.
_ALLOWED_CORRECTION_STATUSES = {
    EvidenceStatus.CLAIMED,
    EvidenceStatus.OBSERVED,
    EvidenceStatus.DEMONSTRATED,
    EvidenceStatus.INFERRED,
    EvidenceStatus.UNKNOWN,
}


class EvidenceService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.evidence = EvidenceRepository(session)
        self.profiles = CandidateProfileRepository(session)

    async def _require_profile(self, user_id: int, profile_id: int) -> None:
        profile = await self.profiles.get_for_user(user_id, profile_id)
        if profile is None:
            raise NotFoundError("candidate profile not found")

    async def list_evidence(
        self,
        user_id: int,
        *,
        competency_id: int | None = None,
        status: EvidenceStatus | None = None,
        profile_id: int | None = None,
        limit: int = 200,
        offset: int = 0,
    ) -> Sequence[Evidence]:
        return await self.evidence.list_for_user(
            user_id,
            competency_id=competency_id,
            status=status,
            profile_id=profile_id,
            limit=limit,
            offset=offset,
        )

    async def create_evidence(
        self,
        *,
        user_id: int,
        claim: str,
        source_kind: EvidenceSourceKind,
        source_ref: str | None = None,
        status: EvidenceStatus = EvidenceStatus.CLAIMED,
        competency_id: int | None = None,
        strength: float | None = None,
        notes: str | None = None,
        profile_id: int | None = None,
    ) -> Evidence:
        if profile_id is not None:
            await self._require_profile(user_id, profile_id)
        if not claim.strip():
            raise ValidationFailedError("claim must not be empty")
        if strength is not None and not (0 <= strength <= 1):
            raise ValidationFailedError("strength must be in [0,1]")
        item = Evidence(
            user_id=user_id,
            profile_id=profile_id,
            source_kind=source_kind,
            source_ref=source_ref,
            claim=claim,
            status=status,
            competency_id=competency_id,
            strength=strength,
            notes=notes,
        )
        await self.evidence.add(item)
        return item

    async def get_evidence(
        self, user_id: int, evidence_id: int, *, profile_id: int | None = None
    ) -> Evidence:
        item = await self.evidence.get_or_raise(evidence_id, name="evidence")
        if item.user_id != user_id:
            raise NotFoundError("evidence not found")
        if profile_id is not None and item.profile_id != profile_id:
            raise NotFoundError("evidence not found")
        return item

    async def patch(
        self,
        user_id: int,
        evidence_id: int,
        *,
        status: EvidenceStatus | None = None,
        strength: float | None = None,
        notes: str | None = None,
        profile_id: int | None = None,
    ) -> Evidence:
        item = await self.get_evidence(user_id, evidence_id, profile_id=profile_id)
        if status is not None:
            if status not in _ALLOWED_CORRECTION_STATUSES:
                raise ValidationFailedError(f"invalid evidence status: {status}")
            item.status = status
        if strength is not None:
            if not (0 <= strength <= 1):
                raise ValidationFailedError("strength must be in [0,1]")
            item.strength = strength
        if notes is not None:
            item.notes = notes
        await self.evidence.flush()
        return item
