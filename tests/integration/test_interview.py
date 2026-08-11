"""Interview service integration tests (Phase 3): lifecycle on real pgvector.

LLM calls are faked via a QueueProvider router (structured JSON per call).
Covers: create -> begin -> question -> answer -> evaluation -> evidence ->
hint -> pause/resume -> stop -> report path, idempotent answers, and
state-transition enforcement.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.contracts import ChatResponse, Usage
from app.ai.policy import TaskPolicyTable
from app.ai.router import InferenceRouter
from app.domain.enums import (
    InterviewKind,
    InterviewSessionStatus,
    InterviewTurnKind,
)
from app.domain.errors import InterviewStateError
from app.interview.service import InterviewService
from app.repositories.interview import InterviewTurnRepository
from app.services.user import CandidateService

QUESTION_JSON = json.dumps(
    {
        "text": "Describe a distributed system you built and a hard tradeoff you faced.",
        "type": "project_deep_dive",
        "difficulty": "medium",
        "rationale": "Probes architecture + tradeoff awareness",
        "hint_levels": ["Think about consistency", "Consider CAP", "Sketch the design"],
        "target_competency": "System Design",
    }
)

EVAL_JSON = json.dumps(
    {
        "dimensions": {
            "correctness": 7.0,
            "technical_depth": 6.0,
            "clarity": 8.0,
            "structure": 7.0,
            "relevance": 8.0,
            "evidence": 7.0,
            "communication": 7.0,
            "tradeoff_awareness": 8.0,
            "reasoning": 7.0,
            "confidence": 6.0,
            "specificity": 7.0,
            "seniority_alignment": 6.0,
            "completeness": 7.0,
        },
        "overall": 7.2,
        "confidence": 0.85,
        "strengths": ["Clear tradeoff discussion"],
        "weaknesses": ["Missing concrete numbers"],
        "missing_evidence": ["Quantified impact"],
        "follow_ups": ["How did you measure consistency?"],
        "evidence": [
            {
                "claim": "Built a distributed event ingestion system",
                "status": "observed",
                "strength": 0.8,
                "competency_hint": "architecture",
            }
        ],
    }
)

HINT_JSON = json.dumps({"hint": "Think about how you'd measure consistency across nodes."})

REPORT_JSON = json.dumps({"report": "Strong tradeoff awareness; work on quantifying impact."})


class QueueProvider:
    name = "fake"

    def __init__(self, contents: list[str]) -> None:
        self.contents = contents
        self.calls: list[ChatRequestLike] = []

    async def generate(self, request: Any) -> ChatResponse:
        self.calls.append(request)
        content = self.contents.pop(0) if self.contents else "{}"
        return ChatResponse(content=content, model="fake", usage=Usage(total_tokens=1))


class ChatRequestLike:
    pass


@pytest.fixture
async def interview_env(db_session: AsyncSession) -> dict[str, Any]:

    user = await CandidateService(db_session).create_user(display_name="Alex")
    await db_session.commit()
    return {"db": db_session, "user_id": user.id}


async def _svc(env: dict[str, Any], contents: list[str]) -> tuple[InterviewService, QueueProvider]:
    provider = QueueProvider(contents)
    router = InferenceRouter(policy=TaskPolicyTable(), omlx=provider, deepseek=None)
    svc = InterviewService(env["db"], router)
    return svc, provider


async def test_full_text_interview_lifecycle(interview_env: dict[str, Any]) -> None:
    db = interview_env["db"]
    user_id = interview_env["user_id"]
    svc, provider = await _svc(interview_env, [QUESTION_JSON, EVAL_JSON, REPORT_JSON])

    session = await svc.create_session(
        user_id=user_id,
        kind=InterviewKind.PROJECT_DEEP_DIVE,
        role_id=None,
        duration_minutes=30,
        focus_competency_ids=[],
    )
    assert session.status == InterviewSessionStatus.CREATED

    await svc.begin(session.id, user_id)
    assert session.status == InterviewSessionStatus.QUESTIONING

    q, turn = await svc.next_question(session.id, user_id)
    assert q.text.startswith("Describe a distributed system")
    assert str(turn.kind) == InterviewTurnKind.QUESTION.value

    answer = await svc.submit_answer(
        session_id=session.id,
        user_id=user_id,
        question_id=q.id,
        answer_text="I built a stream processor and chose at-least-once delivery.",
        idempotency_key="key-1",
    )
    assert answer.id > 0

    from sqlalchemy import select

    from app.models.evidence import Evidence

    evidence_rows = list(await db.scalars(select(Evidence).where(Evidence.user_id == user_id)))
    assert any("event ingestion" in e.claim for e in evidence_rows)

    await svc.stop(session.id, user_id)
    assert session.status == InterviewSessionStatus.COMPLETED

    report = await svc.generate_report(session.id, user_id)
    assert "tradeoff" in report.lower()


async def test_duplicate_answer_returns_same_row(interview_env: dict[str, Any]) -> None:
    svc, _ = await _svc(interview_env, [QUESTION_JSON, EVAL_JSON])
    user_id = interview_env["user_id"]
    session = await svc.create_session(
        user_id=user_id,
        kind=InterviewKind.GENERAL,
        role_id=None,
        duration_minutes=20,
        focus_competency_ids=[],
    )
    await svc.begin(session.id, user_id)
    q, _ = await svc.next_question(session.id, user_id)

    a1 = await svc.submit_answer(
        session_id=session.id,
        user_id=user_id,
        question_id=q.id,
        answer_text="My answer.",
        idempotency_key="dup-key",
    )
    a2 = await svc.submit_answer(
        session_id=session.id,
        user_id=user_id,
        question_id=q.id,
        answer_text="My answer.",
        idempotency_key="dup-key",
    )
    assert a1.id == a2.id


async def test_hint_flow(interview_env: dict[str, Any]) -> None:
    svc, _ = await _svc(interview_env, [QUESTION_JSON, HINT_JSON])
    user_id = interview_env["user_id"]
    session = await svc.create_session(
        user_id=user_id,
        kind=InterviewKind.GENERAL,
        role_id=None,
        duration_minutes=20,
        focus_competency_ids=[],
    )
    await svc.begin(session.id, user_id)
    q, _ = await svc.next_question(session.id, user_id)

    hint = await svc.request_hint(session.id, user_id, q.id)
    assert "consistency" in hint
    # hints_used persisted on the question's turn.
    turns = await InterviewTurnRepository(interview_env["db"]).list_for_session(session.id)
    q_turn = next(t for t in turns if str(t.kind) == InterviewTurnKind.QUESTION.value)
    assert q_turn.hints_used == 1


async def test_state_transitions_enforced(interview_env: dict[str, Any]) -> None:
    svc, _ = await _svc(interview_env, [])
    user_id = interview_env["user_id"]
    session = await svc.create_session(
        user_id=user_id,
        kind=InterviewKind.GENERAL,
        role_id=None,
        duration_minutes=20,
        focus_competency_ids=[],
    )
    # Can't pause from CREATED.
    with pytest.raises(InterviewStateError):
        await svc.pause(session.id, user_id)


async def test_answer_rejected_in_wrong_state(interview_env: dict[str, Any]) -> None:
    svc, _ = await _svc(interview_env, [])
    user_id = interview_env["user_id"]
    session = await svc.create_session(
        user_id=user_id,
        kind=InterviewKind.GENERAL,
        role_id=None,
        duration_minutes=20,
        focus_competency_ids=[],
    )
    from app.domain.errors import InterviewStateError

    # Session is CREATED; answer submission requires QUESTIONING.
    from app.models.interview import Question

    q = Question(interview_session_id=session.id, difficulty="medium", type="general", text="q")
    q.id = 1
    with pytest.raises(InterviewStateError):
        await svc.submit_answer(
            session_id=session.id,
            user_id=user_id,
            question_id=q.id,
            answer_text="x",
            idempotency_key=None,
        )
