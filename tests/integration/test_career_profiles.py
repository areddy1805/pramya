"""Career profile service tests: multi-profile CRUD, ownership, active profile."""

from __future__ import annotations

import pytest

from app.domain.errors import NotFoundError, ValidationFailedError
from app.services.user import CandidateService, slugify


@pytest.mark.asyncio
async def test_create_multiple_profiles_per_user(session_factory: object) -> None:
    async with session_factory() as session:  # type: ignore[attr-defined]
        svc = CandidateService(session)
        user = await svc.create_user(email="multi@test.local")
        await session.commit()

        p1 = await svc.create_profile(user_id=user.id, name="AI Engineer")
        p2 = await svc.create_profile(user_id=user.id, name="Forward Deployed Engineer")
        await session.commit()

        assert p1.id != p2.id
        profiles = await svc.list_profiles(user.id)
        assert [p.name for p in profiles] == ["AI Engineer", "Forward Deployed Engineer"]
        await session.rollback()


@pytest.mark.asyncio
async def test_duplicate_profile_name_rejected(session_factory: object) -> None:
    async with session_factory() as session:  # type: ignore[attr-defined]
        svc = CandidateService(session)
        user = await svc.create_user(email="dup@test.local")
        await session.commit()
        await svc.create_profile(user_id=user.id, name="AI Engineer")
        with pytest.raises(ValidationFailedError):
            await svc.create_profile(user_id=user.id, name="AI Engineer")
        await session.rollback()


@pytest.mark.asyncio
async def test_first_profile_becomes_active(session_factory: object) -> None:
    async with session_factory() as session:  # type: ignore[attr-defined]
        svc = CandidateService(session)
        user = await svc.create_user(email="active@test.local")
        await session.commit()
        p1 = await svc.create_profile(user_id=user.id, name="Alpha")
        await session.commit()
        active_id = await svc.get_active_profile_id(user.id)
        assert active_id == p1.id

        # Creating a second profile does NOT steal active status.
        p2 = await svc.create_profile(user_id=user.id, name="Beta")
        await session.commit()
        active_id = await svc.get_active_profile_id(user.id)
        assert active_id == p1.id
        assert p2.id != p1.id
        await session.rollback()


@pytest.mark.asyncio
async def test_switch_active_profile_persists(session_factory: object) -> None:
    async with session_factory() as session:  # type: ignore[attr-defined]
        svc = CandidateService(session)
        user = await svc.create_user(email="switch@test.local")
        await session.commit()
        await svc.create_profile(user_id=user.id, name="Alpha")
        p2 = await svc.create_profile(user_id=user.id, name="Beta")
        await session.commit()
        switched = await svc.set_active_profile(user.id, p2.id)
        assert switched.id == p2.id
        assert await svc.get_active_profile_id(user.id) == p2.id
        await session.rollback()


@pytest.mark.asyncio
async def test_profile_ownership_cross_user(session_factory: object) -> None:
    async with session_factory() as session:  # type: ignore[attr-defined]
        svc = CandidateService(session)
        user_a = await svc.create_user(email="a@test.local")
        user_b = await svc.create_user(email="b@test.local")
        await session.commit()
        p_a = await svc.create_profile(user_id=user_a.id, name="A's profile")
        await session.commit()

        # user_b cannot read, update, or delete user_a's profile.
        with pytest.raises(NotFoundError):
            await svc.require_profile(user_b.id, p_a.id)
        with pytest.raises(NotFoundError):
            await svc.get_profile(user_b.id, p_a.id)
        with pytest.raises(NotFoundError):
            await svc.update_profile(user_b.id, p_a.id, name="stolen")
        with pytest.raises(NotFoundError):
            await svc.delete_profile(user_b.id, p_a.id)
        with pytest.raises(NotFoundError):
            await svc.set_active_profile(user_b.id, p_a.id)
        await session.rollback()


@pytest.mark.asyncio
async def test_delete_profile_cascades_and_clears_active(session_factory: object) -> None:
    async with session_factory() as session:  # type: ignore[attr-defined]
        svc = CandidateService(session)
        user = await svc.create_user(email="del@test.local")
        await session.commit()
        p1 = await svc.create_profile(user_id=user.id, name="Alpha")
        await svc.create_profile(user_id=user.id, name="Beta")
        await session.commit()
        await svc.set_active_profile(user.id, p1.id)
        await session.commit()

        await svc.delete_profile(user.id, p1.id)
        await session.commit()

        # Active preference must not dangle.
        assert await svc.get_active_profile_id(user.id) is None
        remaining = await svc.list_profiles(user.id)
        assert [p.name for p in remaining] == ["Beta"]
        await session.rollback()


@pytest.mark.asyncio
async def test_legacy_get_profile_falls_back_to_active_then_first(session_factory: object) -> None:
    async with session_factory() as session:  # type: ignore[attr-defined]
        svc = CandidateService(session)
        user = await svc.create_user(email="legacy@test.local")
        await session.commit()
        p1 = await svc.create_profile(user_id=user.id, name="Alpha")
        p2 = await svc.create_profile(user_id=user.id, name="Beta")
        await session.commit()

        # No active set yet -> active was set to first profile on create.
        got = await svc.get_profile(user.id)
        assert got is not None and got.id == p1.id

        await svc.set_active_profile(user.id, p2.id)
        got = await svc.get_profile(user.id)
        assert got is not None and got.id == p2.id
        await session.rollback()


def test_slugify() -> None:
    assert slugify("AI Engineer") == "ai-engineer"
    assert slugify("Forward Deployed Engineer") == "forward-deployed-engineer"
    assert slugify("!!!") == "profile"
    assert slugify("  Senior Backend  ") == "senior-backend"


@pytest.mark.asyncio
async def test_default_profile_name_for_legacy_callers(session_factory: object) -> None:
    async with session_factory() as session:  # type: ignore[attr-defined]
        svc = CandidateService(session)
        user = await svc.create_user(email="default@test.local")
        await session.commit()
        profile = await svc.create_profile(user_id=user.id)
        assert profile.name == "Career Profile"
        assert profile.slug == "career-profile"
        assert profile.status == "active"
        await session.rollback()
