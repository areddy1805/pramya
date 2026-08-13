"""Extraction + role-analysis service tests (Phase 2.4/2.5).

Fake generation provider returns valid structured JSON; services must
validate it, persist claimed evidence / role graph, and never persist
unvalidated output.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.contracts import ChatMessage, ChatResponse, Usage
from app.ai.policy import TaskPolicyTable
from app.ai.router import InferenceRouter
from app.domain.enums import EvidenceSourceKind, EvidenceStatus
from app.services.extraction import ExtractionService
from app.services.role import RoleAnalysisService

RESUME_JSON = json.dumps(
    {
        "headline": "Senior Backend Engineer",
        "seniority_target": "senior",
        "roles": [{"title": "Staff Engineer", "company": "Acme", "years": 6}],
        "technologies": ["Python", "PostgreSQL"],
        "projects": [{"name": "Checkout", "achievements": ["Reduced p95 by 40%"]}],
        "achievements": ["Led 4-person team"],
        "claims": ["Built a fraud detection system used by 2M users"],
        "certifications": ["AWS SA Pro"],
        "strengths": ["Systems thinking"],
        "gaps": ["No mobile experience"],
    }
)

ROLE_JSON = json.dumps(
    {
        "title": "Senior Full Stack Engineer",
        "seniority": "senior",
        "summary": "Own features end to end",
        "required_skills": ["React", "Python"],
        "preferred_skills": ["PostgreSQL"],
        "responsibilities": ["Build features", "Mentor juniors"],
        "competencies": [
            {
                "name": "React",
                "category": "frontend",
                "level": 4,
                "importance": "required",
                "weight": 0.3,
            },
            {
                "name": "System Design",
                "category": "architecture",
                "level": 3,
                "importance": "required",
                "weight": 0.2,
            },
        ],
        "implied_skills": ["Scaling"],
    }
)


class QueueProvider:
    name = "fake"

    def __init__(self, contents: list[str], *, fallback: str | None = None) -> None:
        self.contents = contents
        self.fallback = fallback
        self.calls: list[list[ChatMessage]] = []

    async def generate(self, request: Any) -> ChatResponse:
        self.calls.append(request.messages)
        if self.contents:
            content = self.contents.pop(0)
        elif self.fallback is not None:
            content = self.fallback
        else:
            content = "{}"
        return ChatResponse(content=content, model="fake", usage=Usage(total_tokens=1))


def _router(provider: QueueProvider) -> InferenceRouter:
    return InferenceRouter(policy=TaskPolicyTable(), omlx=None, deepseek=provider)


@pytest.fixture
async def db_user(db_session: AsyncSession) -> int:
    from app.services.user import CandidateService

    user = await CandidateService(db_session).create_user(display_name="Test")
    await db_session.commit()
    return user.id


async def test_extraction_persists_claimed_evidence(db_session: AsyncSession, db_user: int) -> None:
    from app.models.document import Document

    doc = Document(
        user_id=db_user,
        kind="resume",
        filename="r.txt",
        mime="text/plain",
        size=10,
        content_hash="h1",
        status="parsed",
    )
    doc.id = 1
    svc = ExtractionService(db_session, _router(QueueProvider([RESUME_JSON])))
    result = await svc.extract_resume(db_user, doc, "resume text")
    await db_session.commit()

    assert result.headline == "Senior Backend Engineer"
    from sqlalchemy import select

    from app.models.evidence import Evidence

    rows = list(await db_session.scalars(select(Evidence).where(Evidence.user_id == db_user)))
    assert len(rows) >= 8
    for row in rows:
        assert row.status == EvidenceStatus.CLAIMED
        assert row.source_kind == EvidenceSourceKind.RESUME
    claims = " | ".join(r.claim for r in rows)
    assert "Staff Engineer" in claims
    assert "Python" in claims
    assert "Reduced p95" in claims


async def test_extraction_rejects_invalid_output(db_session: AsyncSession, db_user: int) -> None:
    from app.ai.errors import StructuredOutputError
    from app.models.document import Document

    doc = Document(
        user_id=db_user,
        kind="resume",
        filename="r.txt",
        mime="text/plain",
        size=10,
        content_hash="h2",
        status="parsed",
    )
    doc.id = 2
    svc = ExtractionService(
        db_session,
        _router(QueueProvider(["not json", "still bad", "nope"])),
    )
    with pytest.raises(StructuredOutputError):
        await svc.extract_resume(db_user, doc, "text")


async def test_role_analysis_persists_competency_graph(
    db_session: AsyncSession, db_user: int
) -> None:
    svc = RoleAnalysisService(db_session, _router(QueueProvider([ROLE_JSON])))
    role = await svc.analyze(db_user, "We need a senior full stack engineer.")
    await db_session.commit()

    assert role.title == "Senior Full Stack Engineer"
    competencies = await svc.roles.list_competencies(role.id)
    assert len(competencies) == 2
    assert competencies[0].name == "React"
    assert str(competencies[0].importance) == "required"
    assert competencies[0].level == 4
    # importance_rank follows input order.
    assert competencies[1].importance_rank == 1


async def test_role_analysis_rejects_invalid_output(db_session: AsyncSession, db_user: int) -> None:
    from app.ai.errors import StructuredOutputError

    svc = RoleAnalysisService(
        db_session,
        _router(QueueProvider(["not json", "bad", "nope"])),
    )
    with pytest.raises(StructuredOutputError):
        await svc.analyze(db_user, "JD text " * 5)


async def test_role_analysis_requires_competencies(db_session: AsyncSession, db_user: int) -> None:
    from app.domain.errors import ValidationFailedError

    svc = RoleAnalysisService(
        db_session,
        _router(QueueProvider(['{"title": "T", "competencies": []}'])),
    )
    with pytest.raises(ValidationFailedError):
        await svc.analyze(db_user, "JD text " * 5)
