"""Live interview context integrity tests: no cross-profile fallback, no
silent profile inference, fail-fast incomplete grounding, SSE provenance,
and context-parity between the Practice-screen endpoint and the session
snapshot the engine actually uses.

LLM calls are faked via a seeded QueueProvider — fully deterministic.
Real Postgres + pgvector via the shared integration fixtures.
"""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.contracts import ChatResponse, Usage
from app.ai.policy import TaskPolicyTable
from app.ai.router import InferenceRouter
from app.api.v1.profiles import get_profile_interview_context
from app.domain.enums import (
    CompetencyCategory,
    CompetencyImportance,
    DocumentKind,
    DocumentStatus,
    EvidenceSourceKind,
    EvidenceStatus,
    InterviewKind,
)
from app.domain.errors import ValidationFailedError
from app.interview.service import InterviewService, event_bus
from app.models.document import Document, DocumentChunk
from app.models.evidence import Evidence
from app.models.role import Competency, Role
from app.repositories.document import DocumentRepository
from app.repositories.user import CandidateProfileRepository
from app.services.analytics import ReadinessService
from app.services.interview_context import InterviewContextBuilder
from app.services.user import CandidateService

QUESTION_TEXT = (
    "QUESTION: Walk me through the Atlas analytics platform.\n"
    "CATEGORY: architecture_design\n"
    "SOURCE: resume\n"
    "SOURCE_REF: Atlas — RAG knowledge platform\n"
    "DIFFICULTY: medium\n"
    "TYPE: project_deep_dive\n"
    "RATIONALE: probes grounding\n"
    "TARGET: System Design\n"
    "HINTS:\n- h"
)

RESUME_A = "Alex — built Atlas, a RAG platform. Angular, Node.js, MongoDB, AWS."
RESUME_B = "Dana — led Northwind rollout 2 to 40 teams. Python, FastAPI, runbooks."
JD_A = "Senior AI Engineer — LLM applications, prompt engineering, evaluation."
JD_B = "Forward Deployed Engineer — customer integrations, rollout at scale."


class QueueProvider:
    name = "fake"

    def __init__(self, contents: list[str]) -> None:
        self.contents = contents
        self.calls: list[object] = []

    async def generate(self, request: object) -> ChatResponse:
        self.calls.append(request)
        content = self.contents.pop(0) if self.contents else "{}"
        return ChatResponse(content=content, model="fake", usage=Usage(total_tokens=1))


def _router(provider: QueueProvider) -> InferenceRouter:
    return InferenceRouter(policy=TaskPolicyTable(), omlx=None, deepseek=provider)


async def _svc(db: AsyncSession, contents: list[str]) -> tuple[InterviewService, QueueProvider]:
    provider = QueueProvider(contents)
    return InterviewService(db, _router(provider)), provider


async def seed_user(db: AsyncSession, *, email: str | None = None) -> int:
    import uuid

    svc = CandidateService(db)
    user = await svc.create_user(
        email=email or f"ctx-{uuid.uuid4().hex[:10]}@test.local", display_name="User"
    )
    await db.commit()
    return user.id


async def seed_profile(db: AsyncSession, user_id: int, name: str) -> int:
    svc = CandidateService(db)
    profile = await svc.create_profile(user_id=user_id, name=name, positioning="Applied")
    await db.commit()
    return profile.id


async def seed_doc(
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
        content_hash=f"hash-{kind.value}-{filename}",
        status=DocumentStatus.PARSED,
    )
    db.add(doc)
    await db.flush()
    db.add(DocumentChunk(document_id=doc.id, chunk_index=0, content=text.strip()))
    await db.commit()
    return doc.id


