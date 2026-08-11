"""Candidate extraction pipeline (Phase 2.4).

Resume text -> structured extraction (InferenceRouter, TaskClass.EXTRACTION,
pramya-4b local first, deepseek escalation fallback) -> evidence ledger
entries with CLAIMED status + candidate profile enrichment.

Evidence provenance rule (project principle): extraction output is the
candidate's own claims — persisted as `claimed`, never as observed/
demonstrated fact. User corrections can promote status later (2.6).
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.contracts import ChatMessage
from app.ai.policy import TaskClass
from app.ai.router import InferenceRouter
from app.ai.structured import generate_structured
from app.domain.enums import EvidenceSourceKind, EvidenceStatus
from app.domain.errors import ValidationFailedError
from app.domain.schemas import ResumeExtraction
from app.models.document import Document
from app.models.evidence import Evidence
from app.repositories.evidence import EvidenceRepository
from app.services.document import DocumentService
from app.services.prompts import load_prompt

_PROMPT = "candidate_analysis/resume_extraction.txt"
_DEFAULT_PROMPT = (
    "Extract structured facts from the candidate resume. Only what the "
    "resume states — never infer or fabricate."
)


class ExtractionService:
    """Extract candidate facts from a resume document into the evidence ledger."""

    def __init__(
        self,
        session: AsyncSession,
        router: InferenceRouter,
        *,
        prompt_path: Path | None = None,
    ) -> None:
        self.session = session
        self.router = router
        self.evidence = EvidenceRepository(session)
        self.prompt_text = (
            prompt_path.read_text()
            if prompt_path is not None and prompt_path.exists()
            else load_prompt(_PROMPT, fallback=_DEFAULT_PROMPT)
        )

    async def extract_resume(
        self, user_id: int, document: Document, content: str
    ) -> ResumeExtraction:
        """Run structured extraction and persist claimed evidence.

        Returns the validated extraction. Evidence rows are created for
        roles, technologies, projects, achievements, certifications,
        strengths, gaps, and explicit claims — all status=claimed.
        """
        if not content.strip():
            raise ValidationFailedError("resume content is empty")

        messages = [
            ChatMessage(role="system", content=self.prompt_text),
            ChatMessage(
                role="user",
                content=f"<<<RESUME DATA>>>\n{content}\n<<<END RESUME DATA>>>",
            ),
        ]
        extraction, _result = await generate_structured(
            self.router, TaskClass.EXTRACTION, messages, ResumeExtraction
        )

        await self._persist(user_id, document, extraction)
        return extraction

    async def _persist(
        self, user_id: int, document: Document, extraction: ResumeExtraction
    ) -> None:
        rows: list[Evidence] = []
        source_ref = f"document:{document.id}"

        for role in extraction.roles:
            rows.append(
                self._claim(
                    user_id,
                    source_ref,
                    f"Role: {role.title}"
                    + (f" at {role.company}" if role.company else "")
                    + (f" ({role.years:g} yrs)" if role.years else ""),
                )
            )
        for tech in extraction.technologies:
            rows.append(self._claim(user_id, source_ref, f"Technology: {tech}"))
        for proj in extraction.projects:
            if proj.name:
                rows.append(self._claim(user_id, source_ref, f"Project: {proj.name}"))
            for ach in proj.achievements:
                rows.append(self._claim(user_id, source_ref, f"Achievement ({proj.name}): {ach}"))
        for ach in extraction.achievements:
            rows.append(self._claim(user_id, source_ref, f"Achievement: {ach}"))
        for cert in extraction.certifications:
            rows.append(self._claim(user_id, source_ref, f"Certification: {cert}"))
        for claim in extraction.claims:
            rows.append(self._claim(user_id, source_ref, claim))
        for strength in extraction.strengths:
            rows.append(self._claim(user_id, source_ref, f"Strength: {strength}"))
        for gap in extraction.gaps:
            rows.append(self._claim(user_id, source_ref, f"Gap: {gap}"))

        if rows:
            await self.evidence.add_all(rows)

    @staticmethod
    def _claim(user_id: int, source_ref: str, claim: str) -> Evidence:
        return Evidence(
            user_id=user_id,
            source_kind=EvidenceSourceKind.RESUME,
            source_ref=source_ref,
            claim=claim,
            status=EvidenceStatus.CLAIMED,
        )


class ResumeExtractionRunner:
    """Loads a stored resume document, re-parses, and runs extraction."""

    def __init__(
        self, session: AsyncSession, router: InferenceRouter, *, storage_dir: Path
    ) -> None:
        self.session = session
        self.router = router
        self.storage_dir = storage_dir

    async def extract_document(
        self, user_id: int, document_id: int
    ) -> tuple[ResumeExtraction, int]:
        """Extract from document id; returns (extraction, evidence_count)."""
        doc_svc = DocumentService(self.session, storage_dir=self.storage_dir)
        document = await doc_svc.get_document(user_id, document_id)
        if document.kind.value != "resume":
            raise ValidationFailedError(
                "extraction requires a resume document",
                details={"document_id": document_id, "kind": str(document.kind)},
            )
        data = await doc_svc.read_stored_bytes(user_id, document_id)
        from app.core.config import get_settings
        from app.knowledge.parsing import parse_document_with_timeout

        settings = get_settings()
        parsed = await parse_document_with_timeout(
            data=data,
            kind=document.kind,
            mime=document.mime,
            filename=document.filename,
            content_hash=document.content_hash,
            max_pages=settings.document_max_pages,
            timeout_seconds=settings.document_parse_timeout_seconds,
        )
        extraction = await ExtractionService(self.session, self.router).extract_resume(
            user_id, document, parsed.content
        )
        return extraction, await _count_evidence(self.session, user_id)


async def _count_evidence(session: AsyncSession, user_id: int) -> int:
    from sqlalchemy import func, select

    from app.models.evidence import Evidence

    total = await session.scalar(
        select(func.count()).select_from(Evidence).where(Evidence.user_id == user_id)
    )
    return int(total or 0)
