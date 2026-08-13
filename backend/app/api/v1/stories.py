"""Story bank + debrief + transcript analysis API routes (Phase 10).

Story CRUD (write path: user-owned content), real-interview debriefs, and
pasted-transcript analysis via structured LLM output (router-routed).
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.contracts import ChatMessage
from app.ai.factory import build_inference_router
from app.ai.langchain.structured import generate_structured
from app.ai.policy import TaskClass
from app.core.config import get_settings
from app.core.db import get_session
from app.domain.errors import NotFoundError
from app.domain.schemas import DebriefAnalysis, TranscriptAnalysis
from app.models.debrief import InterviewDebrief
from app.models.story import Story
from app.repositories.misc import InterviewDebriefRepository, StoryRepository
from app.services.prompts import load_prompt

SessionDep = Annotated[AsyncSession, Depends(get_session)]

router = APIRouter()

_TRANSCRIPT_PROMPT = "transcript_analysis/transcript_analysis.txt"
_DEBRIEF_PROMPT = "debrief_analysis/debrief_analysis.txt"


class StoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    situation: str | None = None
    task: str | None = None
    action: str | None = None
    result: str | None = None
    metrics: str | None = None
    conflict: str | None = None
    learning: str | None = None
    strength: str | None = None
    competency_ids: list[int] | None = None
    freshness: float | None = None
    usage_count: int = 0
    coverage: float | None = None
    confidence: float | None = None
    created_at: datetime


class StoryCreate(BaseModel):
    user_id: int
    situation: str | None = None
    task: str | None = None
    action: str | None = None
    result: str | None = None
    metrics: str | None = None
    conflict: str | None = None
    learning: str | None = None
    strength: str | None = None
    competency_ids: list[int] | None = None


class StoryPatch(BaseModel):
    situation: str | None = None
    task: str | None = None
    action: str | None = None
    result: str | None = None
    metrics: str | None = None
    conflict: str | None = None
    learning: str | None = None
    strength: str | None = None
    competency_ids: list[int] | None = None


@router.get("/stories", response_model=list[StoryOut])
async def list_stories(
    session: SessionDep,
    user_id: int = Query(...),
) -> list[StoryOut]:
    repo = StoryRepository(session)
    rows = await repo.list_for_user(user_id)
    return [StoryOut.model_validate(r) for r in rows]


@router.post("/stories", response_model=StoryOut, status_code=201)
async def create_story(body: StoryCreate, session: SessionDep) -> StoryOut:
    story = Story(
        user_id=body.user_id,
        situation=body.situation,
        task=body.task,
        action=body.action,
        result=body.result,
        metrics=body.metrics,
        conflict=body.conflict,
        learning=body.learning,
        strength=body.strength,
        competency_ids=body.competency_ids,
    )
    repo = StoryRepository(session)
    await repo.add(story)
    await session.commit()
    return StoryOut.model_validate(story)


@router.patch("/stories/{story_id}", response_model=StoryOut)
async def patch_story(
    story_id: int,
    body: StoryPatch,
    session: SessionDep,
    user_id: int = Query(...),
) -> StoryOut:
    repo = StoryRepository(session)
    story = await repo.get_or_raise(story_id, name="story")
    if story.user_id != user_id:
        raise NotFoundError("story not found")
    for field_name in (
        "situation",
        "task",
        "action",
        "result",
        "metrics",
        "conflict",
        "learning",
        "strength",
        "competency_ids",
    ):
        value = getattr(body, field_name)
        if value is not None:
            setattr(story, field_name, value)
    await session.commit()
    return StoryOut.model_validate(story)


@router.delete("/stories/{story_id}", status_code=204)
async def delete_story(
    story_id: int,
    session: SessionDep,
    user_id: int = Query(...),
) -> None:
    repo = StoryRepository(session)
    story = await repo.get_or_raise(story_id, name="story")
    if story.user_id != user_id:
        raise NotFoundError("story not found")
    await repo.delete(story)
    await session.commit()


class DebriefOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    company: str
    role: str | None = None
    round: str | None = None
    questions: list[dict[str, object]] | None = None
    feedback: str | None = None
    result: str | None = None
    analysis: dict[str, object] | None = None
    created_at: datetime


class DebriefCreate(BaseModel):
    user_id: int
    company: str = Field(min_length=1)
    role: str | None = None
    round: str | None = None
    questions: list[dict[str, object]] | None = None
    feedback: str | None = None
    result: str | None = None


@router.get("/debriefs", response_model=list[DebriefOut])
async def list_debriefs(
    session: SessionDep,
    user_id: int = Query(...),
) -> list[DebriefOut]:
    repo = InterviewDebriefRepository(session)
    rows = await repo.list_for_user(user_id)
    return [DebriefOut.model_validate(r) for r in rows]


@router.post("/debriefs", response_model=DebriefOut, status_code=201)
async def create_debrief(body: DebriefCreate, session: SessionDep) -> DebriefOut:
    debrief = InterviewDebrief(
        user_id=body.user_id,
        company=body.company,
        role=body.role,
        round=body.round,
        questions=body.questions,
        feedback=body.feedback,
        result=body.result,
    )
    repo = InterviewDebriefRepository(session)
    await repo.add(debrief)
    await session.commit()
    return DebriefOut.model_validate(debrief)


class TranscriptIn(BaseModel):
    user_id: int
    transcript_text: str = Field(min_length=20, max_length=200_000)


class TranscriptOut(BaseModel):
    questions: list[str] = []
    answers: list[str] = []
    follow_ups: list[str] = []
    weaknesses: list[str] = []
    strengths: list[str] = []


@router.post("/transcripts/analyze", response_model=TranscriptOut)
async def analyze_transcript(
    body: TranscriptIn,
    session: SessionDep,
) -> TranscriptOut:
    router = build_inference_router(get_settings())
    prompt = load_prompt(
        _TRANSCRIPT_PROMPT,
        fallback=(
            "Analyze the interview transcript: extract questions, answers, "
            "follow-ups, weaknesses, and strengths."
        ),
    )
    messages = [
        ChatMessage(role="system", content=prompt),
        ChatMessage(
            role="user",
            content=f"<<<TRANSCRIPT>>>\n{body.transcript_text}\n<<<END TRANSCRIPT>>>",
        ),
    ]
    analysis, _ = await generate_structured(
        router, TaskClass.ANALYSIS, messages, TranscriptAnalysis
    )
    return TranscriptOut(
        questions=analysis.questions,
        answers=analysis.answers,
        follow_ups=analysis.follow_ups,
        weaknesses=analysis.weaknesses,
        strengths=analysis.strengths,
    )


class DebriefIn(BaseModel):
    user_id: int
    company: str = Field(min_length=1)
    role: str | None = None
    round: str | None = None
    questions: list[str] = []
    feedback: str | None = None
    result: str | None = None


class DebriefAnalyzeOut(DebriefOut):
    weaknesses: list[str] = []
    strengths: list[str] = []
    recommendations: list[str] = []
    competency_hints: list[str] = []


@router.post("/debriefs/analyze", response_model=DebriefAnalyzeOut)
async def analyze_debrief(
    body: DebriefIn,
    session: SessionDep,
) -> DebriefAnalyzeOut:
    router = build_inference_router(get_settings())
    prompt = load_prompt(
        _DEBRIEF_PROMPT,
        fallback=(
            "Analyze the real-interview debrief: weaknesses, strengths, "
            "recommendations, and competency hints."
        ),
    )
    questions_text = "\n".join(f"- {q}" for q in body.questions)
    messages = [
        ChatMessage(role="system", content=prompt),
        ChatMessage(
            role="user",
            content=(
                f"COMPANY: {body.company}\nROLE: {body.role or ''}\n"
                f"ROUND: {body.round or ''}\nRESULT: {body.result or ''}\n"
                f"QUESTIONS:\n{questions_text}\n"
                f"FEEDBACK: {body.feedback or ''}"
            ),
        ),
    ]
    analysis, _ = await generate_structured(router, TaskClass.ANALYSIS, messages, DebriefAnalysis)
    debrief = InterviewDebrief(
        user_id=body.user_id,
        company=body.company,
        role=body.role,
        round=body.round,
        questions=[{"question": q} for q in body.questions],
        feedback=body.feedback,
        result=body.result,
        analysis=analysis.model_dump(),
    )
    repo = InterviewDebriefRepository(session)
    await repo.add(debrief)
    await session.commit()
    out = DebriefAnalyzeOut.model_validate(debrief)
    out.weaknesses = analysis.weaknesses
    out.strengths = analysis.strengths
    out.recommendations = analysis.recommendations
    out.competency_hints = analysis.competency_hints
    return out
