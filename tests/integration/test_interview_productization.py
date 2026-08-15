"""Productization integration tests (steps 2-9): profile-scoped grounding,
provenance, coverage rotation, follow-up routing, gap detection, prep
memory, styles, anti-hallucination guard, report v2, isolation.

LLM calls are faked via seeded QueueProvider/CycleProvider routers — fully
deterministic, no live model runs. Real Postgres + pgvector via the shared
integration fixtures (Alembic migrations, incl. 0005).
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
    CompetencyCategory,
    CompetencyImportance,
    DocumentKind,
    DocumentStatus,
    EvidenceSourceKind,
    EvidenceStatus,
    InterviewKind,
)
from app.interview.service import InterviewService
from app.knowledge.retrieval import RetrievalService
from app.models.document import Document, DocumentChunk
from app.models.evidence import Evidence
from app.models.role import Competency, Role
from app.services.user import CandidateService

# ---------------------------------------------------------------------------
# Fixture material (grounding fixture per the directive)
# ---------------------------------------------------------------------------

RESUME_TEXT = """Alex Rivera
Senior Full-Stack Engineer

EXPERIENCE
TechFlow Inc — Senior Engineer (2021-2024)
Led a 4-person platform team building an analytics dashboard.

PROJECTS
Atlas — real-time analytics platform. Angular 16 frontend, Node.js API,
MongoDB storage, deployed on AWS. Delivered -42% API latency via
response caching and query optimization.

TechFlow portal — internal tooling for support agents (React 18).

SKILLS
Angular, React, Node.js, TypeScript, MongoDB, PostgreSQL, AWS, Docker
"""

JD_TEXT = """Senior Full-Stack Engineer (React/Next.js focus)
We build LLM-powered applications with a React + Next.js frontend and a
Python FastAPI backend. You will own system design for new features,
integrate LLM APIs, and scale the platform.

