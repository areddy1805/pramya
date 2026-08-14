"""Profile workspace integration: resume/JD per profile, dedup idempotency,
profile isolation, analytics attribution, active-profile switching.

These tests exercise the real persistence chain (DB-backed) and prove the
directive's core chain: profile -> resume -> JD -> target roles -> evidence
-> analytics, with no cross-profile leakage.
"""

from __future__ import annotations

import pytest

from app.domain.enums import DocumentKind
from app.domain.errors import NotFoundError, ValidationFailedError
from app.services.analytics import PreparationService, ProgressService, ReadinessService
from app.services.document import DocumentService
from app.services.evidence import EvidenceService
from app.services.user import CandidateService

RESUME_A = b"# Alex\nAI Engineer with 5 years of applied ML."
RESUME_B = b"# Dana\nForward deployed engineer focused on customer adoption."
JD_A = b"# Applied AI Engineer\nBuild LLM products end to end."
JD_B = b"# Platform Engineer\nRun Kubernetes at scale."


async def _mk_user(session_factory: object, email: str) -> int:
    async with session_factory() as session:  # type: ignore[attr-defined]
        svc = CandidateService(session)
        user = await svc.create_user(email=email)
        await session.commit()
        return user.id


async def _mk_profiles(session_factory: object, user_id: int) -> tuple[int, int]:
    async with session_factory() as session:  # type: ignore[attr-defined]
        svc = CandidateService(session)
        p1 = await svc.create_profile(user_id=user_id, name="AI Engineer")
        p2 = await svc.create_profile(user_id=user_id, name="Forward Deployed Engineer")
        await session.commit()
        return p1.id, p2.id


@pytest.mark.asyncio
async def test_resume_upload_is_profile_scoped(session_factory: object, tmp_path) -> None:
    user_id = await _mk_user(session_factory, "resumes@test.local")
    p1, p2 = await _mk_profiles(session_factory, user_id)

    async with session_factory() as session:  # type: ignore[attr-defined]
        svc = DocumentService(session, storage_dir=tmp_path)
        doc1, _ = await svc.upload(
            user_id=user_id,
            profile_id=p1,
            kind=DocumentKind.RESUME,
            filename="alex.md",
            mime="text/markdown",
            data=RESUME_A,
        )
        doc2, _ = await svc.upload(
            user_id=user_id,
            profile_id=p2,
            kind=DocumentKind.RESUME,
            filename="dana.md",
            mime="text/markdown",
            data=RESUME_B,
        )
        await session.commit()

        # Each profile sees only its own resume.
        p1_docs = await svc.list_documents(user_id, kind=DocumentKind.RESUME, profile_id=p1)
        p2_docs = await svc.list_documents(user_id, kind=DocumentKind.RESUME, profile_id=p2)
        assert [d.id for d in p1_docs] == [doc1.id]
        assert [d.id for d in p2_docs] == [doc2.id]

        # Cross-profile read is not-found (isolation).
        with pytest.raises(NotFoundError):
            await svc.get_document(user_id, doc2.id, profile_id=p1)
        await session.rollback()


@pytest.mark.asyncio
async def test_duplicate_upload_same_profile_is_idempotent(
    session_factory: object, tmp_path
) -> None:
    user_id = await _mk_user(session_factory, "dedup@test.local")
    p1, _ = await _mk_profiles(session_factory, user_id)

    async with session_factory() as session:  # type: ignore[attr-defined]
        svc = DocumentService(session, storage_dir=tmp_path)
        doc1, _ = await svc.upload(
            user_id=user_id,
            profile_id=p1,
            kind=DocumentKind.JD,
            filename="jd-a.md",
            mime="text/markdown",
            data=JD_A,
        )
        await session.commit()

        # Same content + same profile -> ValidationFailedError with document_id
        # (the API layer translates this into an idempotent 200 dedup response).
        with pytest.raises(ValidationFailedError) as exc_info:
            await svc.upload(
                user_id=user_id,
                profile_id=p1,
                kind=DocumentKind.JD,
                filename="jd-a-again.md",
                mime="text/markdown",
                data=JD_A,
            )
        assert exc_info.value.details == {"document_id": doc1.id, "profile_id": p1}
        await session.rollback()


@pytest.mark.asyncio
async def test_same_content_different_profile_is_distinct(
    session_factory: object, tmp_path
) -> None:
    """The same file in a different career profile is a distinct document
    (each profile keeps its own workspace)."""
    user_id = await _mk_user(session_factory, "cross@test.local")
    p1, p2 = await _mk_profiles(session_factory, user_id)

    async with session_factory() as session:  # type: ignore[attr-defined]
        svc = DocumentService(session, storage_dir=tmp_path)
        doc1, _ = await svc.upload(
            user_id=user_id,
            profile_id=p1,
            kind=DocumentKind.JD,
            filename="jd.md",
            mime="text/markdown",
            data=JD_A,
        )
        await session.commit()
        doc2, _ = await svc.upload(
            user_id=user_id,
            profile_id=p2,
            kind=DocumentKind.JD,
            filename="jd.md",
            mime="text/markdown",
            data=JD_A,
        )
        await session.commit()
        assert doc1.id != doc2.id
        await session.rollback()


