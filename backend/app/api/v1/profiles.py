"""Career profile routes: multi-profile CRUD + active profile.

Ownership model: every profile operation takes an explicit profile_id and
verifies it belongs to the caller's user_id (server-side). The active
profile is a persisted UX preference (user.active_profile_id); it is never
an authorization boundary.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, cast

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.domain.enums import DocumentKind
from app.repositories.misc import RoleRepository
from app.services.interview_context import InterviewContextBuilder
from app.services.user import CandidateService

SessionDep = Annotated[AsyncSession, Depends(get_session)]

router = APIRouter()


class ProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    name: str
    slug: str | None = None
    positioning: str | None = None
    status: str
    seniority_target: str | None = None
    headline: str | None = None
    timezone: str | None = None
    preferred_resume_document_id: int | None = None
    preferred_jd_document_id: int | None = None
    created_at: datetime
    updated_at: datetime | None = None


class ProfileCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    slug: str | None = Field(default=None, max_length=200)
    positioning: str | None = None
    status: str | None = Field(default="active", max_length=32)
    seniority_target: str | None = Field(default=None, max_length=100)
    headline: str | None = Field(default=None, max_length=300)
    timezone: str | None = Field(default=None, max_length=64)


class ProfileUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    slug: str | None = Field(default=None, max_length=200)
    positioning: str | None = None
    status: str | None = Field(default=None, max_length=32)
    seniority_target: str | None = Field(default=None, max_length=100)
    headline: str | None = Field(default=None, max_length=300)
    timezone: str | None = Field(default=None, max_length=64)


class ActiveProfileOut(BaseModel):
    profile_id: int | None = None
    profile: ProfileOut | None = None


class ActiveProfileSet(BaseModel):
    profile_id: int


class PreferredDocumentSet(BaseModel):
    """Select a profile-owned document as the preferred/current one.
    ``document_id=None`` clears the preference."""

    document_id: int | None = None


def _out(profile: object) -> ProfileOut:
    return ProfileOut.model_validate(profile)


@router.get("/candidates/{user_id}/profiles", response_model=list[ProfileOut])
async def list_profiles(user_id: int, session: SessionDep) -> list[ProfileOut]:
    svc = CandidateService(session)
    profiles = await svc.list_profiles(user_id)
    return [_out(p) for p in profiles]


@router.post("/candidates/{user_id}/profiles", response_model=ProfileOut, status_code=201)
async def create_profile(user_id: int, body: ProfileCreate, session: SessionDep) -> ProfileOut:
    svc = CandidateService(session)
    profile = await svc.create_profile(
        user_id=user_id,
        name=body.name,
        slug=body.slug,
        positioning=body.positioning,
        status=body.status,
        seniority_target=body.seniority_target,
        headline=body.headline,
        timezone=body.timezone,
    )
    await session.commit()
    return _out(profile)


@router.get("/candidates/{user_id}/profiles/{profile_id}", response_model=ProfileOut)
async def get_profile(user_id: int, profile_id: int, session: SessionDep) -> ProfileOut:
    svc = CandidateService(session)
    profile = await svc.require_profile(user_id, profile_id)
    return _out(profile)


@router.patch("/candidates/{user_id}/profiles/{profile_id}", response_model=ProfileOut)
async def update_profile(
    user_id: int, profile_id: int, body: ProfileUpdate, session: SessionDep
) -> ProfileOut:
    svc = CandidateService(session)
    profile = await svc.update_profile(
        user_id,
        profile_id,
        name=body.name,
        slug=body.slug,
        positioning=body.positioning,
        status=body.status,
        seniority_target=body.seniority_target,
        headline=body.headline,
        timezone=body.timezone,
    )
    await session.commit()
    return _out(profile)


@router.delete("/candidates/{user_id}/profiles/{profile_id}", status_code=204)
async def delete_profile(user_id: int, profile_id: int, session: SessionDep) -> None:
    svc = CandidateService(session)
    await svc.delete_profile(user_id, profile_id)
    await session.commit()


class InterviewContextOut(BaseModel):
    """Server-authoritative resolved interview context (same builder + snapshot
    the interview engine uses — never a frontend re-interpretation)."""

    profile_id: int
    profile: dict[str, object] | None = None
    resume: dict[str, object] | None = None
    jd: dict[str, object] | None = None
    target_roles: list[dict[str, object]] = []
    grounding: dict[str, bool]
    evidence_count: int = 0
    missing: list[str] = []


@router.get(
    "/candidates/{user_id}/profiles/{profile_id}/context",
    response_model=InterviewContextOut,
)
async def get_profile_interview_context(
    user_id: int, profile_id: int, session: SessionDep
) -> InterviewContextOut:
    svc = CandidateService(session)
    await svc.require_profile(user_id, profile_id)
    builder = InterviewContextBuilder(session)
    snapshot = await builder.build(user_id=user_id, profile_id=profile_id, role_id=None)
    roles = await RoleRepository(session).list_for_profile(profile_id)
    profile = cast("dict[str, object] | None", snapshot.get("profile"))
    resume = cast("dict[str, object] | None", snapshot.get("resume"))
    jd = cast("dict[str, object] | None", snapshot.get("jd"))
    evidence = cast("list[dict[str, object]]", snapshot.get("evidence") or [])
    missing = cast("list[str]", snapshot.get("missing") or [])
    return InterviewContextOut(
        profile_id=profile_id,
        profile=profile,
        resume=resume,
        jd=jd,
        target_roles=cast(
            "list[dict[str, object]]",
            [{"id": r.id, "title": r.title} for r in roles],
        ),
        grounding={
            "profile": profile is not None,
            "resume": isinstance(resume, dict) and bool(resume.get("ready")),
            "jd": isinstance(jd, dict) and bool(jd.get("ready")),
            "evidence": bool(evidence),
        },
        evidence_count=len(evidence),
        missing=missing,
    )


@router.put(
    "/candidates/{user_id}/profiles/{profile_id}/preferred-resume", response_model=ProfileOut
)
async def set_preferred_resume(
    user_id: int, profile_id: int, body: PreferredDocumentSet, session: SessionDep
) -> ProfileOut:
    svc = CandidateService(session)
    profile = await svc.set_preferred_document(
        user_id, profile_id, kind=DocumentKind.RESUME, document_id=body.document_id
    )
    await session.commit()
    return _out(profile)


@router.put("/candidates/{user_id}/profiles/{profile_id}/preferred-jd", response_model=ProfileOut)
async def set_preferred_jd(
    user_id: int, profile_id: int, body: PreferredDocumentSet, session: SessionDep
) -> ProfileOut:
    svc = CandidateService(session)
    profile = await svc.set_preferred_document(
        user_id, profile_id, kind=DocumentKind.JD, document_id=body.document_id
    )
    await session.commit()
    return _out(profile)


@router.get("/candidates/{user_id}/active-profile", response_model=ActiveProfileOut)
async def get_active_profile(user_id: int, session: SessionDep) -> ActiveProfileOut:
    svc = CandidateService(session)
    active_id = await svc.get_active_profile_id(user_id)
    profile = await svc.get_profile(user_id, active_id) if active_id is not None else None
    if profile is None:
        return ActiveProfileOut(profile_id=None, profile=None)
    return ActiveProfileOut(profile_id=profile.id, profile=_out(profile))


@router.put("/candidates/{user_id}/active-profile", response_model=ActiveProfileOut)
async def set_active_profile(
    user_id: int, body: ActiveProfileSet, session: SessionDep
) -> ActiveProfileOut:
    svc = CandidateService(session)
    profile = await svc.set_active_profile(user_id, body.profile_id)
    await session.commit()
    return ActiveProfileOut(profile_id=profile.id, profile=_out(profile))