# ---------------------------------------------------------------------------
# 1. Resume resolution is STRICTLY profile-scoped
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_resume_is_strictly_profile_scoped(session_factory: object) -> None:
    async with session_factory() as db:  # type: ignore[attr-defined]
        user_id = await seed_user(db)
        pa = await seed_profile(db, user_id, "Profile A")
        pb = await seed_profile(db, user_id, "Profile B")
        doc_a = await seed_doc(
            db,
            user_id=user_id,
            profile_id=pa,
            kind=DocumentKind.RESUME,
            filename="a-resume.md",
            text=RESUME_A,
        )
        await seed_doc(
            db,
            user_id=user_id,
            profile_id=pb,
            kind=DocumentKind.RESUME,
            filename="b-resume.md",
            text=RESUME_B,
        )

        builder = InterviewContextBuilder(db)
        ctx_a = await builder.build(user_id=user_id, profile_id=pa, role_id=None)
        ctx_b = await builder.build(user_id=user_id, profile_id=pb, role_id=None)

        resume_a = ctx_a["resume"]
        assert isinstance(resume_a, dict)
        assert resume_a["document_id"] == doc_a
        assert resume_a["filename"] == "a-resume.md"
        assert "Atlas" in str(resume_a["text"])
        assert "Northwind" not in str(resume_a["text"])

        resume_b = ctx_b["resume"]
        assert isinstance(resume_b, dict)
        assert resume_b["filename"] == "b-resume.md"
        assert "Northwind" in str(resume_b["text"])
        assert "Atlas" not in str(resume_b["text"])
        await db.rollback()


# ---------------------------------------------------------------------------
# 2/3. No silent substitution from another profile
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_profile_without_resume_never_picks_other_profiles_resume(
    session_factory: object,
) -> None:
    async with session_factory() as db:  # type: ignore[attr-defined]
        user_id = await seed_user(db)
        pa = await seed_profile(db, user_id, "Profile A")
        pb = await seed_profile(db, user_id, "Profile B")
        await seed_doc(
            db,
            user_id=user_id,
            profile_id=pa,
            kind=DocumentKind.RESUME,
            filename="a-resume.md",
            text=RESUME_A,
        )
        # Profile B has NO resume — but profile A does (same user).
        builder = InterviewContextBuilder(db)
        ctx_b = await builder.build(user_id=user_id, profile_id=pb, role_id=None)
        assert ctx_b["resume"] is None
        assert "resume" in ctx_b["missing"]
        await db.rollback()


@pytest.mark.asyncio
async def test_profile_without_jd_does_not_pick_other_profiles_jd(session_factory: object) -> None:
    async with session_factory() as db:  # type: ignore[attr-defined]
        user_id = await seed_user(db)
        pa = await seed_profile(db, user_id, "Profile A")
        pb = await seed_profile(db, user_id, "Profile B")
        await seed_doc(
            db,
            user_id=user_id,
            profile_id=pa,
            kind=DocumentKind.RESUME,
            filename="a-resume.md",
            text=RESUME_A,
        )
        await seed_doc(
            db, user_id=user_id, profile_id=pa, kind=DocumentKind.JD, filename="a-jd.md", text=JD_A
        )
        await seed_doc(
            db,
            user_id=user_id,
            profile_id=pb,
            kind=DocumentKind.RESUME,
            filename="b-resume.md",
            text=RESUME_B,
        )
        # Profile B has a resume but no JD; profile A's JD must NOT leak in.
        builder = InterviewContextBuilder(db)
        ctx_b = await builder.build(user_id=user_id, profile_id=pb, role_id=None)
        assert ctx_b["jd"] is None
        assert ctx_b["resume"] is not None
        await db.rollback()


@pytest.mark.asyncio
async def test_legacy_global_docs_are_explicit_profile_id_null_only(
    session_factory: object,
) -> None:
    """Legacy/global documents (profile_id IS NULL) are usable, but never a
    document owned by another profile."""
    async with session_factory() as db:  # type: ignore[attr-defined]
        user_id = await seed_user(db)
        pa = await seed_profile(db, user_id, "Profile A")
        pb = await seed_profile(db, user_id, "Profile B")
        await seed_doc(
            db,
            user_id=user_id,
            profile_id=pa,
            kind=DocumentKind.RESUME,
            filename="a-resume.md",
            text=RESUME_A,
        )
        global_doc = Document(
            user_id=user_id,
            profile_id=None,
            kind=DocumentKind.RESUME,
            filename="legacy-global.md",
            mime="text/markdown",
            size=len("Legacy global resume"),
            content_hash="hash-legacy-global",
            status=DocumentStatus.PARSED,
        )
        db.add(global_doc)
        await db.flush()
        db.add(
            DocumentChunk(document_id=global_doc.id, chunk_index=0, content="Legacy global resume")
        )
        await db.commit()

        builder = InterviewContextBuilder(db)
        ctx_pb = await builder.build(user_id=user_id, profile_id=pb, role_id=None)
        # B has no own resume but a legacy global row exists -> global is used,
        # profile A's resume is NOT.
        resume_b = ctx_pb["resume"]
        assert isinstance(resume_b, dict)
        assert resume_b["filename"] == "legacy-global.md"
        assert "Atlas" not in str(resume_b["text"])
        await db.rollback()


