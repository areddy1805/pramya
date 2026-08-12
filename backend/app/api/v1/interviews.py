"""Interview API routes (Phase 3): create, answer, hint, pause/resume/stop,
cancel, report, and SSE events."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.factory import build_inference_router
from app.core.config import get_settings
from app.core.db import get_session
from app.domain.enums import InterviewKind, InterviewTurnKind
from app.interview.service import InterviewService
from app.knowledge.retrieval import RetrievalService
from app.repositories.interview import AudioSegmentRepository, TranscriptSegmentRepository
from app.services.communication import SegmentInput, analyze_communication

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


class AudioSegmentOut(BaseModel):
    """Stored voice recording for one turn (Phase H replay)."""

    id: int
    turn_id: int | None = None
    kind: str
    duration_ms: int | None = None
    storage_key: str | None = None
    retention_until: datetime | None = None
    download_url: str | None = None


class AudioSegmentsOut(BaseModel):
    interview_id: int
    segments: list[AudioSegmentOut]


class CommunicationOut(BaseModel):
    """Deterministic communication characteristics (measured only, never
    fabricated: metrics without persisted data are reported as None)."""

    answers_count: int = 0
    total_speaking_seconds: float | None = None
    avg_response_latency_ms: float | None = None
    avg_words_per_answer: float | None = None
    longest_answer_words: int = 0
    avg_sentences_per_answer: float | None = None
    filler_count: int = 0
    fillers_per_1000_words: float = 0.0
    interruption_count: int = 0
    pauses_count: int = 0
    total_pause_seconds: float = 0.0
    notes: list[str] = Field(default_factory=lambda: [])


def _service(session: AsyncSession) -> InterviewService:
    settings = get_settings()
    router = build_inference_router(settings)
    retrieval = RetrievalService(session, router)
    # Phase D: LlamaIndex retriever is the primary RAG path (fallback:
    # deterministic hybrid RetrievalService above).
    from app.knowledge.rag.service import LlamaIndexRetriever

    rag = LlamaIndexRetriever(session, router)
    return InterviewService(session, router, retrieval=retrieval, rag=rag)


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


# -- Phase H: voice replay + communication analysis -------------------------


async def _require_owned_session(
    session: AsyncSession, interview_id: int, user_id: int
) -> None:
    svc = _service(session)
    row = await svc.sessions.get_or_raise(interview_id, name="interview session")
    if row.user_id != user_id:
        raise HTTPException(status_code=404, detail="interview session not found")


@router.get("/interviews/{interview_id}/voice/audio", response_model=AudioSegmentsOut)
async def list_voice_audio(
    interview_id: int, session: SessionDep, user_id: int = Query(...)
) -> AudioSegmentsOut:
    """List stored candidate audio segments for a voice interview."""
    await _require_owned_session(session, interview_id, user_id)
    rows = await AudioSegmentRepository(session).list_for_session(interview_id)
    segments = [
        AudioSegmentOut(
            id=r.id,
            turn_id=r.turn_id,
            kind=str(r.kind),
            duration_ms=r.duration_ms,
            storage_key=r.storage_key,
            retention_until=r.retention_until,
            download_url=(
                f"/api/v1/interviews/{interview_id}/voice/audio/{r.id}" if r.storage_key else None
            ),
        )
        for r in rows
    ]
    return AudioSegmentsOut(interview_id=interview_id, segments=segments)


@router.get("/interviews/{interview_id}/voice/audio/{segment_id}")
async def download_voice_audio(
    interview_id: int, segment_id: int, session: SessionDep, user_id: int = Query(...)
) -> FileResponse:
    """Stream a stored WAV recording (replay)."""
    await _require_owned_session(session, interview_id, user_id)
    row = await AudioSegmentRepository(session).get_or_raise(segment_id, name="audio segment")
    if row.interview_session_id != interview_id or not row.storage_key:
        raise HTTPException(status_code=404, detail="audio segment not found")
    settings = get_settings()
    path = settings.audio_storage_path / row.storage_key
    if not path.is_file():
        raise HTTPException(status_code=404, detail="audio file missing on disk")
    return FileResponse(
        path,
        media_type="audio/wav",
        filename=f"pramya-interview-{interview_id}-turn-{row.turn_id or '?'}.wav",
    )


@router.get("/interviews/{interview_id}/communication", response_model=CommunicationOut)
async def interview_communication(
    interview_id: int, session: SessionDep, user_id: int = Query(...)
) -> CommunicationOut:
    """Deterministic communication analysis from persisted transcript data.

    Only measured values are reported (see analyzer notes); nothing is
    fabricated when timestamps are absent.
    """
    await _require_owned_session(session, interview_id, user_id)
    segments = await TranscriptSegmentRepository(session).list_for_session(interview_id)
    turns = await _service(session).turns.list_for_session(interview_id)
    turn_kinds = {t.id: str(t.kind) for t in turns}
    inputs: list[SegmentInput] = []
    interruptions = 0
    for seg in segments:
        ts = seg.timestamps or {}
        role = ts.get("role")
        if not isinstance(role, str):
            kind = turn_kinds.get(seg.turn_id or -1)
            role = "candidate" if kind == str(InterviewTurnKind.ANSWER) else "interviewer"
        raw_int = ts.get("interruptions")
        if isinstance(raw_int, int):
            interruptions = max(interruptions, raw_int)
        inputs.append(SegmentInput(text=seg.text, role=role, timestamps=seg.timestamps))
    analysis = analyze_communication(inputs, interruption_count=interruptions)
    return CommunicationOut(
        answers_count=analysis.answers_count,
        total_speaking_seconds=analysis.total_speaking_seconds,
        avg_response_latency_ms=analysis.avg_response_latency_ms,
        avg_words_per_answer=analysis.avg_words_per_answer,
        longest_answer_words=analysis.longest_answer_words,
        avg_sentences_per_answer=analysis.avg_sentences_per_answer,
        filler_count=analysis.filler_count,
        fillers_per_1000_words=analysis.fillers_per_1000_words,
        interruption_count=analysis.interruption_count,
        pauses_count=analysis.pauses_count,
        total_pause_seconds=analysis.total_pause_seconds,
        notes=analysis.notes,
    )
