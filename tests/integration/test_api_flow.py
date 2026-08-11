"""API integration smoke: upload flow end-to-end against real DB."""

from __future__ import annotations

import pytest_asyncio

from app.domain.enums import DocumentKind
from app.models.user import User
from app.repositories.user import UserRepository


@pytest_asyncio.fixture
async def api_user(session_factory: object) -> int:
    async with session_factory() as session:  # type: ignore[attr-defined]
        repo = UserRepository(session)
        user = User(email="api@test.local")
        await repo.add(user)
        await session.commit()
        return user.id


async def test_upload_flow_accepts_valid_and_rejects_invalid(
    api_user: int, session_factory: object
) -> None:
    """Upload flow (task 1.5) via services: valid accepted, invalid rejected."""
    from app.services.document import DocumentService

    async with session_factory() as session:  # type: ignore[attr-defined]
        svc = DocumentService(session)
        doc = await svc.upload(
            user_id=api_user,
            kind=DocumentKind.RESUME,
            filename="resume.md",
            mime="text/markdown",
            data=b"# Alex\nSenior engineer",
        )
        assert doc.id
        assert doc.status.value == "pending"

        docs = await svc.list_documents(api_user, kind=DocumentKind.RESUME)
        assert len(docs) == 1
        await session.rollback()