# ---------------------------------------------------------------------------
# 4/5/8. profile_id=None: resolve active profile, never first/seed profile
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_session_without_profile_id_raises_when_no_active_profile(
    session_factory: object,
) -> None:
    async with session_factory() as db:  # type: ignore[attr-defined]
        # No profiles at all -> nothing to resolve -> must fail loudly.
        user_id = await seed_user(db)
        svc = InterviewService(db, _router(QueueProvider([])))
        with pytest.raises(ValidationFailedError) as exc:
            await svc.create_session(
                user_id=user_id,
                kind=InterviewKind.GENERAL,
                role_id=None,
                duration_minutes=30,
                focus_competency_ids=[],
                profile_id=None,
            )
        assert "Interview profile is required" in str(exc.value)
        await db.rollback()

        # Profiles exist but the active pointer was cleared (e.g. the active
        # profile was deleted): must NOT silently pick another profile.
        user2 = await seed_user(db, email="cleared@test.local")
        pa = await seed_profile(db, user2, "A")
        await seed_profile(db, user2, "B")
        svc2 = CandidateService(db)
        await svc2.set_active_profile(user2, pa)
        await db.commit()
        await svc2.delete_profile(user2, pa)
        await db.commit()
        svc3 = InterviewService(db, _router(QueueProvider([])))
        with pytest.raises(ValidationFailedError) as exc2:
            await svc3.create_session(
                user_id=user2,
                kind=InterviewKind.GENERAL,
                role_id=None,
                duration_minutes=30,
                focus_competency_ids=[],
                profile_id=None,
            )
        assert "Interview profile is required" in str(exc2.value)
        await db.rollback()


@pytest.mark.asyncio
async def test_create_session_resolves_active_profile_not_first_seed(
    session_factory: object,
) -> None:
    """The FIRST profile (a seed/demo profile) must never be silently chosen:
    the persisted active profile is authoritative."""
    async with session_factory() as db:  # type: ignore[attr-defined]
        user_id = await seed_user(db)
        first = await seed_profile(db, user_id, "Seed Profile")
        second = await seed_profile(db, user_id, "Real Profile")
        await seed_doc(
            db,
            user_id=user_id,
            profile_id=second,
            kind=DocumentKind.RESUME,
            filename="real-resume.md",
            text=RESUME_B,
        )
        svc = CandidateService(db)
        await svc.set_active_profile(user_id, second)
        await db.commit()

        provider = QueueProvider([QUESTION_TEXT])
        svc = InterviewService(db, _router(provider))
        session = await svc.create_session(
            user_id=user_id,
            kind=InterviewKind.GENERAL,
            role_id=None,
            duration_minutes=30,
            focus_competency_ids=[],
            profile_id=None,  # must resolve to the ACTIVE profile, not `first`
        )
        assert session.candidate_profile_id == second
        assert session.candidate_profile_id != first
        await db.rollback()


# ---------------------------------------------------------------------------
# 6. Session persists the exact selected profile
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_session_persists_exact_profile_id(session_factory: object) -> None:
    async with session_factory() as db:  # type: ignore[attr-defined]
        user_id = await seed_user(db)
        pa = await seed_profile(db, user_id, "Profile A")
        await seed_doc(
            db,
            user_id=user_id,
            profile_id=pa,
            kind=DocumentKind.RESUME,
            filename="a-resume.md",
            text=RESUME_A,
        )
        provider = QueueProvider([QUESTION_TEXT])
        svc = InterviewService(db, _router(provider))
        session = await svc.create_session(
            user_id=user_id,
            kind=InterviewKind.GENERAL,
            role_id=None,
            duration_minutes=30,
            focus_competency_ids=[],
            profile_id=pa,
        )
        assert session.candidate_profile_id == pa
        await db.rollback()


