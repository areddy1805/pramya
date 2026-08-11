"""Interview API routes (Phase 3): create, answer, hint, pause/resume/stop,
cancel, report, and SSE events."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.factory import build_inference_router
from app.core.config import get_settings
from app.core.db import get_session
from app.domain.enums import InterviewKind
from app.interview.service import InterviewService
from app.knowledge.retrieval import RetrievalService

SessionDep = Annotated[AsyncSession, Depends(get_session)]

router = APIRouter()


class InterviewSessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    role_id: int | None = None
    kind: str
    status: str
    started_at: datetime | None = None
    ended_at: datetime | None = None
    config: dict[str, object] | None = None


class InterviewCreate(BaseModel):
    user_id: int
    kind: InterviewKind = InterviewKind.GENERAL
    role_id: int | None = None
    duration_minutes: int = Field(default=30, ge=5, le=120)
    focus_competency_ids: list[int] = Field(default_factory=lambda: [])
    mode: str = "text"


class QuestionOut(BaseModel):
    id: int
    text: str
    difficulty: str
    type: str
    hint_levels: list[str] = Field(default_factory=lambda: [])
    rationale: str | None = None


class AnswerIn(BaseModel):
    question_id: int
    answer_text: str = Field(min_length=1)
    idempotency_key: str | None = None
    mode: str = "text"


class AnswerOut(BaseModel):
    id: int
    question_id: int
    text: str
    mode: str
    created_at: datetime | None = None


class HintOut(BaseModel):
    hint: str


class ReportOut(BaseModel):
    report: str


def _service(session: AsyncSession) -> InterviewService:
    settings = get_settings()
    router = build_inference_router(settings)
    retrieval = RetrievalService(session, router)
    return InterviewService(session, router, retrieval=retrieval)


@router.post("/interviews", response_model=InterviewSessionOut, status_code=201)
async def create_interview(body: InterviewCreate, session: SessionDep) -> InterviewSessionOut:
    svc = _service(session)
    row = await svc.create_session(
        user_id=body.user_id,
        kind=body.kind,
        role_id=body.role_id,
        duration_minutes=body.duration_minutes,
        focus_competency_ids=body.focus_competency_ids,
        mode=body.mode,
    )
    return InterviewSessionOut.model_validate(row)


@router.get("/interviews", response_model=list[InterviewSessionOut])
async def list_interviews(
    session: SessionDep, user_id: int = Query(...)
) -> list[InterviewSessionOut]:
    svc = _service(session)
    rows = await svc.sessions.list_for_user(user_id)
    return [InterviewSessionOut.model_validate(r) for r in rows]


@router.get("/interviews/{interview_id}", response_model=InterviewSessionOut)
async def get_interview(
    interview_id: int, session: SessionDep, user_id: int = Query(...)
) -> InterviewSessionOut:
    svc = _service(session)
    row = await svc.sessions.get_or_raise(interview_id, name="interview session")
    return InterviewSessionOut.model_validate(row)


@router.post("/interviews/{interview_id}/begin", response_model=InterviewSessionOut)
async def begin_interview(
    interview_id: int, session: SessionDep, user_id: int = Query(...)
) -> InterviewSessionOut:
    svc = _service(session)
    row = await svc.begin(interview_id, user_id)
    return InterviewSessionOut.model_validate(row)


@router.post("/interviews/{interview_id}/questions", response_model=QuestionOut, status_code=201)
async def next_question(
    interview_id: int, session: SessionDep, user_id: int = Query(...)
) -> QuestionOut:
    svc = _service(session)
    q, _turn = await svc.next_question(interview_id, user_id)
    return QuestionOut(
        id=q.id,
        text=q.text,
        difficulty=str(q.difficulty),
        type=str(q.type),
        hint_levels=q.hint_levels or [],
        rationale=q.rationale,
    )


@router.post("/interviews/{interview_id}/answers", response_model=AnswerOut)
async def submit_answer(
    interview_id: int,
    body: AnswerIn,
    session: SessionDep,
    user_id: int = Query(...),
) -> AnswerOut:
    svc = _service(session)
    answer = await svc.submit_answer(
        session_id=interview_id,
        user_id=user_id,
        question_id=body.question_id,
        answer_text=body.answer_text,
        idempotency_key=body.idempotency_key,
        mode=body.mode,
    )
    return AnswerOut(
        id=answer.id,
        question_id=answer.question_id,
        text=answer.text,
        mode=str(answer.mode),
    )


@router.post("/interviews/{interview_id}/hint", response_model=HintOut)
async def request_hint(
    interview_id: int,
    session: SessionDep,
    user_id: int = Query(...),
    question_id: int = Query(...),
) -> HintOut:
    svc = _service(session)
    hint = await svc.request_hint(interview_id, user_id, question_id)
    return HintOut(hint=hint)


@router.post("/interviews/{interview_id}/pause", response_model=InterviewSessionOut)
async def pause_interview(
    interview_id: int, session: SessionDep, user_id: int = Query(...)
) -> InterviewSessionOut:
    svc = _service(session)
    row = await svc.pause(interview_id, user_id)
    return InterviewSessionOut.model_validate(row)


@router.post("/interviews/{interview_id}/resume", response_model=InterviewSessionOut)
async def resume_interview(
    interview_id: int, session: SessionDep, user_id: int = Query(...)
) -> InterviewSessionOut:
    svc = _service(session)
    row = await svc.resume(interview_id, user_id)
    return InterviewSessionOut.model_validate(row)


@router.post("/interviews/{interview_id}/stop", response_model=InterviewSessionOut)
async def stop_interview(
    interview_id: int, session: SessionDep, user_id: int = Query(...)
) -> InterviewSessionOut:
    svc = _service(session)
    row = await svc.stop(interview_id, user_id)
    return InterviewSessionOut.model_validate(row)


@router.post("/interviews/{interview_id}/cancel", response_model=InterviewSessionOut)
async def cancel_interview(
    interview_id: int, session: SessionDep, user_id: int = Query(...)
) -> InterviewSessionOut:
    svc = _service(session)
    row = await svc.cancel(interview_id, user_id)
    return InterviewSessionOut.model_validate(row)


@router.get("/interviews/{interview_id}/report", response_model=ReportOut)
async def interview_report(
    interview_id: int, session: SessionDep, user_id: int = Query(...)
) -> ReportOut:
    svc = _service(session)
    report = await svc.generate_report(interview_id, user_id)
    return ReportOut(report=report)


@router.get("/interviews/{interview_id}/events")
async def interview_events(
    interview_id: int, session: SessionDep, user_id: int = Query(...)
) -> StreamingResponse:
    svc = _service(session)
    stream = svc.stream_events(interview_id, user_id)
    return StreamingResponse(stream, media_type="text/event-stream")
