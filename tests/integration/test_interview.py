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

QUESTION_TEXT = (
    "QUESTION: Describe a distributed system you built and a hard tradeoff you faced.\n"
    "TYPE: project_deep_dive\n"
    "DIFFICULTY: medium\n"
    "RATIONALE: Probes architecture + tradeoff awareness\n"
    "TARGET: System Design\n"
    "HINTS:\n"
    "- Think about consistency\n"
    "- Consider CAP\n"
    "- Sketch the design"
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
    router = InferenceRouter(policy=TaskPolicyTable(), omlx=None, deepseek=provider)
    svc = InterviewService(env["db"], router)
    return svc, provider


async def test_full_text_interview_lifecycle(interview_env: dict[str, Any]) -> None:
    db = interview_env["db"]
    user_id = interview_env["user_id"]
    svc, provider = await _svc(interview_env, [QUESTION_TEXT, EVAL_JSON, REPORT_JSON])

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
    svc, _ = await _svc(interview_env, [QUESTION_TEXT, EVAL_JSON])
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
    svc, _ = await _svc(interview_env, [QUESTION_TEXT, HINT_JSON])
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


async def test_transcript_records_questions_answers_and_evaluations(
    interview_env: dict[str, Any],
) -> None:
    """Phase K: the durable interview record exposes Q/A/evaluation in order."""
    db = interview_env["db"]
    user_id = interview_env["user_id"]
    svc, _provider = await _svc(interview_env, [QUESTION_TEXT, EVAL_JSON])

    session = await svc.create_session(
        user_id=user_id,
        kind=InterviewKind.GENERAL,
        role_id=None,
        duration_minutes=20,
        focus_competency_ids=[],
    )
    await svc.begin(session.id, user_id)
    q, _turn = await svc.next_question(session.id, user_id)
    await svc.submit_answer(
        session_id=session.id,
        user_id=user_id,
        question_id=q.id,
        answer_text="I led a distributed systems migration.",
        idempotency_key=None,
    )

    records = await svc.transcript(session.id, user_id)
    assert len(records) >= 2  # question turn + answer turn
    question_turns = [r for r in records if r.question is not None]
    assert question_turns, "expected at least one question turn"
    assert question_turns[0].question_id == q.id
    answered = [r for r in records if r.answer is not None]
    assert answered and answered[0].answer == "I led a distributed systems migration."
    assert answered[0].evaluation_overall is not None

    # Ownership check: another user cannot read the transcript.
    from app.domain.errors import NotFoundError

    other = await CandidateService(db).create_user(display_name="Other")
    await db.commit()
    with pytest.raises(NotFoundError):
        await svc.transcript(session.id, other.id)


async def test_next_question_streaming_yields_tokens_then_question(
    interview_env: dict[str, Any],
) -> None:
    """V1.1: the streaming question generator surfaces model tokens (via
    LangGraph stream_mode='messages') and then the persisted question —
    proving the realtime path (StateSnapshot readback) works end to end."""
    user_id = interview_env["user_id"]
    # Token-streaming fake: the workflow's RouterChatModel.astream consumes
    # deltas via router.stream(); QueueProvider has no stream surface so the
    # router falls back to a single-chunk yield — still token-shaped.
    svc, _provider = await _svc(interview_env, [QUESTION_TEXT])
    session = await svc.create_session(
        user_id=user_id,
        kind=InterviewKind.PROJECT_DEEP_DIVE,
        role_id=None,
        duration_minutes=30,
        focus_competency_ids=[],
    )
    await svc.begin(session.id, user_id)

    tokens: list[str] = []
    question: object | None = None
    async for kind, payload in svc.next_question_streaming(session.id, user_id):
        if kind == "token":
            tokens.append(payload)
        elif kind == "question":
            question = payload

    assert "".join(tokens), "expected streamed tokens"
    assert question is not None
    q, turn = question  # type: ignore[misc]
    assert str(q.text).startswith("Describe a distributed system")
    assert turn.id is not None
    # Durable: the question was persisted by the streaming path.
    rows = await svc.questions.list_for_session(session.id)
    assert len(rows) == 1
