"""Demo mode API (Phase J).

POST /api/v1/demo/setup — idempotently populate demo data for a user
(profile, resumes, indexing, extraction, roles, readiness, preparation).
GET  /api/v1/demo/roles — list the demo role keys available.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.services.demo import DEMO_ROLE_KEYS, DemoService

router = APIRouter()

SessionDep = Annotated[AsyncSession, Depends(get_session)]


class DemoRoleOut(BaseModel):
    key: str
    document_id: int | None = None
    role_id: int | None = None
    chunks: int = 0
    evidence_count: int = 0
    competencies: int = 0


class DemoSetupOut(BaseModel):
    user_id: int
    profile: str
    roles: list[DemoRoleOut] = Field(default_factory=lambda: [])
    readiness: float = 0.0
    critical_gaps: int = 0
    preparation_items: int = 0


@router.get("/demo/roles", response_model=list[str])
async def demo_roles() -> list[str]:
    return DEMO_ROLE_KEYS


@router.post("/demo/setup", response_model=DemoSetupOut)
async def demo_setup(
    session: SessionDep,
    user_id: int = Query(default=1),
    roles: str | None = Query(default=None, description="comma-separated role keys; default all"),
) -> DemoSetupOut:
    service = DemoService(session)
    result = await service.setup(
        user_id,
        roles=[r.strip() for r in roles.split(",") if r.strip()] if roles else None,
    )
    return DemoSetupOut(
        user_id=result.user_id,
        profile=result.profile,
        roles=[DemoRoleOut(**r.__dict__) for r in result.roles],
        readiness=result.readiness,
        critical_gaps=result.critical_gaps,
        preparation_items=result.preparation_items,
    )
