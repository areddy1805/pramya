"""API v1 routers: candidates, documents, evidence."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.factory import build_inference_router
from app.core.config import get_settings
from app.core.db import get_session
from app.domain.enums import DocumentKind, EvidenceStatus
from app.domain.errors import NotFoundError, ValidationFailedError
from app.knowledge.ingestion import IngestionService
from app.knowledge.parsing import parse_document_with_timeout
from app.repositories.document import DocumentChunkRepository
from app.services.document import DocumentService
from app.services.evidence import EvidenceService
from app.services.extraction import ResumeExtractionRunner
from app.services.role import RoleAnalysisService
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
    profile_id: int | None = None
    kind: DocumentKind
    filename: str
    mime: str
    size: int
    content_hash: str
    status: str
    parsed_at: datetime | None = None
    created_at: datetime


class DocumentUploadOut(BaseModel):
    """Idempotent upload result: created or deduplicated."""

    status: str  # "created" | "deduplicated"
    created: bool
    document_id: int
    profile_id: int | None = None
    processing_status: str
    kind: DocumentKind
    filename: str


class DocumentUploadIn(BaseModel):
    user_id: int
    profile_id: int | None = None
    kind: DocumentKind


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
    await session.commit()
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
    await session.commit()
    return CandidateProfileOut.model_validate(profile)


@router.delete("/candidates/{user_id}", status_code=204)
async def delete_candidate(user_id: int, session: SessionDep) -> None:
    svc = CandidateService(session)
    await svc.delete_user(user_id)  # cascades to all owned data
    await session.commit()


@router.get("/documents", response_model=list[DocumentOut])
async def list_documents(
    session: SessionDep,
    user_id: int = Query(...),
    profile_id: int | None = None,
    kind: DocumentKind | None = None,
) -> list[DocumentOut]:
    settings = get_settings()
    svc = DocumentService(session, max_size_mb=settings.upload_max_mb)
    docs = await svc.list_documents(user_id, kind=kind, profile_id=profile_id)
    return [DocumentOut.model_validate(d) for d in docs]


@router.post("/documents", response_model=DocumentUploadOut, status_code=201)
async def upload_document(
    session: SessionDep,
    response: Response,
    user_id: Annotated[int, Form()],
    kind: Annotated[DocumentKind, Form()],
    file: UploadFileDep,
    profile_id: Annotated[int | None, Form()] = None,
) -> DocumentUploadOut:
    """Upload a document. Identical content within the same
    (user, profile) is deduplicated: a 200 with status='deduplicated'
    identifying the existing document, never a generic failure."""
    settings = get_settings()
    svc = DocumentService(
        session,
        storage_dir=Path(settings.upload_storage_dir),
        max_size_mb=settings.upload_max_mb,
        max_pages=settings.document_max_pages,
        parse_timeout_seconds=settings.document_parse_timeout_seconds,
    )
    data = await file.read()
    try:
        doc, _parsed = await svc.upload(
            user_id=user_id,
            profile_id=profile_id,
            kind=kind,
            filename=file.filename or "unnamed",
            mime=file.content_type or "application/octet-stream",
            data=data,
        )
        await session.commit()
        return DocumentUploadOut(
            status="created",
            created=True,
            document_id=doc.id,
            profile_id=doc.profile_id,
            processing_status=str(doc.status),
            kind=doc.kind,
            filename=doc.filename,
        )
    except ValidationFailedError as exc:
        details = exc.details or {}
        existing_id = details.get("document_id")
        if existing_id is not None:
            # Idempotent dedup: return the existing document as a normal
            # application state, not an unexplained failure. 200 (not 201:
            # nothing was created).
            response.status_code = 200
            existing = await svc.get_document(user_id, int(existing_id), profile_id=profile_id)
            return DocumentUploadOut(
                status="deduplicated",
                created=False,
                document_id=existing.id,
                profile_id=existing.profile_id,
                processing_status=str(existing.status),
                kind=existing.kind,
                filename=existing.filename,
            )
        raise


@router.get("/documents/{document_id}", response_model=DocumentOut)
async def get_document(
    session: SessionDep,
    document_id: int,
    user_id: int = Query(...),
    profile_id: int | None = None,
) -> DocumentOut:
    settings = get_settings()
    svc = DocumentService(session, max_size_mb=settings.upload_max_mb)
    doc = await svc.get_document(user_id, document_id, profile_id=profile_id)
    return DocumentOut.model_validate(doc)


@router.delete("/documents/{document_id}", status_code=204)
async def delete_document(
    session: SessionDep,
    document_id: int,
    user_id: int = Query(...),
    profile_id: int | None = None,
) -> None:
    settings = get_settings()
    svc = DocumentService(session, max_size_mb=settings.upload_max_mb)
    await svc.delete_document(user_id, document_id, profile_id=profile_id)
    await session.commit()


class DocumentIndexOut(BaseModel):
    document_id: int
    chunk_count: int
    dimension: int = 0


@router.post("/documents/{document_id}/index", response_model=DocumentIndexOut)
async def index_document(
    session: SessionDep,
    document_id: int,
    user_id: int = Query(...),
    profile_id: int | None = None,
) -> DocumentIndexOut:
    """Chunk + embed + persist a parsed document (idempotent re-index)."""
    settings = get_settings()
    doc_svc = DocumentService(
        session,
        storage_dir=Path(settings.upload_storage_dir),
        max_size_mb=settings.upload_max_mb,
        max_pages=settings.document_max_pages,
        parse_timeout_seconds=settings.document_parse_timeout_seconds,
    )
    doc = await doc_svc.get_document(user_id, document_id, profile_id=profile_id)
    data = await doc_svc.read_stored_bytes(user_id, document_id, profile_id=profile_id)
    parsed = await parse_document_with_timeout(
        data=data,
        kind=doc.kind,
        mime=doc.mime,
        filename=doc.filename,
        content_hash=doc.content_hash,
        max_pages=settings.document_max_pages,
        timeout_seconds=settings.document_parse_timeout_seconds,
    )
    router = build_inference_router(settings)
    # Phase D: production ingestion executes the LlamaIndex pipeline
    # (RouterEmbeddings -> PramyaVectorStore); deterministic IngestionService
    # stays as the reference/fallback layer.
    try:
        from app.knowledge.rag.service import LlamaIndexIngestionService

        rag_ingestion = LlamaIndexIngestionService(
            session,
            router,
            chunk_size=settings.knowledge_chunk_size,
            chunk_overlap=settings.knowledge_chunk_overlap,
        )
        count = await rag_ingestion.index_document(doc, parsed.content)
        if count:
            await session.commit()
            chunks = await DocumentChunkRepository(session).list_for_document(document_id)
            dimension = len(chunks[0].embedding) if chunks and chunks[0].embedding else 0
            return DocumentIndexOut(document_id=doc.id, chunk_count=count, dimension=dimension)
    except Exception as exc:
        # Degrade to the deterministic ingestion path (reference layer).
        logging.getLogger(__name__).warning(
            "llamaindex ingestion degraded to deterministic path: %s", exc
        )
    ingestion = IngestionService(
        session,
        router,
        chunk_size=settings.knowledge_chunk_size,
        chunk_overlap=settings.knowledge_chunk_overlap,
        embed_batch_size=settings.knowledge_embed_batch_size,
    )
    rows = await ingestion.index_document(doc, parsed.content)
    dimension = len(rows[0].embedding) if rows and rows[0].embedding else 0
    return DocumentIndexOut(document_id=doc.id, chunk_count=len(rows), dimension=dimension)


@router.get("/candidates/{user_id}/evidence", response_model=list[EvidenceOut])
async def list_evidence(
    session: SessionDep,
    user_id: int,
    profile_id: int | None = None,
    competency_id: int | None = None,
    status: EvidenceStatus | None = None,
) -> list[EvidenceOut]:
    svc = EvidenceService(session)
    items = await svc.list_evidence(
        user_id, competency_id=competency_id, status=status, profile_id=profile_id
    )
    return [EvidenceOut.model_validate(i) for i in items]


@router.patch("/candidates/{user_id}/evidence/{evidence_id}", response_model=EvidenceOut)
async def patch_evidence(
    session: SessionDep,
    user_id: int,
    evidence_id: int,
    body: EvidencePatch,
    profile_id: int | None = None,
) -> EvidenceOut:
    svc = EvidenceService(session)
    item = await svc.patch(
        user_id,
        evidence_id,
        status=body.status,
        strength=body.strength,
        notes=body.notes,
        profile_id=profile_id,
    )
    await session.commit()
    return EvidenceOut.model_validate(item)


# --- Roles (Phase 2.5) -------------------------------------------------------


class CompetencyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    category: str
    level: int
    importance: str
    weight: float
    importance_rank: int


class RoleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    title: str
    seniority: str | None = None
    summary: str | None = None
    created_at: datetime


class RoleDetailOut(RoleOut):
    competencies: list[CompetencyOut] = Field(default_factory=lambda: [])


class RoleAnalyzeIn(BaseModel):
    user_id: int
    profile_id: int | None = None
    jd_text: str = Field(min_length=20, max_length=100_000)
    source_document_id: int | None = None


@router.post("/roles/analyze", response_model=RoleDetailOut, status_code=201)
async def analyze_role(
    body: RoleAnalyzeIn,
    session: SessionDep,
) -> RoleDetailOut:
    settings = get_settings()
    router = build_inference_router(settings)
    svc = RoleAnalysisService(session, router)
    role = await svc.analyze(
        body.user_id,
        body.jd_text,
        source_document_id=body.source_document_id,
        profile_id=body.profile_id,
    )
    competencies = await svc.roles.list_competencies(role.id)
    await session.commit()
    # Build manually: model_validate(role) would lazy-load the competencies
    # relationship outside the async greenlet (MissingGreenlet).
    detail = RoleDetailOut(
        id=role.id,
        user_id=role.user_id,
        title=role.title,
        seniority=role.seniority,
        summary=role.summary,
        created_at=role.created_at,
    )
    detail.competencies = [CompetencyOut.model_validate(c) for c in competencies]
    return detail


@router.get("/roles/{role_id}", response_model=RoleDetailOut)
async def get_role(
    role_id: int,
    session: SessionDep,
    user_id: int = Query(...),
    profile_id: int | None = None,
) -> RoleDetailOut:
    settings = get_settings()
    router = build_inference_router(settings)
    svc = RoleAnalysisService(session, router)
    role = await svc.roles.get_or_raise(role_id, name="role")
    if role.user_id != user_id:
        raise NotFoundError("role not found")
    if profile_id is not None and role.profile_id != profile_id:
        raise NotFoundError("role not found")
    competencies = await svc.roles.list_competencies(role.id)
    detail = RoleDetailOut(
        id=role.id,
        user_id=role.user_id,
        title=role.title,
        seniority=role.seniority,
        summary=role.summary,
        created_at=role.created_at,
    )
    detail.competencies = [CompetencyOut.model_validate(c) for c in competencies]
    return detail


@router.get("/roles", response_model=list[RoleOut])
async def list_roles(
    session: SessionDep,
    user_id: int = Query(...),
    profile_id: int | None = None,
) -> list[RoleOut]:
    settings = get_settings()
    router = build_inference_router(settings)
    svc = RoleAnalysisService(session, router)
    if profile_id is not None:
        # Ownership check: the profile must belong to the user before its
        # roles are readable (never trust a client-supplied profile_id).
        profile = await svc.profiles.get_for_user(user_id, profile_id)
        if profile is None:
            raise NotFoundError("candidate profile not found")
        roles = await svc.roles.list_for_profile(profile_id)
    else:
        roles = await svc.roles.list_for_user(user_id)
    return [RoleOut.model_validate(r) for r in roles]


# --- Candidate extraction (Phase 2.4) ----------------------------------------


class ExtractionOut(BaseModel):
    extraction: dict[str, object]
    evidence_count: int


@router.post("/candidates/{user_id}/extract", response_model=ExtractionOut)
async def extract_candidate(
    session: SessionDep,
    user_id: int,
    document_id: int = Query(...),
    profile_id: int | None = None,
) -> ExtractionOut:
    settings = get_settings()
    router = build_inference_router(settings)
    if profile_id is not None:
        # Ownership check before attributing evidence to a profile.
        svc = CandidateService(session)
        await svc.require_profile(user_id, profile_id)
    runner = ResumeExtractionRunner(session, router, storage_dir=Path(settings.upload_storage_dir))
    extraction, count = await runner.extract_document(user_id, document_id, profile_id=profile_id)
    await session.commit()
    return ExtractionOut(
        extraction=extraction.model_dump(),
        evidence_count=count,
    )