# ---------------------------------------------------------------------------
# 6/7. Context endpoint parity + fail-fast + SSE provenance
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_context_endpoint_matches_session_snapshot(session_factory: object) -> None:
    async with session_factory() as db:  # type: ignore[attr-defined]
        user_id = await seed_user(db)
        pa = await seed_profile(db, user_id, "Profile A")
        doc_a = await seed_doc(
            db,
            user_id=user_id,
            profile_id=pa,
            kind=DocumentKind.RESUME,
            filename="a-resume.md",
            text=RESUME_A,
        )
        jd_a = await seed_doc(
            db, user_id=user_id, profile_id=pa, kind=DocumentKind.JD, filename="a-jd.md", text=JD_A
        )

        provider = QueueProvider([QUESTION_TEXT])
        svc = InterviewService(db, _router(provider))
        session = await svc.create_session(
            user_id=user_id,
            kind=InterviewKind.GENERAL,
            role_id=None,
            duration_minutes=30,
            focus_competency_ids=[],
            profile_id=pa,
        )
        await svc.begin(session.id, user_id)
        session_cfg = session.config or {}
        ctx_snapshot = session_cfg["context"]
        assert isinstance(ctx_snapshot, dict)

        # Practice-screen endpoint derives from the SAME builder.
        endpoint = await get_profile_interview_context(user_id, pa, db)
        assert endpoint.profile_id == pa
        assert endpoint.resume is not None and endpoint.resume["document_id"] == doc_a
        assert endpoint.jd is not None and endpoint.jd["document_id"] == jd_a
        assert endpoint.grounding["resume"] is True
        assert endpoint.grounding["jd"] is True
        assert endpoint.grounding["profile"] is True

        # Parity: endpoint == session snapshot (same document ids).
        snap_resume = ctx_snapshot["resume"]
        assert isinstance(snap_resume, dict)
        assert snap_resume["document_id"] == doc_a
        assert snap_resume["document_id"] == endpoint.resume["document_id"]
        snap_jd = ctx_snapshot["jd"]
        assert isinstance(snap_jd, dict)
        assert snap_jd["document_id"] == endpoint.jd["document_id"]
        await db.rollback()


@pytest.mark.asyncio
async def test_begin_fails_fast_when_profile_has_no_resume(session_factory: object) -> None:
    async with session_factory() as db:  # type: ignore[attr-defined]
        user_id = await seed_user(db)
        pa = await seed_profile(db, user_id, "Empty Profile")
        # another profile owns a resume — must not be used
        await seed_doc(
            db,
            user_id=user_id,
            profile_id=(await seed_profile(db, user_id, "Other")),
            kind=DocumentKind.RESUME,
            filename="other.md",
            text=RESUME_A,
        )
        provider = QueueProvider([QUESTION_TEXT])
        svc = InterviewService(db, _router(provider))
        session = await svc.create_session(
            user_id=user_id,
            kind=InterviewKind.GENERAL,
            role_id=None,
            duration_minutes=30,
            focus_competency_ids=[],
            profile_id=pa,
        )
        with pytest.raises(ValidationFailedError) as exc:
            await svc.begin(session.id, user_id)
        assert "no processed resume" in str(exc.value)
        assert session.config is None or "context" not in (session.config or {})
        await db.rollback()


@pytest.mark.asyncio
async def test_jd_interview_mode_requires_jd(session_factory: object) -> None:
    async with session_factory() as db:  # type: ignore[attr-defined]
        user_id = await seed_user(db)
        pa = await seed_profile(db, user_id, "Resume-Only Profile")
        await seed_doc(
            db,
            user_id=user_id,
            profile_id=pa,
            kind=DocumentKind.RESUME,
            filename="a-resume.md",
            text=RESUME_A,
        )
        provider = QueueProvider([QUESTION_TEXT])
        svc = InterviewService(db, _router(provider))
        session = await svc.create_session(
            user_id=user_id,
            kind=InterviewKind.JOB_DESCRIPTION,
            role_id=None,
            duration_minutes=30,
            focus_competency_ids=[],
            profile_id=pa,
        )
        with pytest.raises(ValidationFailedError) as exc:
            await svc.begin(session.id, user_id)
        assert "job description" in str(exc.value)
        # resume-only GENERAL interview on the same profile is fine
        session2 = await svc.create_session(
            user_id=user_id,
            kind=InterviewKind.GENERAL,
            role_id=None,
            duration_minutes=30,
            focus_competency_ids=[],
            profile_id=pa,
        )
        await svc.begin(session2.id, user_id)
        assert session2.status.value == "questioning"
        await db.rollback()


