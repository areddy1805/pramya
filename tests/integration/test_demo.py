"""Demo mode integration test (Phase J).

Proves the demo pipeline is real and idempotent: profile creation, resume
upload + indexing (fake embed provider), evidence extraction + role analysis
(fake generation provider), readiness, and preparation — then a second run
must NOT duplicate documents, roles, or evidence.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.contracts import ChatResponse, EmbedResponse, Usage
from app.ai.policy import TaskPolicyTable
from app.ai.router import InferenceRouter
from app.core.config import Settings
from app.models.document import Document
from app.models.evidence import Evidence
from app.models.role import Role
from app.services.demo import DemoService
from app.services.user import CandidateService

RESUME_JSON = json.dumps(
    {
        "headline": "Senior Full Stack Engineer",
        "seniority_target": "senior",
        "roles": [{"title": "Staff Engineer", "company": "Acme", "years": 6}],
        "technologies": ["React", "Python"],
        "projects": [{"name": "Portal", "achievements": ["Cut bundle 58%"]}],
        "achievements": ["Led 4-person team"],
        "claims": ["Owned customer portal"],
        "certifications": [],
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


class FakeQueue:
    name = "fake"

    def __init__(self, contents: list[str]) -> None:
        self.contents = contents
        self.calls: list[Any] = []

    async def generate(self, request: Any) -> ChatResponse:
        self.calls.append(request)
        content = self.contents.pop(0) if self.contents else "{}"
        return ChatResponse(content=content, model="fake", usage=Usage(total_tokens=1))


class FakeEmbed:
    name = "fake-embed"

    async def embed(self, request: Any) -> EmbedResponse:
        return EmbedResponse(
            embeddings=[[0.0] * 1024 for _ in request.texts],
            model="fake",
            dimension=1024,
        )


def _router(provider: FakeQueue) -> InferenceRouter:
    return InferenceRouter(
        policy=TaskPolicyTable(),
        omlx=FakeEmbed(),
        deepseek=provider,  # type: ignore[arg-type]
    )


async def _counts(db: AsyncSession, user_id: int) -> tuple[int, int, int]:
    docs = int(
        (
            await db.scalars(
                select(func.count()).select_from(Document).where(Document.user_id == user_id)
            )
        ).one()
    )
    roles = int(
        (
            await db.scalars(select(func.count()).select_from(Role).where(Role.user_id == user_id))
        ).one()
    )
    evidence = int(
        (
            await db.scalars(
                select(func.count()).select_from(Evidence).where(Evidence.user_id == user_id)
            )
        ).one()
    )
    return docs, roles, evidence


async def test_demo_setup_is_idempotent(db_session: AsyncSession, tmp_path) -> None:
    user = await CandidateService(db_session).create_user(display_name="Demo")
    await db_session.commit()
    user_id = user.id  # cache: later demo commits expire ORM instances

    # Two runs need two rounds of generation JSON (extract + role per run);
    # the second run must NOT consume them (dedup by source_ref + role title).
    provider = FakeQueue([RESUME_JSON, ROLE_JSON])
    settings = Settings(upload_storage_dir=str(tmp_path))
    svc = DemoService(db_session, settings=settings, router=_router(provider))

    first = await svc.setup(user_id, roles=["senior-fullstack"])
    await db_session.commit()
    assert first.profile == "created"
    assert first.roles[0].chunks > 0
    assert first.roles[0].evidence_count > 0
    assert first.roles[0].competencies == 2
    assert first.preparation_items >= 0  # 0 is valid when no critical gaps

    docs1, roles1, evidence1 = await _counts(db_session, user_id)
    assert docs1 == 1
    assert roles1 == 1
    assert evidence1 > 0

    # Second run: dedup everything; generation provider must not be called.
    second = await svc.setup(user_id, roles=["senior-fullstack"])
    await db_session.commit()
    assert second.profile == "exists"
    assert second.roles[0].document_id == first.roles[0].document_id
    assert second.roles[0].role_id == first.roles[0].role_id
    assert second.roles[0].evidence_count == first.roles[0].evidence_count

    docs2, roles2, evidence2 = await _counts(db_session, user_id)
    assert (docs2, roles2, evidence2) == (docs1, roles1, evidence1)

    calls_after_first = len(provider.calls)
    # No further generation calls happened during the dedup'd second run.
    assert calls_after_first == 2  # exactly extract + role from run one


async def test_demo_setup_multiple_roles(db_session: AsyncSession, tmp_path) -> None:
    user = await CandidateService(db_session).create_user(display_name="Demo2")
    await db_session.commit()
    user_id = user.id

    contents: list[str] = []
    for _ in range(2):  # two roles -> extract + role each
        contents += [RESUME_JSON, ROLE_JSON]
    provider = FakeQueue(contents)
    settings = Settings(upload_storage_dir=str(tmp_path))
    svc = DemoService(db_session, settings=settings, router=_router(provider))

    result = await svc.setup(user_id, roles=["senior-fullstack", "frontend"])
    await db_session.commit()
    assert len(result.roles) == 2
    docs, roles, _ = await _counts(db_session, user_id)
    assert docs == 2
    assert roles == 2
    assert len(provider.calls) == 4


async def test_demo_unknown_role_rejected(db_session: AsyncSession, tmp_path) -> None:
    from app.domain.errors import ValidationFailedError

    user = await CandidateService(db_session).create_user(display_name="Demo3")
    await db_session.commit()
    svc = DemoService(
        db_session,
        settings=Settings(upload_storage_dir=str(tmp_path)),
        router=_router(FakeQueue([])),
    )
    with pytest.raises(ValidationFailedError):
        await svc.setup(user.id, roles=["nonexistent-role"])
