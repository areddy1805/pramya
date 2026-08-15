"""Readiness/preparation/progress service adapters (Phase 5).

Thin DB adapters over the deterministic engines (readiness.py,
preparation.py, progress.py). Compute + persist readiness snapshots,
materialize the preparation queue, and aggregate progress.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import PracticeItemStatus
from app.domain.errors import ValidationFailedError
from app.models.evidence import Evidence
from app.models.interview import Evaluation, Question
from app.models.preparation import PreparationItem
from app.models.readiness import ReadinessSnapshot
from app.repositories.evidence import EvidenceRepository
from app.repositories.interview import InterviewSessionRepository
from app.repositories.misc import (
    PreparationItemRepository,
    ReadinessSnapshotRepository,
    RoleRepository,
)
from app.services.preparation import GapInput, plan_preparation
from app.services.progress import ProgressPoint, ProgressSummary, aggregate_progress
from app.services.readiness import (
    CompetencyInput,
    EvaluationInput,
    EvidenceInput,
    ReadinessResult,
    compute_readiness,
)


class ReadinessService:
    """Compute + persist an immutable readiness snapshot."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.roles = RoleRepository(session)
        self.evidence = EvidenceRepository(session)
        self.snapshots = ReadinessSnapshotRepository(session)

    async def compute_and_save(
        self,
        user_id: int,
        role_id: int | None,
        *,
        candidate_profile_id: int | None = None,
        profile_id: int | None = None,
    ) -> tuple[ReadinessResult, ReadinessSnapshot]:
        # Back-compat: legacy callers pass candidate_profile_id; profile_id
        # is the canonical career-profile id.
        effective_profile = profile_id if profile_id is not None else candidate_profile_id
        competencies, evidence, evaluations = await self._load(user_id, role_id, effective_profile)
        result = compute_readiness(competencies, evidence, evaluations)
        snapshot = ReadinessSnapshot(
            user_id=user_id,
            profile_id=effective_profile,
            role_id=role_id,
            overall=result.overall,
            per_competency={
                c.name: {
                    "score": c.score,
                    "confidence": c.confidence,
                    "evidence_coverage": c.evidence_coverage,
                    "demonstrated_level": c.demonstrated_level,
                    "importance": c.importance,
                }
                for c in result.per_competency
            },
            confidence=result.confidence,
            evidence_coverage=result.evidence_coverage,
            critical_gaps=result.critical_gaps,
        )
        await self.snapshots.add(snapshot)
        await self.session.commit()
        return result, snapshot

    async def latest(
        self, user_id: int, *, profile_id: int | None = None
    ) -> ReadinessSnapshot | None:
        return await self.snapshots.latest_for_user(user_id, profile_id=profile_id)

    async def _load(
        self, user_id: int, role_id: int | None, profile_id: int | None = None
    ) -> tuple[list[CompetencyInput], list[EvidenceInput], list[EvaluationInput]]:
        competencies: list[CompetencyInput] = []
        if role_id is not None:
            role = await self.roles.get(role_id)
            # Ownership invariant: readiness may only score a role the
            # caller's profile owns (legacy profile_id IS NULL roles stay
            # valid). A foreign role would leak another profile's target
            # role + competencies into this profile's readiness report.
            if role is None or role.user_id != user_id or (
                role.profile_id is not None and role.profile_id != profile_id
            ):
                raise ValidationFailedError(
                    "role does not belong to this profile",
                    details={"role_id": role_id, "profile_id": profile_id},
                )
            rows = await self.roles.list_competencies(role_id)
            competencies = [
                CompetencyInput(
                    id=c.id,
                    name=c.name,
                    importance=str(c.importance),
                    weight=c.weight,
                    level=c.level,
                )
                for c in rows
            ]
        evidence_rows: Sequence[Evidence] = await self.evidence.list_for_user(
            user_id, profile_id=profile_id, limit=500
        )
        evidence = [
            EvidenceInput(
                competency_id=e.competency_id,
                status=str(e.status),
                strength=e.strength or 0.0,
                created_at=e.created_at,
            )
            for e in evidence_rows
        ]
        evaluations = [
            EvaluationInput(
                competency_id=None,
                overall=ev.overall,
                confidence=ev.confidence,
                created_at=ev.created_at,
            )
            for ev in await self._load_evaluations(user_id, profile_id)
        ]
        return competencies, evidence, evaluations

    async def _load_evaluations(
        self, user_id: int, profile_id: int | None = None
    ) -> Sequence[Evaluation]:
        sessions = await InterviewSessionRepository(self.session).list_for_user(
            user_id, limit=200, profile_id=profile_id
        )
        session_ids = [s.id for s in sessions]
        if not session_ids:
            return []
        questions = (
            await self.session.scalars(
                select(Question).where(Question.interview_session_id.in_(session_ids))
            )
        ).all()
        q_ids = [q.id for q in questions]
        if not q_ids:
            return []
        return list(
            (
                await self.session.scalars(
                    select(Evaluation).where(Evaluation.answer_id.in_(q_ids))
                )
            ).all()
        )


class PreparationService:
    """Materialize the preparation queue from readiness gaps."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.items = PreparationItemRepository(session)
        self.snapshots = ReadinessSnapshotRepository(session)

    async def regenerate(
        self, user_id: int, *, profile_id: int | None = None
    ) -> list[PreparationItem]:
        snapshot = await self.snapshots.latest_for_user(user_id, profile_id=profile_id)
        if snapshot is None or not snapshot.critical_gaps:
            return []
        gaps = [
            GapInput(
                competency_id=int(g["competency_id"]),
                name=str(g["name"]),
                demonstrated_level=int(g["demonstrated_level"]),
                required_level=int(g["required_level"]),
                score=float(g["score"]),
                gap=int(g["gap"]),
            )
            for g in snapshot.critical_gaps
        ]
        plan = plan_preparation(gaps)
        await self.items.reopen_open(user_id, profile_id=profile_id)
        rows = [
            PreparationItem(
                user_id=user_id,
                profile_id=profile_id,
                competency_id=item.competency_id,
                priority=item.priority,
                estimated_minutes=item.estimated_minutes,
                reason=item.reason,
                assessment_type=item.assessment_type,
                expected_improvement=item.expected_improvement,
                status=PracticeItemStatus.OPEN,
            )
            for item in plan
        ]
        if rows:
            await self.items.add_all(rows)
            await self.session.commit()
        return rows


class ProgressService:
    """Aggregate progress from completed evaluations (never fabricated)."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.sessions = InterviewSessionRepository(session)

    async def summary(self, user_id: int, *, profile_id: int | None = None) -> ProgressSummary:
        sessions = await self.sessions.list_for_user(user_id, limit=200, profile_id=profile_id)
        if not sessions:
            return aggregate_progress([])
        session_ids = [s.id for s in sessions]
        questions = (
            await self.session.scalars(
                select(Question).where(Question.interview_session_id.in_(session_ids))
            )
        ).all()
        q_ids = [q.id for q in questions]
        if not q_ids:
            return aggregate_progress([])
        evaluations = (
            await self.session.scalars(select(Evaluation).where(Evaluation.answer_id.in_(q_ids)))
        ).all()
        points = [
            ProgressPoint(
                evaluation_id=ev.id,
                session_id=0,
                competency_id=None,
                competency_name="interview",
                overall=ev.overall,
                created_at=ev.created_at or datetime.now(UTC),
            )
            for ev in evaluations
        ]
        return aggregate_progress(points)