@pytest.mark.asyncio
async def test_sse_question_event_includes_source_ref(session_factory: object) -> None:
    async with session_factory() as db:  # type: ignore[attr-defined]
        user_id = await seed_user(db)
        pa = await seed_profile(db, user_id, "Profile A")
        await seed_doc(
            db,
            user_id=user_id,
            profile_id=pa,
            kind=DocumentKind.RESUME,
            filename="a-resume.md",
            text=RESUME_A,
        )
        provider = QueueProvider([QUESTION_TEXT])
        svc = InterviewService(db, _router(provider))
        session = await svc.create_session(
            user_id=user_id,
            kind=InterviewKind.GENERAL,
            role_id=None,
            duration_minutes=30,
            focus_competency_ids=[],
            profile_id=pa,
        )
        await svc.begin(session.id, user_id)
        queue = event_bus.subscribe(session.id)
        await svc.next_question(session.id, user_id)
        seen: list[tuple[str, dict[str, object]]] = []
        while not queue.empty():
            ev = queue.get_nowait()
            seen.append((ev.type, ev.data))
        question_events = [d for t, d in seen if t == "question"]
        assert question_events, f"no question event in {seen!r}"
        payload = question_events[0]
        assert payload.get("source") == "resume"
        assert payload.get("source_ref") == "Atlas — RAG knowledge platform"
        assert payload.get("category") == "architecture_design"
        await db.rollback()


# ---------------------------------------------------------------------------
# 9. A/B isolation remains green end-to-end
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_profile_a_and_b_fully_isolated(session_factory: object) -> None:
    async with session_factory() as db:  # type: ignore[attr-defined]
        user_id = await seed_user(db)
        pa = await seed_profile(db, user_id, "Profile A")
        pb = await seed_profile(db, user_id, "Profile B")
        await seed_doc(
            db,
            user_id=user_id,
            profile_id=pa,
            kind=DocumentKind.RESUME,
            filename="a-resume.md",
            text=RESUME_A,
        )
        await seed_doc(
            db,
            user_id=user_id,
            profile_id=pb,
            kind=DocumentKind.RESUME,
            filename="b-resume.md",
            text=RESUME_B,
        )
        await seed_doc(
            db, user_id=user_id, profile_id=pb, kind=DocumentKind.JD, filename="b-jd.md", text=JD_B
        )
        db.add(
            Evidence(
                user_id=user_id,
                profile_id=pb,
                source_kind=EvidenceSourceKind.RESUME,
                source_ref="document:1",
                claim="Technology: KafkaStreams",
                status=EvidenceStatus.CLAIMED,
            )
        )
        await db.commit()

        # Endpoint for B: only B's material.
        endpoint_b = await get_profile_interview_context(user_id, pb, db)
        assert endpoint_b.resume is not None and endpoint_b.resume["filename"] == "b-resume.md"
        assert endpoint_b.jd is not None and endpoint_b.jd["filename"] == "b-jd.md"
        assert "Atlas" not in (endpoint_b.resume or {}).get("filename", "")
        assert endpoint_b.evidence_count == 1

        # Builder snapshot for B never contains A's resume text.
        builder = InterviewContextBuilder(db)
        ctx_b = await builder.build(user_id=user_id, profile_id=pb, role_id=None)
        resume_b = ctx_b["resume"]
        assert isinstance(resume_b, dict)
        assert "Northwind" in str(resume_b["text"])
        assert "Atlas" not in str(resume_b["text"])
        await db.rollback()


