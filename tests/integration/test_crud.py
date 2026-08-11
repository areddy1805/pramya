"""Integration tests: repository CRUD, cascade delete, idempotency, upload flow."""

from __future__ import annotations

import uuid

import pytest

from app.domain.enums import (
    DocumentKind,
    DocumentStatus,
    EvidenceSourceKind,
    EvidenceStatus,
    InterviewKind,
    InterviewSessionStatus,
)
from app.domain.errors import DuplicateSubmissionError, NotFoundError, ValidationFailedError
from app.models.document import DocumentChunk
from app.models.evidence import Evidence
from app.models.interview import InterviewSession, Question
from app.models.role import Competency, Role
from app.models.user import User
from app.repositories.interview import InterviewSessionRepository
from app.repositories.misc import EvaluationVersionRepository
from app.repositories.user import UserRepository
from app.services.document import DocumentService, content_hash
from app.services.evidence import EvidenceService
from app.services.idempotency import IdempotencyService, make_idempotency_key
from app.services.user import CandidateService


def _email() -> str:
    return f"u{uuid.uuid4().hex[:8]}@test.local"


async def test_user_profile_crud(session_factory: object) -> None:
    async with session_factory() as session:  # type: ignore[attr-defined]
        svc = CandidateService(session)
        user = await svc.create_user(email=_email(), display_name="Alex")
        assert user.id
        profile = await svc.create_profile(user_id=user.id, seniority_target="senior")
        assert profile.id
        got = await svc.get_profile(user.id)
        assert got is not None and got.seniority_target == "senior"
        await session.commit()


async def test_profile_unique_per_user(session_factory: object) -> None:
    async with session_factory() as session:  # type: ignore[attr-defined]
        svc = CandidateService(session)
        user = await svc.create_user(email=_email())
        await svc.create_profile(user_id=user.id)
        with pytest.raises(ValidationFailedError):
            await svc.create_profile(user_id=user.id)
        await session.rollback()


async def test_document_upload_and_validation(tmp_path, session_factory: object) -> None:
    async with session_factory() as session:  # type: ignore[attr-defined]
        svc = CandidateService(session)
        user = await svc.create_user(email=_email())
        doc_svc = DocumentService(session, storage_dir=tmp_path)
        doc = await doc_svc.upload(
            user_id=user.id,
            kind=DocumentKind.RESUME,
            filename="resume.pdf",
            mime="application/pdf",
            data=b"%PDF-1.4 fake",
        )
        assert doc.status == DocumentStatus.PENDING
        assert doc.content_hash == content_hash(b"%PDF-1.4 fake")
        assert doc.storage_key is not None
        assert (tmp_path / doc.storage_key).exists()

        with pytest.raises(ValidationFailedError):
            await doc_svc.upload(
                user_id=user.id,
                kind=DocumentKind.RESUME,
                filename="evil.sh",
                mime="application/x-sh",
                data=b"#!/bin/sh",
            )
        with pytest.raises(ValidationFailedError):
            await doc_svc.upload(
                user_id=user.id,
                kind=DocumentKind.RESUME,
                filename="big.pdf",
                mime="application/pdf",
                data=b"x" * (5 * 1024 * 1024 + 1),
            )
        # duplicate content rejected
        with pytest.raises(ValidationFailedError):
            await doc_svc.upload(
                user_id=user.id,
                kind=DocumentKind.RESUME,
                filename="dup.pdf",
                mime="application/pdf",
                data=b"%PDF-1.4 fake",
            )
        await session.rollback()


async def test_evidence_patch_correction(session_factory: object) -> None:
    async with session_factory() as session:  # type: ignore[attr-defined]
        svc = CandidateService(session)
        user = await svc.create_user(email=_email())
        ev_svc = EvidenceService(session)
        item = await ev_svc.create_evidence(
            user_id=user.id, claim="led team of 5", source_kind=EvidenceSourceKind.RESUME
        )
        assert item.status == EvidenceStatus.CLAIMED
        patched = await ev_svc.patch(
            user.id, item.id, status=EvidenceStatus.DEMONSTRATED, strength=0.8
        )
        assert patched.status == EvidenceStatus.DEMONSTRATED
        assert patched.strength == 0.8
        # ownership check
        with pytest.raises(NotFoundError):
            await ev_svc.get_evidence(user.id + 999, item.id)
        await session.rollback()


