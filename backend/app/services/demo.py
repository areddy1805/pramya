"""Demo mode (Phase J): idempotent synthetic candidate + role setup.

Populates a fresh install with deterministic demo data — one candidate
profile, resumes, roles (4 demo roles), extraction, knowledge indexing,
readiness, and the preparation queue — so the UI can be exercised end to
end without real user data.

The demo pipeline mirrors the real HTTP flow but runs service-level so it
works in one call: profile -> upload+index resume -> extract evidence ->
analyze JD -> readiness -> preparation. Re-running is safe: identical
content is de-duplicated by content hash and roles by (user, title).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.factory import build_inference_router
from app.ai.router import InferenceRouter
from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.domain.enums import DocumentKind
from app.domain.errors import ValidationFailedError
from app.domain.schemas import ResumeExtraction
from app.services.analytics import PreparationService, ReadinessService
from app.services.document import DocumentService
from app.services.extraction import ResumeExtractionRunner
from app.services.role import RoleAnalysisService
from app.services.user import CandidateService

_logger = get_logger("app.services.demo")

# backend/app/services -> backend/app -> backend -> repo root
_REPO_ROOT = Path(__file__).resolve().parents[3]

DEMO_ROLE_KEYS: list[str] = ["senior-fullstack", "backend", "frontend", "product-manager"]

_ROLE_LABELS: dict[str, str] = {
    "senior-fullstack": "Senior Full Stack Engineer",
    "backend": "Senior Backend Engineer",
    "frontend": "Senior Frontend Engineer",
    "product-manager": "Senior Product Manager",
}


@dataclass
class DemoRoleResult:
    key: str
    document_id: int | None = None
    role_id: int | None = None
    chunks: int = 0
    evidence_count: int = 0
    competencies: int = 0


@dataclass
class DemoSetupResult:
    user_id: int
    profile: str = "ok"
    roles: list[DemoRoleResult] = field(default_factory=list[DemoRoleResult])
    readiness: float = 0.0
    critical_gaps: int = 0
    preparation_items: int = 0

    def summary(self) -> dict[str, object]:
        return {
            "user_id": self.user_id,
            "profile": self.profile,
            "roles": [
                {
                    "key": r.key,
                    "document_id": r.document_id,
                    "role_id": r.role_id,
                    "chunks": r.chunks,
                    "evidence_count": r.evidence_count,
                    "competencies": r.competencies,
                }
                for r in self.roles
            ],
            "readiness": self.readiness,
            "critical_gaps": self.critical_gaps,
            "preparation_items": self.preparation_items,
        }


def _demo_path(key: str, filename: str) -> Path:
    return _REPO_ROOT / "demo" / "roles" / key / filename


def load_demo_fixture(key: str, filename: str) -> str:
    """Read a demo fixture (resume.md / jd.md); ValueError when missing."""
    path = _demo_path(key, filename)
    if not path.is_file():
        raise ValueError(f"demo fixture missing: {path}")
    return path.read_text()


class DemoService:
    """Idempotent demo setup over the real domain services."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        settings: Settings | None = None,
        router: InferenceRouter | None = None,
    ) -> None:
        self.session = session
        self.settings = settings or get_settings()
        self.router = router or build_inference_router(self.settings)
        self.profiles = CandidateService(session)

    async def setup(
        self,
        user_id: int,
        *,
        roles: list[str] | None = None,
    ) -> DemoSetupResult:
        keys = [k for k in (roles or DEMO_ROLE_KEYS) if k in _ROLE_LABELS]
        if not keys:
            raise ValidationFailedError(
                "no demo roles requested; valid: " + ", ".join(DEMO_ROLE_KEYS)
            )

        # 1. Candidate profile (first run creates the owning user too).
        try:
            await self.profiles.create_profile(
                user_id=user_id,
                seniority_target="senior",
                headline="Demo candidate — full stack product engineer",
                timezone="UTC",
            )
            await self.session.commit()
            profile_status = "created"
        except ValidationFailedError:
            await self.session.rollback()
            profile_status = "exists"

        # 2. Per-role pipeline.
        results: list[DemoRoleResult] = []
        for key in keys:
            results.append(await self._setup_role(user_id, key))

        # 3. Readiness + preparation over all roles.
        readiness, gaps, prep_items = await self._finalize(user_id)

        result = DemoSetupResult(user_id=user_id, profile=profile_status, roles=results)
        result.readiness = readiness
        result.critical_gaps = gaps
        result.preparation_items = prep_items
        return result

    # -- internals -----------------------------------------------------------

    async def _setup_role(self, user_id: int, key: str) -> DemoRoleResult:
        out = DemoRoleResult(key=key)
        try:
            resume_text = load_demo_fixture(key, "resume.md")
            jd_text = load_demo_fixture(key, "jd.md")
        except ValueError as exc:
            _logger.warning("demo role %s skipped: %s", key, exc)
            return out

        # Resume: upload (dedup by content hash) -> index -> extract.
        doc_svc = DocumentService(
            self.session,
            storage_dir=Path(self.settings.upload_storage_dir),
            max_size_mb=self.settings.upload_max_mb,
            max_pages=self.settings.document_max_pages,
            parse_timeout_seconds=self.settings.document_parse_timeout_seconds,
        )
        document_id: int | None = None
        content = resume_text
        try:
            doc, parsed = await doc_svc.upload(
                user_id=user_id,
                kind=DocumentKind.RESUME,
                filename=f"{key}-resume.md",
                mime="text/markdown",
                data=resume_text.encode(),
            )
            await self.session.commit()
            document_id = doc.id
            content = parsed.content or resume_text
            out.document_id = doc.id
        except ValidationFailedError as exc:
            # Duplicate content: reuse the existing document.
            existing_id = (exc.details or {}).get("document_id")
            if isinstance(existing_id, int):
                document_id = existing_id
                out.document_id = existing_id
                doc = await doc_svc.get_document(user_id, existing_id)
                data = await doc_svc.read_stored_bytes(user_id, existing_id)
                from app.knowledge.parsing import parse_document_with_timeout

                parsed = await parse_document_with_timeout(
                    data=data,
                    kind=doc.kind,
                    mime=doc.mime,
                    filename=doc.filename,
                    content_hash=doc.content_hash,
                    max_pages=self.settings.document_max_pages,
                    timeout_seconds=self.settings.document_parse_timeout_seconds,
                )
                content = parsed.content or resume_text
            else:
                raise

        out.chunks = await self._index(user_id, document_id, content)
        _extraction, evidence_count = await self._extract(user_id, document_id)
        out.evidence_count = evidence_count

        # Role analysis (dedup by (user, title)).
        role_id, competencies = await self._analyze_role(user_id, jd_text, key)
        out.role_id = role_id
        out.competencies = competencies
        return out

    async def _index(self, user_id: int, document_id: int, content: str) -> int:
        doc_svc = DocumentService(self.session, storage_dir=Path(self.settings.upload_storage_dir))
        doc = await doc_svc.get_document(user_id, document_id)
        try:
            from app.knowledge.rag.service import LlamaIndexIngestionService

            rag = LlamaIndexIngestionService(
                self.session,
                self.router,
                chunk_size=self.settings.knowledge_chunk_size,
                chunk_overlap=self.settings.knowledge_chunk_overlap,
            )
            count = await rag.index_document(doc, content)
            if count:
                await self.session.commit()
                return count
        except Exception as exc:  # noqa: BLE001 — deterministic fallback
            _logger.warning("demo llamaindex ingest degraded: %s", exc)
        from app.knowledge.ingestion import IngestionService

        rows = await IngestionService(
            self.session,
            self.router,
            chunk_size=self.settings.knowledge_chunk_size,
            chunk_overlap=self.settings.knowledge_chunk_overlap,
            embed_batch_size=self.settings.knowledge_embed_batch_size,
        ).index_document(doc, content)
        return len(rows)

    async def _extract(self, user_id: int, document_id: int) -> tuple[ResumeExtraction | None, int]:
        # Idempotent: extraction evidence is keyed by source_ref; do not
        # duplicate evidence rows on re-runs.
        from sqlalchemy import select as sa_select

        from app.models.evidence import Evidence

        source_ref = f"document:{document_id}"
        stmt = sa_select(Evidence).where(Evidence.source_ref == source_ref)
        existing = (await self.session.scalars(stmt)).all()
        if existing:
            return None, len(existing)
        runner = ResumeExtractionRunner(
            self.session,
            self.router,
            storage_dir=Path(self.settings.upload_storage_dir),
        )
        extraction, count = await runner.extract_document(user_id, document_id)
        await self.session.commit()
        return extraction, count

    async def _analyze_role(self, user_id: int, jd_text: str, key: str) -> tuple[int | None, int]:
        svc = RoleAnalysisService(self.session, self.router)
        existing = await svc.roles.list_for_user(user_id)
        wanted = _ROLE_LABELS[key]
        for role in existing:
            if role.title == wanted:
                comps = await svc.roles.list_competencies(role.id)
                return role.id, len(comps)
        role = await svc.analyze(user_id, jd_text)
        await self.session.commit()
        comps = await svc.roles.list_competencies(role.id)
        return role.id, len(comps)

    async def _finalize(self, user_id: int) -> tuple[float, int, int]:
        readiness_svc = ReadinessService(self.session)
        prep_svc = PreparationService(self.session)
        roles = await RoleAnalysisService(self.session, self.router).roles.list_for_user(user_id)
        overall: float = 0.0
        gaps = 0
        for role in roles:
            result, _snapshot = await readiness_svc.compute_and_save(user_id, role.id)
            overall = max(overall, result.overall)
            gaps += len(result.critical_gaps)
        await self.session.commit()
        items = await prep_svc.regenerate(user_id)
        await self.session.commit()
        return overall, gaps, len(items)