@pytest.mark.asyncio
async def test_context_builder_rejects_foreign_profile(session_factory: object) -> None:
    """A profile owned by ANOTHER user never resolves into this user's context."""
    async with session_factory() as db:  # type: ignore[attr-defined]
        user_a = await seed_user(db, email="owner-a@test.local")
        user_b = await seed_user(db, email="owner-b@test.local")
        pa = await seed_profile(db, user_a, "A's Profile")
        await seed_doc(
            db,
            user_id=user_a,
            profile_id=pa,
            kind=DocumentKind.RESUME,
            filename="a-resume.md",
            text=RESUME_A,
        )
        builder = InterviewContextBuilder(db)
        # user B asking for A's profile: ownership-checked -> profile None.
        ctx = await builder.build(user_id=user_b, profile_id=pa, role_id=None)
        assert ctx["profile"] is None
        assert "profile" in ctx["missing"]
        await db.rollback()


# ---------------------------------------------------------------------------
# Preferred/current document selection (workspace document management)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_preferred_resume_wins_over_latest(session_factory: object) -> None:
    """Explicit persisted preference beats latest-uploaded."""
    async with session_factory() as db:  # type: ignore[attr-defined]
        user_id = await seed_user(db)
        pa = await seed_profile(db, user_id, "Profile A")
        older = await seed_doc(
            db,
            user_id=user_id,
            profile_id=pa,
            kind=DocumentKind.RESUME,
            filename="older.md",
            text=RESUME_A,
        )
        newer = await seed_doc(
            db,
            user_id=user_id,
            profile_id=pa,
            kind=DocumentKind.RESUME,
            filename="newer.md",
            text=RESUME_B,
        )
        svc = CandidateService(db)
        await svc.set_preferred_document(user_id, pa, kind=DocumentKind.RESUME, document_id=older)
        await db.commit()

        builder = InterviewContextBuilder(db)
        ctx = await builder.build(user_id=user_id, profile_id=pa, role_id=None)
        resume = ctx["resume"]
        assert isinstance(resume, dict)
        assert resume["document_id"] == older
        assert resume["document_id"] != newer  # latest-uploaded is NOT chosen

        # Context endpoint parity: same preferred document.
        endpoint = await get_profile_interview_context(user_id, pa, db)
        assert endpoint.resume is not None and endpoint.resume["document_id"] == older
        await db.rollback()


@pytest.mark.asyncio
async def test_preferred_jd_selection_and_clear(session_factory: object) -> None:
    async with session_factory() as db:  # type: ignore[attr-defined]
        user_id = await seed_user(db)
        pa = await seed_profile(db, user_id, "Profile A")
        await seed_doc(
            db,
            user_id=user_id,
            profile_id=pa,
            kind=DocumentKind.RESUME,
            filename="r.md",
            text=RESUME_A,
        )
        jd1 = await seed_doc(
            db, user_id=user_id, profile_id=pa, kind=DocumentKind.JD, filename="jd1.md", text=JD_A
        )
        # Second (never) JD: exists so the explicit preference for jd1 beats
        # the latest-by-id fallback.
        await seed_doc(
            db, user_id=user_id, profile_id=pa, kind=DocumentKind.JD, filename="jd2.md", text=JD_B
        )
        svc = CandidateService(db)
        # select the OLDER jd explicitly
        await svc.set_preferred_document(user_id, pa, kind=DocumentKind.JD, document_id=jd1)
        await db.commit()
        builder = InterviewContextBuilder(db)
        ctx = await builder.build(user_id=user_id, profile_id=pa, role_id=None)
        jd = ctx["jd"]
        assert isinstance(jd, dict) and jd["document_id"] == jd1

        # clear -> resume-only mode (JD optional)
        await svc.set_preferred_document(user_id, pa, kind=DocumentKind.JD, document_id=None)
        await db.commit()
        ctx2 = await builder.build(user_id=user_id, profile_id=pa, role_id=None)
        assert ctx2["jd"] is not None  # falls back to latest parsed JD
        await db.rollback()


