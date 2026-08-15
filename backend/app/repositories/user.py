"""User + candidate profile repositories."""

from __future__ import annotations

from sqlalchemy import func as sa_func
from sqlalchemy import select

from app.models.user import CandidateProfile, User
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    model = User

    async def get_by_email(self, email: str) -> User | None:
        stmt = select(User).where(User.email == email)
        return (await self.session.scalars(stmt)).first()

    async def get_with_profile(self, user_id: int) -> User | None:
        stmt = select(User).where(User.id == user_id)
        return (await self.session.scalars(stmt)).first()


class CandidateProfileRepository(BaseRepository[CandidateProfile]):
    model = CandidateProfile

    async def get_by_user(self, user_id: int) -> CandidateProfile | None:
        """Legacy single-profile lookup: the user's first profile."""
        stmt = (
            select(CandidateProfile)
            .where(CandidateProfile.user_id == user_id)
            .order_by(CandidateProfile.id)
        )
        return (await self.session.scalars(stmt)).first()

    async def list_for_user(self, user_id: int) -> list[CandidateProfile]:
        stmt = (
            select(CandidateProfile)
            .where(CandidateProfile.user_id == user_id)
            .order_by(CandidateProfile.id)
        )
        return list((await self.session.scalars(stmt)).all())

    async def get_for_user(self, user_id: int, profile_id: int) -> CandidateProfile | None:
        """Ownership-checked profile fetch: profile must belong to user."""
        stmt = select(CandidateProfile).where(
            CandidateProfile.id == profile_id, CandidateProfile.user_id == user_id
        )
        return (await self.session.scalars(stmt)).first()

    async def get_by_name(self, user_id: int, name: str) -> CandidateProfile | None:
        stmt = select(CandidateProfile).where(
            CandidateProfile.user_id == user_id, CandidateProfile.name == name
        )
        return (await self.session.scalars(stmt)).first()

    async def count_for_user(self, user_id: int) -> int:
        stmt = (
            select(sa_func.count())
            .select_from(CandidateProfile)
            .where(CandidateProfile.user_id == user_id)
        )
        return int((await self.session.scalar(stmt)) or 0)