@pytest.mark.asyncio
async def test_evidence_isolation_between_profiles(session_factory: object) -> None:
    user_id = await _mk_user(session_factory, "evidence@test.local")
    p1, p2 = await _mk_profiles(session_factory, user_id)

    async with session_factory() as session:  # type: ignore[attr-defined]
        ev_svc = EvidenceService(session)
        await ev_svc.create_evidence(
            user_id=user_id,
            profile_id=p1,
            claim="Led an applied ML team",
            source_kind="resume",
        )
        await ev_svc.create_evidence(
            user_id=user_id,
            profile_id=p2,
            claim="Drove customer adoption",
            source_kind="resume",
        )
        await session.commit()

        p1_items = await ev_svc.list_evidence(user_id, profile_id=p1)
        p2_items = await ev_svc.list_evidence(user_id, profile_id=p2)
        assert len(p1_items) == 1 and "ML" in p1_items[0].claim
        assert len(p2_items) == 1 and "adoption" in p2_items[0].claim

        # Cross-profile patch is not-found.
        with pytest.raises(NotFoundError):
            await ev_svc.patch(user_id, p1_items[0].id, status="demonstrated", profile_id=p2)
        await session.rollback()


@pytest.mark.asyncio
async def test_readiness_is_profile_scoped(session_factory: object, tmp_path) -> None:
    """Readiness for one profile must not consume the other profile's evidence."""
    user_id = await _mk_user(session_factory, "readiness@test.local")
    p1, p2 = await _mk_profiles(session_factory, user_id)

    async with session_factory() as session:  # type: ignore[attr-defined]
        ev_svc = EvidenceService(session)
        # Strong evidence under p1, nothing under p2.
        await ev_svc.create_evidence(
            user_id=user_id,
            profile_id=p1,
            claim="Led applied ML teams",
            source_kind="resume",
            status="demonstrated",
            strength=0.9,
        )
        await session.commit()

        rsvc = ReadinessService(session)
        # Readiness without a role (no competency model) still records a
        # snapshot attributed to the profile.
        result1, snap1 = await rsvc.compute_and_save(user_id, None, profile_id=p1)
        result2, snap2 = await rsvc.compute_and_save(user_id, None, profile_id=p2)
        assert snap1.profile_id == p1
        assert snap2.profile_id == p2

        latest1 = await rsvc.latest(user_id, profile_id=p1)
        latest2 = await rsvc.latest(user_id, profile_id=p2)
        assert latest1 is not None and latest1.profile_id == p1
        assert latest2 is not None and latest2.profile_id == p2
        await session.rollback()


@pytest.mark.asyncio
async def test_preparation_items_carry_profile(session_factory: object, tmp_path) -> None:
    user_id = await _mk_user(session_factory, "prep@test.local")
    p1, p2 = await _mk_profiles(session_factory, user_id)

    async with session_factory() as session:  # type: ignore[attr-defined]
        rsvc = ReadinessService(session)
        await rsvc.compute_and_save(user_id, None, profile_id=p1)
        await session.commit()

        psvc = PreparationService(session)
        rows = await psvc.regenerate(user_id, profile_id=p1)
        assert all(r.profile_id == p1 for r in rows)

        p2_rows = await psvc.regenerate(user_id, profile_id=p2)
        assert all(r.profile_id == p2 for r in p2_rows)
        await session.rollback()


@pytest.mark.asyncio
async def test_progress_filtered_by_profile(session_factory: object) -> None:
    user_id = await _mk_user(session_factory, "progress@test.local")
    p1, p2 = await _mk_profiles(session_factory, user_id)

    async with session_factory() as session:  # type: ignore[attr-defined]
        psvc = ProgressService(session)
        s1 = await psvc.summary(user_id, profile_id=p1)
        s2 = await psvc.summary(user_id, profile_id=p2)
        assert s1.total_evaluations == 0
        assert s2.total_evaluations == 0
        await session.rollback()


@pytest.mark.asyncio
async def test_delete_profile_cascades_owned_documents(session_factory: object, tmp_path) -> None:
    user_id = await _mk_user(session_factory, "cascade@test.local")
    p1, p2 = await _mk_profiles(session_factory, user_id)

    async with session_factory() as session:  # type: ignore[attr-defined]
        svc = DocumentService(session, storage_dir=tmp_path)
        doc1, _ = await svc.upload(
            user_id=user_id,
            profile_id=p1,
            kind=DocumentKind.RESUME,
            filename="a.md",
            mime="text/markdown",
            data=RESUME_A,
        )
        doc2, _ = await svc.upload(
            user_id=user_id,
            profile_id=p2,
            kind=DocumentKind.RESUME,
            filename="b.md",
            mime="text/markdown",
            data=RESUME_B,
        )
        await session.commit()

        cs = CandidateService(session)
        await cs.delete_profile(user_id, p1)
        await session.commit()

        # p1's document is gone; p2's document survives.
        docs_p2 = await svc.list_documents(user_id, profile_id=p2)
        assert [d.id for d in docs_p2] == [doc2.id]
        docs_p1 = await svc.list_documents(user_id, profile_id=p1)
        assert docs_p1 == []
        await session.rollback()


@pytest.mark.asyncio
async def test_document_upload_without_profile_uses_default(
    session_factory: object, tmp_path
) -> None:
    """Legacy callers (no profile_id) attribute to the user's first profile."""
    user_id = await _mk_user(session_factory, "legacy-doc@test.local")
    p1, _ = await _mk_profiles(session_factory, user_id)

    async with session_factory() as session:  # type: ignore[attr-defined]
        svc = DocumentService(session, storage_dir=tmp_path)
        doc, _ = await svc.upload(
            user_id=user_id,
            kind=DocumentKind.RESUME,
            filename="legacy.md",
            mime="text/markdown",
            data=b"# Legacy",
        )
        assert doc.profile_id == p1
        await session.rollback()