@pytest.mark.asyncio
async def test_preferred_document_cross_profile_rejected(session_factory: object) -> None:
    async with session_factory() as db:  # type: ignore[attr-defined]
        user_id = await seed_user(db)
        pa = await seed_profile(db, user_id, "Profile A")
        pb = await seed_profile(db, user_id, "Profile B")
        doc_b = await seed_doc(
            db,
            user_id=user_id,
            profile_id=pb,
            kind=DocumentKind.RESUME,
            filename="b.md",
            text=RESUME_B,
        )
        svc = CandidateService(db)
        with pytest.raises(ValidationFailedError):
            await svc.set_preferred_document(
                user_id, pa, kind=DocumentKind.RESUME, document_id=doc_b
            )
        await db.rollback()


@pytest.mark.asyncio
async def test_historical_snapshot_immutable_after_preference_change(
    session_factory: object,
) -> None:
    """Changing the preferred resume later NEVER mutates an existing session's
    grounding snapshot."""
    async with session_factory() as db:  # type: ignore[attr-defined]
        user_id = await seed_user(db)
        pa = await seed_profile(db, user_id, "Profile A")
        r1 = await seed_doc(
            db,
            user_id=user_id,
            profile_id=pa,
            kind=DocumentKind.RESUME,
            filename="r1.md",
            text=RESUME_A,
        )
        r2 = await seed_doc(
            db,
            user_id=user_id,
            profile_id=pa,
            kind=DocumentKind.RESUME,
            filename="r2.md",
            text=RESUME_B,
        )
        provider = QueueProvider([QUESTION_TEXT])
        svc = InterviewService(db, _router(provider))
        session = await svc.create_session(
            user_id=user_id,
            kind=InterviewKind.GENERAL,
            role_id=None,
            duration_minutes=30,
            focus_competency_ids=[],
            profile_id=pa,
        )
        await svc.begin(session.id, user_id)
        snap = (session.config or {})["context"]["resume"]
        assert snap["document_id"] == r2  # latest at start time (no preference)

        # user later switches preference to r1 -> old session unchanged
        svc_prof = CandidateService(db)
        await svc_prof.set_preferred_document(user_id, pa, kind=DocumentKind.RESUME, document_id=r1)
        await db.commit()
        assert (session.config or {})["context"]["resume"]["document_id"] == r2

        # a NEW session uses the new preference
        session2 = await svc.create_session(
            user_id=user_id,
            kind=InterviewKind.GENERAL,
            role_id=None,
            duration_minutes=30,
            focus_competency_ids=[],
            profile_id=pa,
        )
        await svc.begin(session2.id, user_id)
        snap2 = (session2.config or {})["context"]["resume"]
        assert snap2["document_id"] == r1
        await db.rollback()


@pytest.mark.asyncio
async def test_deleted_preferred_document_clears_pointer_and_keeps_history(
    session_factory: object,
) -> None:
    async with session_factory() as db:  # type: ignore[attr-defined]
        user_id = await seed_user(db)
        pa = await seed_profile(db, user_id, "Profile A")
        r1 = await seed_doc(
            db,
            user_id=user_id,
            profile_id=pa,
            kind=DocumentKind.RESUME,
            filename="r1.md",
            text=RESUME_A,
        )
        await seed_doc(
            db,
            user_id=user_id,
            profile_id=pa,
            kind=DocumentKind.RESUME,
            filename="r2.md",
            text=RESUME_B,
        )
        svc = CandidateService(db)
        await svc.set_preferred_document(user_id, pa, kind=DocumentKind.RESUME, document_id=r1)
        await db.commit()
        provider = QueueProvider([QUESTION_TEXT])
        isvc = InterviewService(db, _router(provider))
        session = await isvc.create_session(
            user_id=user_id,
            kind=InterviewKind.GENERAL,
            role_id=None,
            duration_minutes=30,
            focus_competency_ids=[],
            profile_id=pa,
        )
        await isvc.begin(session.id, user_id)
        snap = (session.config or {})["context"]["resume"]
        assert snap["document_id"] == r1

        # delete the preferred document -> pointer cleared by FK SET NULL
        doc = await DocumentRepository(db).get(r1)
        assert doc is not None
        from app.services.document import DocumentService

        await DocumentService(db).delete_document(user_id, r1, profile_id=pa)
        await db.commit()
        profile = await CandidateProfileRepository(db).get(pa)
        assert profile is not None and profile.preferred_resume_document_id is None
        # old session snapshot retained (explainability)
        assert (session.config or {})["context"]["resume"]["document_id"] == r1
        # builder falls back to the remaining parsed resume
        builder = InterviewContextBuilder(db)
        ctx = await builder.build(user_id=user_id, profile_id=pa, role_id=None)
        resume = ctx["resume"]
        assert isinstance(resume, dict) and resume["document_id"] != r1
        await db.rollback()


