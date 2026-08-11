"""User + candidate profile repositories."""

from __future__ import annotations

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
        stmt = select(CandidateProfile).where(CandidateProfile.user_id == user_id)
        return (await self.session.scalars(stmt)).first()
