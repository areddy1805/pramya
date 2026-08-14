"""User + candidate profile (career profile) services.

Ownership model: ``user`` owns one or more career profiles
(``candidate_profile``). Every profile-scoped operation takes an explicit
``profile_id`` and verifies it belongs to ``user_id`` server-side — a
client-supplied profile_id is never trusted on its own. The active profile
is a persisted UX preference (``user.active_profile_id``); authorization
never depends on it.
"""

from __future__ import annotations

import re

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.errors import NotFoundError, ValidationFailedError
from app.models.user import CandidateProfile, User
from app.observability import record_event
from app.repositories.user import CandidateProfileRepository, UserRepository

_DEFAULT_PROFILE_NAME = "Career Profile"


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "profile"


class CandidateService:
    """User + career profile CRUD."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.users = UserRepository(session)
        self.profiles = CandidateProfileRepository(session)

    async def create_user(
        self, *, email: str | None = None, display_name: str | None = None
    ) -> User:
        if email:
            existing = await self.users.get_by_email(email)
            if existing:
                raise ValidationFailedError(f"user with email {email} already exists")
        user = User(email=email, display_name=display_name)
        await self.users.add(user)
        return user

    async def get_user(self, user_id: int) -> User:
        return await self.users.get_or_raise(user_id, name="user")

    async def delete_user(self, user_id: int) -> None:
        user = await self.users.get_or_raise(user_id, name="user")
        await self.users.delete(user)  # FK cascade removes all owned data

    # --- profiles ------------------------------------------------------------

    async def create_profile(
        self,
        *,
        user_id: int,
        name: str | None = None,
        slug: str | None = None,
        positioning: str | None = None,
        status: str | None = None,
        seniority_target: str | None = None,
        headline: str | None = None,
        timezone: str | None = None,
    ) -> CandidateProfile:
        """Create a career profile; ensure the owning user exists.

        ``name`` defaults to 'Career Profile' (legacy callers). Duplicate
        (user_id, name) is rejected by the unique constraint.
        """
        user = await self.users.get(user_id)
        if user is None:
            await self.users.add(User(id=user_id))
        profile_name = (name or "").strip() or _DEFAULT_PROFILE_NAME
        existing = await self.profiles.get_by_name(user_id, profile_name)
        if existing:
            raise ValidationFailedError(
                f"profile named '{profile_name}' already exists for this user"
            )
        profile = CandidateProfile(
            user_id=user_id,
            name=profile_name,
            slug=(slug or "").strip() or slugify(profile_name),
            positioning=positioning,
            status=(status or "active").strip() or "active",
            seniority_target=seniority_target,
            headline=headline,
            timezone=timezone,
        )
        await self.profiles.add(profile)
        await self.profiles.flush()
        # First profile of a user becomes the active workspace by default
        # (persisted UX preference; not an authorization boundary).
        user = await self.users.get(user_id)
        if user is not None and user.active_profile_id is None:
            user.active_profile_id = profile.id
            await self.users.flush()
        record_event(
            "profile_created",
            user_id=user_id,
            profile_id=profile.id,
            profile_name=profile.name,
        )
        return profile

    async def list_profiles(self, user_id: int) -> list[CandidateProfile]:
        return await self.profiles.list_for_user(user_id)

    async def get_profile(
        self, user_id: int, profile_id: int | None = None
    ) -> CandidateProfile | None:
        """Ownership-checked profile fetch.

        ``profile_id=None`` (legacy callers) returns the active profile if
        set, else the user's first profile.
        """
        if profile_id is not None:
            profile = await self.profiles.get_for_user(user_id, profile_id)
            if profile is None:
                raise NotFoundError("candidate profile not found")
            return profile
        active_id = await self.get_active_profile_id(user_id)
        if active_id is not None:
            return await self.profiles.get_for_user(user_id, active_id)
        return await self.profiles.get_by_user(user_id)

    async def require_profile(self, user_id: int, profile_id: int | None) -> CandidateProfile:
        profile = await self.get_profile(user_id, profile_id)
        if profile is None:
            raise NotFoundError("candidate profile not found")
        return profile

    async def update_profile(
        self, user_id: int, profile_id: int | None = None, **fields: object
    ) -> CandidateProfile:
        profile = await self.require_profile(user_id, profile_id)
        for key, value in fields.items():
            if value is not None:
                setattr(profile, key, value)
        await self.profiles.flush()
        record_event(
            "profile_updated",
            user_id=user_id,
            profile_id=profile.id,
            updated=list(fields),
        )
        return profile

    async def delete_profile(self, user_id: int, profile_id: int) -> None:
        profile = await self.require_profile(user_id, profile_id)
        # The active preference must not dangle after deletion.
        user = await self.users.get(user_id)
        if user is not None and user.active_profile_id == profile.id:
            user.active_profile_id = None
        await self.profiles.delete(profile)  # FK cascade removes owned data
        record_event("profile_deleted", user_id=user_id, profile_id=profile.id)

    # --- active profile (persisted UX preference) ----------------------------

    async def get_active_profile_id(self, user_id: int) -> int | None:
        user = await self.users.get(user_id)
        if user is None:
            return None
        if user.active_profile_id is None:
            return None
        # Never trust a stale pointer: it must still belong to the user.
        profile = await self.profiles.get_for_user(user_id, user.active_profile_id)
        return profile.id if profile is not None else None

    async def set_active_profile(self, user_id: int, profile_id: int) -> CandidateProfile:
        profile = await self.require_profile(user_id, profile_id)
        user = await self.users.get(user_id)
        if user is None:
            await self.users.add(User(id=user_id))
        else:
            user.active_profile_id = profile.id
        await self.users.flush()
        record_event(
            "profile_switched",
            user_id=user_id,
            profile_id=profile.id,
            profile_name=profile.name,
        )
        return profile


# Back-compat alias (user CRUD lives in the same service).
UserService = CandidateService
