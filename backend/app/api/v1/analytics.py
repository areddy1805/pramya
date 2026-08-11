"""Readiness / preparation / progress API routes (Phase 5)."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.services.analytics import PreparationService, ProgressService, ReadinessService

SessionDep = Annotated[AsyncSession, Depends(get_session)]

router = APIRouter()


class CompetencyReadinessOut(BaseModel):
    name: str
    score: float
    confidence: float
    evidence_coverage: float
    demonstrated_level: int
    importance: str


class ReadinessOut(BaseModel):
    overall: float
    confidence: float
    evidence_coverage: float
    per_competency: list[CompetencyReadinessOut]
    critical_gaps: list[dict[str, object]]
    created_at: datetime | None = None


class PreparationItemOut(BaseModel):
    id: int
    competency_id: int | None = None
    priority: int
    estimated_minutes: int | None = None
    reason: str | None = None
    assessment_type: str | None = None
    expected_improvement: float | None = None
    status: str


class ProgressPointOut(BaseModel):
    evaluation_id: int
    session_id: int
    competency_id: int | None = None
    competency_name: str
    overall: float
    created_at: datetime


class CompetencySeriesOut(BaseModel):
    competency_id: int | None = None
    name: str
    latest: float | None = None
    trend: float | None = None
    points: list[ProgressPointOut]


class ProgressOut(BaseModel):
    total_evaluations: int
    sessions: int
    average_overall: float
    series: list[CompetencySeriesOut]


@router.post("/readiness", response_model=ReadinessOut)
async def compute_readiness(
    session: SessionDep,
    user_id: int = Query(...),
    role_id: int | None = Query(default=None),
) -> ReadinessOut:
    svc = ReadinessService(session)
    result, snapshot = await svc.compute_and_save(user_id, role_id)
    return ReadinessOut(
        overall=result.overall,
        confidence=result.confidence,
        evidence_coverage=result.evidence_coverage,
        per_competency=[
            CompetencyReadinessOut(
                name=c.name,
                score=c.score,
                confidence=c.confidence,
                evidence_coverage=c.evidence_coverage,
                demonstrated_level=c.demonstrated_level,
                importance=c.importance,
            )
            for c in result.per_competency
        ],
        critical_gaps=result.critical_gaps,
        created_at=snapshot.created_at,
    )


@router.get("/readiness/latest", response_model=ReadinessOut)
async def latest_readiness(
    session: SessionDep,
    user_id: int = Query(...),
) -> ReadinessOut:
    svc = ReadinessService(session)
    snapshot = await svc.latest(user_id)
    if snapshot is None:
        return ReadinessOut(
            overall=0.0,
            confidence=0.0,
            evidence_coverage=0.0,
            per_competency=[],
            critical_gaps=[],
        )
    return ReadinessOut(
        overall=snapshot.overall,
        confidence=snapshot.confidence,
        evidence_coverage=snapshot.evidence_coverage,
        per_competency=[
            CompetencyReadinessOut(
                name=name,
                score=float(entry["score"]),
                confidence=float(entry["confidence"]),
                evidence_coverage=float(entry["evidence_coverage"]),
                demonstrated_level=int(entry["demonstrated_level"]),
                importance=str(entry["importance"]),
            )
            for name, entry in snapshot.per_competency.items()
        ],
        critical_gaps=snapshot.critical_gaps or [],
        created_at=snapshot.created_at,
    )


@router.post("/preparation/regenerate", response_model=list[PreparationItemOut])
async def regenerate_preparation(
    session: SessionDep,
    user_id: int = Query(...),
) -> list[PreparationItemOut]:
    svc = PreparationService(session)
    rows = await svc.regenerate(user_id)
    return [
        PreparationItemOut(
            id=row.id,
            competency_id=row.competency_id,
            priority=row.priority,
            estimated_minutes=row.estimated_minutes,
            reason=row.reason,
            assessment_type=row.assessment_type,
            expected_improvement=row.expected_improvement,
            status=str(row.status),
        )
        for row in rows
    ]


@router.get("/preparation", response_model=list[PreparationItemOut])
async def list_preparation(
    session: SessionDep,
    user_id: int = Query(...),
) -> list[PreparationItemOut]:
    svc = PreparationService(session)
    rows = await svc.items.list_open_for_user(user_id)
    return [
        PreparationItemOut(
            id=row.id,
            competency_id=row.competency_id,
            priority=row.priority,
            estimated_minutes=row.estimated_minutes,
            reason=row.reason,
            assessment_type=row.assessment_type,
            expected_improvement=row.expected_improvement,
            status=str(row.status),
        )
        for row in rows
    ]


@router.get("/progress", response_model=ProgressOut)
async def progress_summary(
    session: SessionDep,
    user_id: int = Query(...),
) -> ProgressOut:
    svc = ProgressService(session)
    summary = await svc.summary(user_id)
    return ProgressOut(
        total_evaluations=summary.total_evaluations,
        sessions=summary.sessions,
        average_overall=summary.average_overall,
        series=[
            CompetencySeriesOut(
                competency_id=s.competency_id,
                name=s.name,
                latest=s.latest,
                trend=s.trend,
                points=[
                    ProgressPointOut(
                        evaluation_id=p.evaluation_id,
                        session_id=p.session_id,
                        competency_id=p.competency_id,
                        competency_name=p.competency_name,
                        overall=p.overall,
                        created_at=p.created_at,
                    )
                    for p in s.points
                ],
            )
            for s in summary.series
        ],
    )
