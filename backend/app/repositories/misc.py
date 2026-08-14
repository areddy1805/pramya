"""Preparation / practice / story / readiness / debrief / idempotency repos."""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select, update

from app.domain.enums import PracticeItemStatus
from app.models.debrief import EvaluationVersion, InterviewDebrief
from app.models.idempotency import IdempotencyRecord
from app.models.preparation import PracticeSession, PreparationItem
from app.models.readiness import ReadinessSnapshot
from app.models.role import CandidateCompetency, Competency, Role
from app.models.story import Story
from app.repositories.base import BaseRepository


class RoleRepository(BaseRepository[Role]):
    model = Role

    async def add_all_competencies(self, competencies: Sequence[Competency]) -> None:
        self.session.add_all(competencies)
        await self.session.flush()

    async def list_for_user(self, user_id: int) -> Sequence[Role]:
        stmt = select(Role).where(Role.user_id == user_id).order_by(Role.id)
        return (await self.session.scalars(stmt)).all()

    async def list_for_profile(self, profile_id: int) -> Sequence[Role]:
        stmt = select(Role).where(Role.profile_id == profile_id).order_by(Role.id)
        return (await self.session.scalars(stmt)).all()

    async def list_competencies(self, role_id: int) -> Sequence[Competency]:
        stmt = (
            select(Competency)
            .where(Competency.role_id == role_id)
            .order_by(Competency.importance_rank)
        )
        return (await self.session.scalars(stmt)).all()


class CandidateCompetencyRepository(BaseRepository[CandidateCompetency]):
    model = CandidateCompetency

    async def list_for_profile(self, candidate_profile_id: int) -> Sequence[CandidateCompetency]:
        stmt = (
            select(CandidateCompetency)
            .where(CandidateCompetency.candidate_profile_id == candidate_profile_id)
            .order_by(CandidateCompetency.id)
        )
        return (await self.session.scalars(stmt)).all()


class PreparationItemRepository(BaseRepository[PreparationItem]):
    model = PreparationItem

    async def reopen_open(self, user_id: int, *, profile_id: int | None = None) -> None:
        """Reopen dismissed items (or mark stale done items open) for a
        fresh regeneration pass — keeps the queue accurate per snapshot."""
        stmt = (
            update(PreparationItem)
            .where(
                PreparationItem.user_id == user_id,
                PreparationItem.status == PracticeItemStatus.DISMISSED,
            )
            .values(status=PracticeItemStatus.OPEN)
        )
        if profile_id is not None:
            stmt = stmt.where(PreparationItem.profile_id == profile_id)
        await self.session.execute(stmt)

    async def list_open_for_user(
        self, user_id: int, *, profile_id: int | None = None, limit: int = 50
    ) -> Sequence[PreparationItem]:
        stmt = (
            select(PreparationItem)
            .where(
                PreparationItem.user_id == user_id,
                PreparationItem.status == PracticeItemStatus.OPEN,
            )
            .order_by(PreparationItem.priority.desc(), PreparationItem.id)
            .limit(limit)
        )
        if profile_id is not None:
            stmt = stmt.where(PreparationItem.profile_id == profile_id)
        return (await self.session.scalars(stmt)).all()


class PracticeSessionRepository(BaseRepository[PracticeSession]):
    model = PracticeSession


class StoryRepository(BaseRepository[Story]):
    model = Story

    async def list_for_user(self, user_id: int, *, limit: int = 100) -> Sequence[Story]:
        stmt = select(Story).where(Story.user_id == user_id).order_by(Story.id).limit(limit)
        return (await self.session.scalars(stmt)).all()


class ReadinessSnapshotRepository(BaseRepository[ReadinessSnapshot]):
    model = ReadinessSnapshot

    async def latest_for_user(
        self, user_id: int, *, profile_id: int | None = None
    ) -> ReadinessSnapshot | None:
        stmt = (
            select(ReadinessSnapshot)
            .where(ReadinessSnapshot.user_id == user_id)
            .order_by(ReadinessSnapshot.id.desc())
            .limit(1)
        )
        if profile_id is not None:
            stmt = stmt.where(ReadinessSnapshot.profile_id == profile_id)
        return (await self.session.scalars(stmt)).first()


class InterviewDebriefRepository(BaseRepository[InterviewDebrief]):
    model = InterviewDebrief

    async def list_for_user(self, user_id: int, *, limit: int = 100) -> Sequence[InterviewDebrief]:
        stmt = (
            select(InterviewDebrief)
            .where(InterviewDebrief.user_id == user_id)
            .order_by(InterviewDebrief.id.desc())
            .limit(limit)
        )
        return (await self.session.scalars(stmt)).all()


class EvaluationVersionRepository(BaseRepository[EvaluationVersion]):
    model = EvaluationVersion

    async def get_by_name(self, name: str) -> EvaluationVersion | None:
        stmt = select(EvaluationVersion).where(EvaluationVersion.name == name)
        return (await self.session.scalars(stmt)).first()


class IdempotencyRepository(BaseRepository[IdempotencyRecord]):
    model = IdempotencyRecord

    async def get_by_scope_key(self, scope: str, key: str) -> IdempotencyRecord | None:
        stmt = select(IdempotencyRecord).where(
            IdempotencyRecord.scope == scope, IdempotencyRecord.key == key
        )
        return (await self.session.scalars(stmt)).first()