async def test_idempotency_dedup(session_factory: object) -> None:
    async with session_factory() as session:  # type: ignore[attr-defined]
        svc = IdempotencyService(session)
        key = make_idempotency_key(scope="interview:1", payload={"question_id": 1})
        await svc.check_and_record(scope="interview:1", key=key, payload={"question_id": 1})
        with pytest.raises(DuplicateSubmissionError):
            await svc.check_and_record(scope="interview:1", key=key, payload={"question_id": 1})
        # same key different scope is fine
        await svc.check_and_record(scope="interview:2", key=key, payload={"question_id": 1})
        await session.rollback()


async def test_cascade_delete_user_removes_all(session_factory: object) -> None:
    async with session_factory() as session:  # type: ignore[attr-defined]
        svc = CandidateService(session)
        user = await svc.create_user(email=_email())
        profile = await svc.create_profile(user_id=user.id)

        # document + chunk
        doc_svc = DocumentService(session)
        doc = await doc_svc.upload(
            user_id=user.id,
            kind=DocumentKind.RESUME,
            filename="r.txt",
            mime="text/plain",
            data=b"hello",
        )
        session.add(DocumentChunk(document_id=doc.id, chunk_index=0, content="hello"))
        # role + competency
        role = Role(user_id=user.id, source_document_id=doc.id, title="SWE")
        session.add(role)
        await session.flush()
        session.add(
            Competency(
                role_id=role.id,
                name="Python",
                category="backend",
                level=3,
                importance="required",
                weight=0.8,
                importance_rank=1,
            )
        )
        # evidence
        ev = Evidence(
            user_id=user.id,
            source_kind=EvidenceSourceKind.RESUME,
            claim="claim",
            status=EvidenceStatus.CLAIMED,
        )
        session.add(ev)
        # interview session + question
        sess = InterviewSession(
            user_id=user.id,
            candidate_profile_id=profile.id,
            role_id=role.id,
            kind=InterviewKind.TECHNICAL,
            status=InterviewSessionStatus.CREATED,
        )
        session.add(sess)
        await session.flush()
        session.add(
            Question(interview_session_id=sess.id, difficulty="medium", type="technical", text="Q?")
        )
        await session.commit()

        await svc.delete_user(user.id)
        await session.commit()

        for table, col in [
            ("document", "user_id"),
            ("role", "user_id"),
            ("evidence", "user_id"),
            ("interview_session", "user_id"),
            ("candidate_profile", "user_id"),
        ]:
            from sqlalchemy import column, func, select
            from sqlalchemy import table as sa_table

            tbl = sa_table(table, column(col))
            stmt = select(func.count()).select_from(tbl).where(tbl.c[col] == user.id)
            n = (await session.execute(stmt)).scalar()
            assert n == 0, f"{table} not cascaded (left {n})"


async def test_repositories_roundtrip(session_factory: object) -> None:
    async with session_factory() as session:  # type: ignore[attr-defined]
        from sqlalchemy import text

        repo = UserRepository(session)
        user = User(email=_email())
        await repo.add(user)
        assert (await repo.get(user.id)) is not None

        srepo = InterviewSessionRepository(session)
        sess = InterviewSession(
            user_id=user.id, kind=InterviewKind.GENERAL, status=InterviewSessionStatus.CREATED
        )
        await srepo.add(sess)
        assert (await srepo.list_for_user(user.id))[0].id == sess.id

        evrepo = EvaluationVersionRepository(session)
        from app.models.debrief import EvaluationVersion

        ev = EvaluationVersion(name=f"v-{uuid.uuid4().hex[:8]}", version="1.0", prompt_hash="abc")
        await evrepo.add(ev)
        assert (await evrepo.get_by_name(ev.name)) is not None

        await session.commit()

        # verify committed rows are readable + cascade on user delete
        assert (
            await session.execute(
                text("SELECT count(*) FROM interview_session WHERE id=:i"), {"i": sess.id}
            )
        ).scalar() == 1
        await repo.delete(user)
        await session.commit()
        assert (
            await session.execute(
                text("SELECT count(*) FROM interview_session WHERE id=:i"), {"i": sess.id}
            )
        ).scalar() == 0
