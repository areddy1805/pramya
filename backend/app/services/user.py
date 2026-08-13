"""User + candidate profile services (base CRUD)."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.errors import NotFoundError, ValidationFailedError
from app.models.user import CandidateProfile, User
from app.repositories.user import CandidateProfileRepository, UserRepository


class CandidateService:
    """User + candidate profile CRUD (task 1.4)."""

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

    async def create_profile(
        self,
        *,
        user_id: int,
        seniority_target: str | None = None,
        headline: str | None = None,
        timezone: str | None = None,
    ) -> CandidateProfile:
        """Create the candidate profile; ensure the owning user exists.

        Single-user local default (plan §19): first-run profile creation
        also creates the user row so a fresh install can bootstrap via the
        UI without a separate user-creation step.
        """
        user = await self.users.get(user_id)
        if user is None:
            await self.users.add(User(id=user_id))
        existing = await self.profiles.get_by_user(user_id)
        if existing:
            raise ValidationFailedError("candidate profile already exists for this user")
        profile = CandidateProfile(
            user_id=user_id,
            seniority_target=seniority_target,
            headline=headline,
            timezone=timezone,
        )
        await self.profiles.add(profile)
        return profile

    async def get_profile(self, user_id: int) -> CandidateProfile | None:
        return await self.profiles.get_by_user(user_id)

    async def update_profile(self, user_id: int, **fields: object) -> CandidateProfile:
        profile = await self.profiles.get_by_user(user_id)
        if profile is None:
            raise NotFoundError("candidate profile not found")
        for key, value in fields.items():
            if value is not None:
                setattr(profile, key, value)
        await self.profiles.flush()
        return profile


# Back-compat alias (user CRUD lives in the same service).
UserService = CandidateService
