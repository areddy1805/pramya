"""API v1 routers: candidates, documents, evidence."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_session
from app.domain.enums import DocumentKind, EvidenceStatus
from app.domain.errors import NotFoundError
from app.services.document import DocumentService
from app.services.evidence import EvidenceService
from app.services.user import CandidateService

SessionDep = Annotated[AsyncSession, Depends(get_session)]
UploadFileDep = Annotated[UploadFile, File()]

router = APIRouter()


# --- Schemas -----------------------------------------------------------------


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str | None = None
    display_name: str | None = None


class CandidateProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    seniority_target: str | None = None
    headline: str | None = None
    timezone: str | None = None
    created_at: datetime


class CandidateProfileCreate(BaseModel):
    user_id: int
    seniority_target: str | None = None
    headline: str | None = None
    timezone: str | None = None


class CandidateProfileUpdate(BaseModel):
    seniority_target: str | None = None
    headline: str | None = None
    timezone: str | None = None


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    kind: DocumentKind
    filename: str
    mime: str
    size: int
    content_hash: str
    status: str
    parsed_at: datetime | None = None
    created_at: datetime


class EvidenceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    source_kind: str
    source_ref: str | None = None
    claim: str
    status: EvidenceStatus
    competency_id: int | None = None
    strength: float | None = None
    notes: str | None = None
    created_at: datetime


class EvidencePatch(BaseModel):
    status: EvidenceStatus | None = None
    strength: float | None = Field(default=None, ge=0, le=1)
    notes: str | None = None


# --- Endpoints ----------------------------------------------------------------


@router.get("/candidates/{user_id}", response_model=CandidateProfileOut)
async def get_candidate(user_id: int, session: SessionDep) -> CandidateProfileOut:
    svc = CandidateService(session)
    profile = await svc.get_profile(user_id)
    if profile is None:
        raise NotFoundError("candidate profile not found")
    return CandidateProfileOut.model_validate(profile)


@router.post("/candidates", response_model=CandidateProfileOut, status_code=201)
async def create_candidate(
    body: CandidateProfileCreate, session: SessionDep
) -> CandidateProfileOut:
    svc = CandidateService(session)
    profile = await svc.create_profile(
        user_id=body.user_id,
        seniority_target=body.seniority_target,
        headline=body.headline,
        timezone=body.timezone,
    )
    return CandidateProfileOut.model_validate(profile)


@router.patch("/candidates/{user_id}", response_model=CandidateProfileOut)
async def update_candidate(
    user_id: int,
    body: CandidateProfileUpdate,
    session: SessionDep,
) -> CandidateProfileOut:
    svc = CandidateService(session)
    profile = await svc.update_profile(
        user_id,
        seniority_target=body.seniority_target,
        headline=body.headline,
        timezone=body.timezone,
    )
    return CandidateProfileOut.model_validate(profile)


@router.delete("/candidates/{user_id}", status_code=204)
async def delete_candidate(user_id: int, session: SessionDep) -> None:
    svc = CandidateService(session)
    await svc.delete_user(user_id)  # cascades to all owned data


@router.get("/documents", response_model=list[DocumentOut])
async def list_documents(
    session: SessionDep,
    user_id: int = Query(...),
    kind: DocumentKind | None = None,
) -> list[DocumentOut]:
    settings = get_settings()
    svc = DocumentService(session, max_size_mb=settings.upload_max_mb)
    docs = await svc.list_documents(user_id, kind=kind)
    return [DocumentOut.model_validate(d) for d in docs]


@router.post("/documents", response_model=DocumentOut, status_code=201)
async def upload_document(
    session: SessionDep,
    user_id: Annotated[int, Form()],
    kind: Annotated[DocumentKind, Form()],
    file: UploadFileDep,
) -> DocumentOut:
    settings = get_settings()
    svc = DocumentService(session, max_size_mb=settings.upload_max_mb)
    data = await file.read()
    doc = await svc.upload(
        user_id=user_id,
        kind=kind,
        filename=file.filename or "unnamed",
        mime=file.content_type or "application/octet-stream",
        data=data,
    )
    return DocumentOut.model_validate(doc)


@router.get("/documents/{document_id}", response_model=DocumentOut)
async def get_document(
    session: SessionDep,
    document_id: int,
    user_id: int = Query(...),
) -> DocumentOut:
    settings = get_settings()
    svc = DocumentService(session, max_size_mb=settings.upload_max_mb)
    doc = await svc.get_document(user_id, document_id)
    return DocumentOut.model_validate(doc)


@router.delete("/documents/{document_id}", status_code=204)
async def delete_document(
    session: SessionDep,
    document_id: int,
    user_id: int = Query(...),
) -> None:
    settings = get_settings()
    svc = DocumentService(session, max_size_mb=settings.upload_max_mb)
    await svc.delete_document(user_id, document_id)


@router.get("/candidates/{user_id}/evidence", response_model=list[EvidenceOut])
async def list_evidence(
    session: SessionDep,
    user_id: int,
    competency_id: int | None = None,
    status: EvidenceStatus | None = None,
) -> list[EvidenceOut]:
    svc = EvidenceService(session)
    items = await svc.list_evidence(user_id, competency_id=competency_id, status=status)
    return [EvidenceOut.model_validate(i) for i in items]


@router.patch("/candidates/{user_id}/evidence/{evidence_id}", response_model=EvidenceOut)
async def patch_evidence(
    session: SessionDep,
    user_id: int,
    evidence_id: int,
    body: EvidencePatch,
) -> EvidenceOut:
    svc = EvidenceService(session)
    item = await svc.patch(
        user_id, evidence_id, status=body.status, strength=body.strength, notes=body.notes
    )
    return EvidenceOut.model_validate(item)