Requirements: React, Next.js, Python, FastAPI, TypeScript, system design,
LLM application development.
"""

CLAIM_A = "Technology: Angular"
CLAIM_PROJECT = "Project: Atlas"
CLAIM_METRIC = "Achievement (Atlas): cut API latency by 42% with caching"
CLAIM_NODE = "Technology: Node.js"
CLAIM_B_ONLY = "Technology: KafkaStreams"  # profile B only — must never leak into A


def q(
    text: str,
    *,
    competency: str,
    category: str = "project_deep_dive",
    source: str = "resume",
    source_ref: str = "Atlas",
) -> str:
    return (
        f"QUESTION: {text}\n"
        f"CATEGORY: {category}\n"
        f"SOURCE: {source}\n"
        f"SOURCE_REF: {source_ref}\n"
        f"DIFFICULTY: medium\n"
        f"TYPE: project_deep_dive\n"
        f"RATIONALE: probes grounding\n"
        f"TARGET: {competency}\n"
        f"HINTS:\n- h"
    )


def ev(overall: float = 7.0) -> str:
    return json.dumps(
        {
            "dimensions": {
                "correctness": overall,
                "technical_depth": overall - 1,
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
            "overall": overall,
            "confidence": 0.85,
            "strengths": ["Clear tradeoff discussion", "Concrete metrics"],
            "weaknesses": ["Missing edge-case analysis"],
            "missing_evidence": ["Quantified impact"],
            "follow_ups": ["How did you measure the latency drop?"],
            "evidence": [
                {
                    "claim": "Built the Atlas analytics platform",
                    "status": "observed",
                    "strength": 0.8,
                    "competency_hint": "architecture",
                }
            ],
        }
    )


def reason(
    decision: str = "follow_up_deep", topic: str | None = None, gaps: list[str] | None = None
) -> str:
    return json.dumps(
        {
            "decision": decision,
            "reason": "thread worth excavating",
            "topic": topic,
            "gaps_detected": gaps or [],
            "coverage_tags": ["architecture"],
        }
    )


# ---------------------------------------------------------------------------
# Seeded fakes
# ---------------------------------------------------------------------------


class QueueProvider:
    name = "fake"

    def __init__(self, contents: list[str]) -> None:
        self.contents = contents
        self.calls: list[Any] = []

    async def generate(self, request: Any) -> ChatResponse:
        self.calls.append(request)
        content = self.contents.pop(0) if self.contents else "{}"
        return ChatResponse(content=content, model="fake", usage=Usage(total_tokens=1))


class CycleProvider:
    """Rotates through contents deterministically (long simulations)."""

    name = "fake"

    def __init__(self, contents: list[str]) -> None:
        self.contents = contents
        self.calls: list[Any] = []

    async def generate(self, request: Any) -> ChatResponse:
        self.calls.append(request)
        content = self.contents[(len(self.calls) - 1) % len(self.contents)]
        return ChatResponse(content=content, model="fake", usage=Usage(total_tokens=1))


def _router(provider: Any) -> InferenceRouter:
    return InferenceRouter(policy=TaskPolicyTable(), omlx=None, deepseek=provider)


async def _svc(db: AsyncSession, contents: list[str]) -> tuple[InterviewService, QueueProvider]:
    provider = QueueProvider(contents)
    svc = InterviewService(db, _router(provider))
    return svc, provider


def _prompt_context(provider: Any, call_index: int = -1) -> dict[str, Any]:
    """Parse the question-generation prompt context from a provider call."""
    request = provider.calls[call_index]
    user_message = request.messages[-1]
    return json.loads(str(user_message.content))


def _target(provider: Any, call_index: int) -> str:
    """target_competency of the nth question-generation call."""
    return str(_prompt_context(provider, call_index).get("target_competency", ""))


# ---------------------------------------------------------------------------
# Seeders
# ---------------------------------------------------------------------------


async def seed_user_profile(
    db: AsyncSession, *, name: str, positioning: str | None = None
) -> tuple[int, int]:
    user = await CandidateService(db).create_user(display_name=name)
    profile = await CandidateService(db).create_profile(
        user_id=user.id,
        name=name,
        positioning=positioning,
        seniority_target="senior",
        headline="Engineer",
    )
    await db.commit()
    return user.id, profile.id


async def seed_document(
    db: AsyncSession,
    *,
    user_id: int,
    profile_id: int,
    kind: DocumentKind,
    filename: str,
    text: str,
) -> int:
    doc = Document(
        user_id=user_id,
        profile_id=profile_id,
        kind=kind,
        filename=filename,
        mime="text/markdown",
        size=len(text.encode()),
        content_hash=f"hash-{kind.value}-{filename}-{len(text)}",
        status=DocumentStatus.PARSED,
    )
    db.add(doc)
    await db.flush()
    for idx, para in enumerate([p for p in text.split("\n\n") if p.strip()]):
        db.add(
            DocumentChunk(
                document_id=doc.id,
                chunk_index=idx,
                content=para.strip(),
            )
        )
    await db.commit()
    return doc.id


async def seed_evidence(db: AsyncSession, user_id: int, profile_id: int, claims: list[str]) -> None:
    for claim in claims:
        db.add(
            Evidence(
                user_id=user_id,
                profile_id=profile_id,
                source_kind=EvidenceSourceKind.RESUME,
                source_ref="document:1",
                claim=claim,
                status=EvidenceStatus.CLAIMED,
            )
        )
    await db.commit()


async def seed_role(
    db: AsyncSession,
    *,
    user_id: int,
    profile_id: int,
    competencies: list[tuple[str, CompetencyImportance]],
) -> int:
    role = Role(
        user_id=user_id,
        profile_id=profile_id,
        title="Senior Full-Stack Engineer",
        seniority="senior",
        summary="Full-stack + LLM applications",
    )
    db.add(role)
    await db.flush()
    for rank, (name, importance) in enumerate(competencies):
        db.add(
            Competency(
                role_id=role.id,
                name=name,
                category=CompetencyCategory.ARCHITECTURE,
                level=4,
                importance=importance,
                weight=0.5,
                importance_rank=rank,
            )
        )
    await db.commit()
    return role.id


async def seed_grounded_profile(
    db: AsyncSession, *, name: str = "AI Engineer"
) -> tuple[int, int, int]:
    user_id, profile_id = await seed_user_profile(db, name=name)
    await seed_document(
        db,
        user_id=user_id,
        profile_id=profile_id,
        kind=DocumentKind.RESUME,
        filename="resume.md",
        text=RESUME_TEXT,
    )
    await seed_document(
        db,
        user_id=user_id,
        profile_id=profile_id,
        kind=DocumentKind.JD,
        filename="jd.md",
        text=JD_TEXT,
    )
    await seed_evidence(db, user_id, profile_id, [CLAIM_A, CLAIM_PROJECT, CLAIM_METRIC, CLAIM_NODE])
    role_id = await seed_role(
        db,
        user_id=user_id,
        profile_id=profile_id,
        competencies=[
            ("System Design", CompetencyImportance.REQUIRED),
            ("Full-Stack Engineering", CompetencyImportance.REQUIRED),
            ("LLM Applications", CompetencyImportance.PREFERRED),
        ],
    )
    return user_id, profile_id, role_id


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_context_snapshot_is_profile_scoped_and_grounded(
    db_session: AsyncSession,
) -> None:
    user_id, profile_id, _role_id = await seed_grounded_profile(db_session)
    _ub, profile_b, _rb = await seed_grounded_profile(db_session, name="FDE")
    await seed_evidence(db_session, user_id, profile_b, [CLAIM_B_ONLY])

    from app.services.interview_context import InterviewContextBuilder, resume_signals

    builder = InterviewContextBuilder(db_session)
    snapshot = await builder.build(user_id=user_id, profile_id=profile_id, role_id=_role_id)

    assert snapshot["profile"]["name"] == "AI Engineer"
    resume = snapshot["resume"]
    assert "Atlas" in resume["text"] and "Angular 16" in resume["text"]
    jd = snapshot["jd"]
    assert "FastAPI" in jd["text"]
    evidence_text = " ".join(str(e["claim"]) for e in snapshot["evidence"])
    assert "Atlas" in evidence_text
    assert CLAIM_B_ONLY not in evidence_text  # profile isolation

    signals = resume_signals(snapshot["evidence"] or [])
    assert "Angular" in signals["technologies"]
    assert "Atlas" in signals["projects"]

    comps = snapshot["role"]["competencies"]
    assert {"System Design", "Full-Stack Engineering", "LLM Applications"} <= {
        c["name"] for c in comps
    }


async def test_retrieval_search_filters_by_profile(db_session: AsyncSession) -> None:
    user_id, profile_a, _ = await seed_grounded_profile(db_session)
    _ub, profile_b, _ = await seed_grounded_profile(db_session, name="FDE")

    provider = QueueProvider([])
    retrieval = RetrievalService(db_session, _router(provider))

    # Query for Atlas: must only return profile A chunks (FTS leg; vector
    # leg degrades because the fake router has no embedding provider).
    result_a = await retrieval.search(user_id, "Atlas analytics Angular", profile_id=profile_a)
    assert result_a.chunks
    assert all(str(c.kind) == "resume" for c in result_a.chunks)

    result_b = await retrieval.search(user_id, "Atlas analytics Angular", profile_id=profile_b)
    assert not any("Atlas" in c.content for c in result_b.chunks)


async def test_question_provenance_persisted_and_coverage_tracked(
    db_session: AsyncSession,
) -> None:
    user_id, profile_id, role_id = await seed_grounded_profile(db_session)
    svc, provider = await _svc(
        db_session,
        [
            q(
                "Walk me through the Atlas analytics platform — what did you build and why"
                " Angular 16?",
                competency="Full-Stack Engineering",
            )
        ],
    )
    session = await svc.create_session(
        user_id=user_id,
        kind=InterviewKind.TECHNICAL,
        role_id=role_id,
        duration_minutes=30,
        focus_competency_ids=[],
        profile_id=profile_id,
    )
    await svc.begin(session.id, user_id)
    question, _turn = await svc.next_question(session.id, user_id)

    assert question.category == "project_deep_dive"
    assert question.source == "resume"
    assert question.source_ref == "Atlas"
    assert "Atlas" in question.text
    # Prompt context is grounded in profile-A material only.
    ctx = _prompt_context(provider)
    assert CLAIM_B_ONLY not in json.dumps(ctx)
    assert "Atlas" in json.dumps(ctx)

    cfg = session.config or {}
    coverage = cfg["coverage"]
    assert "project_deep_dive" in coverage["categories"]
    assert "Full-Stack Engineering" in coverage["competencies"]


async def test_focus_rotation_over_uncovered_competencies(db_session: AsyncSession) -> None:
    user_id, profile_id, role_id = await seed_grounded_profile(db_session)
    contents = [
        q("Q1 System Design?", competency="System Design"),
        q("Q2 Full-Stack?", competency="Full-Stack Engineering"),
        q("Q3 LLM?", competency="LLM Applications"),
    ]
    svc, provider = await _svc(db_session, contents)
    session = await svc.create_session(
        user_id=user_id,
        kind=InterviewKind.TECHNICAL,
        role_id=role_id,
        duration_minutes=30,
        focus_competency_ids=[],
        profile_id=profile_id,
    )
    await svc.begin(session.id, user_id)

    for _ in range(3):
        await svc.next_question(session.id, user_id)

    # Coverage tracks PERSISTED targets (what was actually asked): with 3
    # questions over 3 competencies, every competency gets covered.
    coverage = (session.config or {})["coverage"]
    assert sorted(coverage["competencies"]) == sorted(
        ["System Design", "Full-Stack Engineering", "LLM Applications"]
    )
    svc2, provider2 = await _svc(
        db_session,
        [
            q("Q1 System Design?", competency="System Design"),
            q("Q2 Full-Stack?", competency="Full-Stack Engineering"),
            q("Q3 LLM?", competency="LLM Applications"),
        ],
    )
    session2 = await svc2.create_session(
        user_id=user_id,
        kind=InterviewKind.TECHNICAL,
        role_id=role_id,
        duration_minutes=30,
        focus_competency_ids=[],
        profile_id=profile_id,
    )
    await svc2.begin(session2.id, user_id)
    await svc2.next_question(session2.id, user_id)
    # Focus selection is deterministic per session id: recompute the seeded
    # pick for THIS actual session id and compare (ids are never equal across
    # sessions, so the historical same-id assertion was order-dependent).
    import random

    from app.services.coverage import focus_competency, new_coverage

    comps = ["System Design", "Full-Stack Engineering", "LLM Applications"]
    expected_pick = focus_competency(new_coverage(), comps, random.Random(session2.id))  # noqa: S311 — seeded, deterministic test RNG
    assert _target(provider2, 0) == expected_pick


async def test_follow_up_directive_flows_into_next_question(db_session: AsyncSession) -> None:
    user_id, profile_id, role_id = await seed_grounded_profile(db_session)
    svc, provider = await _svc(
        db_session,
        [
            q("Describe the Atlas project.", competency="System Design"),
            ev(overall=7.5),
            reason("follow_up_deep", topic="System Design"),
            q(
                "How did you measure the 42% latency improvement on Atlas?",
                competency="System Design",
                source="followup",
                source_ref="42% latency",
            ),
        ],
    )
    session = await svc.create_session(
        user_id=user_id,
        kind=InterviewKind.TECHNICAL,
        role_id=role_id,
        duration_minutes=30,
        focus_competency_ids=[],
        profile_id=profile_id,
    )
    await svc.begin(session.id, user_id)

    q1, _ = await svc.next_question(session.id, user_id)
    await svc.submit_answer(
        session_id=session.id,
        user_id=user_id,
        question_id=q1.id,
        answer_text="Atlas cut API latency by 42% via caching and query tuning.",
        idempotency_key=None,
    )
    cfg = session.config or {}
    directives = cfg.get("directives") or {}
    assert str(q1.id) in directives
    assert directives[str(q1.id)]["decision"] == "follow_up_deep"

    # Next question consumes the directive: focus prefers the topic and the
    # prompt carries the directive.
    q2, _ = await svc.next_question(session.id, user_id)
    ctx = _prompt_context(provider)
    directive = ctx.get("follow_up_directive") or {}
    assert directive.get("decision") == "follow_up_deep"
    assert directive.get("topic") == "System Design"
    assert "42%" in q2.text


async def test_previous_weakness_influences_next_session(db_session: AsyncSession) -> None:
    user_id, profile_id, role_id = await seed_grounded_profile(db_session)
    svc, provider = await _svc(
        db_session,
        [
            q("Q1", competency="System Design"),
            ev(overall=3.5),
            reason("change_topic", gaps=["System Design"]),
        ],
    )
    session = await svc.create_session(
        user_id=user_id,
        kind=InterviewKind.TECHNICAL,
        role_id=role_id,
        duration_minutes=30,
        focus_competency_ids=[],
        profile_id=profile_id,
    )
    await svc.begin(session.id, user_id)
    q1, _ = await svc.next_question(session.id, user_id)
    await svc.submit_answer(
        session_id=session.id,
        user_id=user_id,
        question_id=q1.id,
        answer_text="Weak answer without detail.",
        idempotency_key=None,
    )
    await svc.stop(session.id, user_id)

    from sqlalchemy import select

    from app.models.interview_feedback import InterviewFeedback

    rows = list(
        await db_session.scalars(
            select(InterviewFeedback).where(InterviewFeedback.profile_id == profile_id)
        )
    )
    assert rows
    assert rows[0].weaknesses  # written at stop()
    assert rows[0].gaps  # gap detected for System Design

    # A NEW session on the same profile reads the prep memory.
    svc2, _ = await _svc(db_session, [q("Q2", competency="System Design")])
    session2 = await svc2.create_session(
        user_id=user_id,
        kind=InterviewKind.TECHNICAL,
        role_id=role_id,
        duration_minutes=30,
        focus_competency_ids=[],
        profile_id=profile_id,
    )
    await svc2.begin(session2.id, user_id)
    cfg = session2.config or {}
    prior = cfg["context"]["prior_feedback"]
    assert prior and prior[0]["weaknesses"]


async def test_gap_detection_writes_config_gaps(db_session: AsyncSession) -> None:
    user_id, profile_id, role_id = await seed_grounded_profile(db_session)
    svc, provider = await _svc(
        db_session,
        [
            q("Q1", competency="System Design"),
            ev(overall=6.0),
            reason("move_on", gaps=["React"]),
        ],
    )
    session = await svc.create_session(
        user_id=user_id,
        kind=InterviewKind.TECHNICAL,
        role_id=role_id,
        duration_minutes=30,
        focus_competency_ids=[],
        profile_id=profile_id,
    )
    await svc.begin(session.id, user_id)
    q1, _ = await svc.next_question(session.id, user_id)
    await svc.submit_answer(
        session_id=session.id,
        user_id=user_id,
        question_id=q1.id,
        answer_text="I built Atlas with Angular and Node.",
        idempotency_key=None,
    )
    cfg = session.config or {}
    gaps = cfg["gaps"]
    # "React" from reasoning + "Full-Stack Engineering" (required, uncovered,
    # absent from evidence) must appear. "System Design" was asked — not a gap.
    assert "React" in gaps
    assert "Full-Stack Engineering" in gaps
    assert "System Design" not in gaps


async def test_style_reaches_question_prompt(db_session: AsyncSession) -> None:
    user_id, profile_id, role_id = await seed_grounded_profile(db_session)
    svc, provider = await _svc(db_session, [q("Q1", competency="System Design")])
    session = await svc.create_session(
        user_id=user_id,
        kind=InterviewKind.TECHNICAL,
        role_id=role_id,
        duration_minutes=30,
        focus_competency_ids=[],
        profile_id=profile_id,
        style="technical_expert",
    )
    await svc.begin(session.id, user_id)
    await svc.next_question(session.id, user_id)
    ctx = _prompt_context(provider)
    assert ctx["style"] == "technical_expert"
    assert ctx["time_budget"]["minutes"] == 30


async def test_unknown_style_rejected(db_session: AsyncSession) -> None:
    from app.domain.errors import ValidationFailedError

    user_id, profile_id, role_id = await seed_grounded_profile(db_session)
    svc, _ = await _svc(db_session, [])
    with pytest.raises(ValidationFailedError):
        await svc.create_session(
            user_id=user_id,
            kind=InterviewKind.TECHNICAL,
            role_id=role_id,
            duration_minutes=30,
            focus_competency_ids=[],
            profile_id=profile_id,
            style="hostile",
        )


async def test_entity_guard_regenerates_question_once(db_session: AsyncSession) -> None:
    user_id, profile_id, role_id = await seed_grounded_profile(db_session)
    invented = q(
        "Describe your KafkaStreams pipeline — how did you tune its lag?",
        competency="System Design",
        source="resume",
        source_ref="KafkaStreams",
    )
    grounded = q(
        "Walk me through the Atlas project again, focusing on the Node API.",
        competency="System Design",
        source="resume",
        source_ref="Atlas",
    )
    svc, provider = await _svc(db_session, [invented, grounded])
    session = await svc.create_session(
        user_id=user_id,
        kind=InterviewKind.TECHNICAL,
        role_id=role_id,
        duration_minutes=30,
        focus_competency_ids=[],
        profile_id=profile_id,
    )
    await svc.begin(session.id, user_id)
    question, _ = await svc.next_question(session.id, user_id)

    assert len(provider.calls) == 2  # guard regenerated once
    assert "KafkaStreams" not in question.text
    assert "Atlas" in question.text


async def test_report_v2_deterministic_scorecard(db_session: AsyncSession) -> None:
    user_id, profile_id, role_id = await seed_grounded_profile(db_session)
    svc, _ = await _svc(
        db_session,
        [
            q("Q1", competency="System Design"),
            ev(overall=8.0),
            reason("follow_up_deep", topic="System Design"),
            q("Q2 follow-up", competency="System Design", source="followup", source_ref="42%"),
            ev(overall=4.0),
            reason("change_topic"),
        ],
    )
    session = await svc.create_session(
        user_id=user_id,
        kind=InterviewKind.TECHNICAL,
        role_id=role_id,
        duration_minutes=30,
        focus_competency_ids=[],
        profile_id=profile_id,
    )
    await svc.begin(session.id, user_id)
    q1, _ = await svc.next_question(session.id, user_id)
    await svc.submit_answer(
        session_id=session.id,
        user_id=user_id,
        question_id=q1.id,
        answer_text="Strong structured answer with metrics.",
        idempotency_key=None,
    )
    q2, _ = await svc.next_question(session.id, user_id)
    await svc.submit_answer(
        session_id=session.id,
        user_id=user_id,
        question_id=q2.id,
        answer_text="Shallow answer without specifics.",
        idempotency_key=None,
    )
    await svc.stop(session.id, user_id)

    data = await svc.report_data(session.id, user_id)
    scorecard = data.scorecard
    assert scorecard["overall"] == 6.0  # (8.0 + 4.0) / 2
    assert scorecard["correctness"] == 6.0  # (8.0 + 4.0) / 2
    rows = data.questions
    assert len(rows) == 2
    assert rows[0]["good"]
    assert rows[1]["prep_recommendation"].startswith("re-practice")  # overall 4.0
    assert data.gaps  # LLM Applications required/uncovered


async def test_30_minute_simulation_covers_without_repetition(db_session: AsyncSession) -> None:
    user_id, profile_id, role_id = await seed_grounded_profile(db_session)
    comps_cycle = [
        "System Design",
        "Full-Stack Engineering",
        "LLM Applications",
        "System Design",
        "Full-Stack Engineering",
        "LLM Applications",
    ]
    cat_cycle = [
        "architecture_design",
        "frontend_engineering",
        "llm_ai_applications",
        "system_scaling",
        "api_design",
        "performance_optimization",
    ]
    contents: list[str] = []
    for i, comp in enumerate(comps_cycle):
        contents.append(
            q(
                f"Question {i + 1} about {comp}.",
                competency=comp,
                category=cat_cycle[i],
            )
        )
        contents.append(ev(overall=6.0 + (i % 2)))
        contents.append(reason("follow_up_light" if i % 2 else "move_on"))

    svc, provider = await _svc(db_session, contents)
    session = await svc.create_session(
        user_id=user_id,
        kind=InterviewKind.TECHNICAL,
        role_id=role_id,
        duration_minutes=30,
        focus_competency_ids=[],
        profile_id=profile_id,
    )
    await svc.begin(session.id, user_id)

    texts: list[str] = []
    for _ in range(6):
        question, _ = await svc.next_question(session.id, user_id)
        texts.append(question.text)
        await svc.submit_answer(
            session_id=session.id,
            user_id=user_id,
            question_id=question.id,
            answer_text=f"Answer covering {question.target_competency}.",
            idempotency_key=None,
        )

    assert len(set(texts)) == 6  # no repeated question text
    coverage = (session.config or {})["coverage"]
    assert len(coverage["competencies"]) == 3  # all competencies rotated
    assert len(coverage["categories"]) >= 3
    directives = (session.config or {})["directives"]
    assert len(directives) == 6