async def seed_role(db: AsyncSession, *, user_id: int, profile_id: int, title: str) -> int:
    """Minimal persisted role (profile-scoped) with one competency."""
    role = Role(
        user_id=user_id,
        profile_id=profile_id,
        title=title,
        seniority="senior",
        summary=f"{title} target role",
    )
    db.add(role)
    await db.flush()
    db.add(
        Competency(
            role_id=role.id,
            name="System Design",
            category=CompetencyCategory.ARCHITECTURE,
            level=4,
            importance=CompetencyImportance.REQUIRED,
            importance_rank=1,
            weight=1.0,
        )
    )
    await db.flush()
    return role.id


# ---------------------------------------------------------------------------
# Role grounding ownership: a foreign profile's role must be REJECTED
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_foreign_role_rejected_in_interview_context(
    session_factory: object,
) -> None:
    """Profile A's interview must never ground on Profile B's role."""
    async with session_factory() as db:  # type: ignore[attr-defined]
        user_id = await seed_user(db)
        pa = await seed_profile(db, user_id, "Profile A")
        pb = await seed_profile(db, user_id, "Profile B")
        await seed_doc(
            db,
            user_id=user_id,
            profile_id=pa,
            kind=DocumentKind.RESUME,
            filename="a-resume.md",
            text=RESUME_A,
        )
        role_b = await seed_role(db, user_id=user_id, profile_id=pb, title="Northwind Eng")

        builder = InterviewContextBuilder(db)
        with pytest.raises(ValidationFailedError):
            await builder.build(user_id=user_id, profile_id=pa, role_id=role_b)
        await db.rollback()


@pytest.mark.asyncio
async def test_foreign_role_rejected_in_readiness(session_factory: object) -> None:
    """Readiness must not score a role the profile does not own."""
    async with session_factory() as db:  # type: ignore[attr-defined]
        user_id = await seed_user(db)
        pa = await seed_profile(db, user_id, "Profile A")
        pb = await seed_profile(db, user_id, "Profile B")
        role_b = await seed_role(db, user_id=user_id, profile_id=pb, title="Northwind Eng")

        svc = ReadinessService(db)
        with pytest.raises(ValidationFailedError):
            await svc.compute_and_save(user_id, role_b, profile_id=pa)
        await db.rollback()


# ---------------------------------------------------------------------------
# Interview session read requires ownership (GET /interviews/{id})
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_interview_requires_ownership(session_factory: object) -> None:
    """HTTP layer: a foreign user_id must get 404, the owner gets 200."""
    from httpx import ASGITransport, AsyncClient

    from app.core.db import get_session
    from app.main import create_app

    async with session_factory() as db:  # type: ignore[attr-defined]
        owner = await seed_user(db)
        stranger = await seed_user(db)
        pa = await seed_profile(db, owner, "Profile A")
        await seed_doc(
            db,
            user_id=owner,
            profile_id=pa,
            kind=DocumentKind.RESUME,
            filename="a-resume.md",
            text=RESUME_A,
        )
        svc, _ = await _svc(db, [QUESTION_TEXT])
        session = await svc.create_session(
            user_id=owner,
            kind=InterviewKind.GENERAL,
            role_id=None,
            duration_minutes=30,
            focus_competency_ids=[],
            profile_id=pa,
        )
        session_id = session.id

        async def _override() -> AsyncSession:
            async with session_factory() as s:  # type: ignore[attr-defined]
                yield s

        app = create_app()
        app.dependency_overrides[get_session] = _override
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r_stranger = await client.get(
                f"/api/v1/interviews/{session_id}", params={"user_id": stranger}
            )
            assert r_stranger.status_code == 404
            r_owner = await client.get(
                f"/api/v1/interviews/{session_id}", params={"user_id": owner}
            )
            assert r_owner.status_code == 200
        app.dependency_overrides.clear()
        await db.rollback()
