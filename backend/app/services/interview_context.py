# pyright: reportUnknownVariableType=false, reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownParameterType=false
"""Interview context builder (productization step 2).

Builds an immutable grounding snapshot for one interview session from the
profile-scoped workspace: candidate profile, resume text + evidence claims,
JD text, role + competency graph, profile-scoped evidence, and prior
preparation memory (interview_feedback rows for the profile).

The snapshot is stored in ``session.config["context"]`` at begin()/first
question and injected into the question-generation prompt so the
interviewer grounds every question in the candidate's REAL material only.
This is the anti-hallucination + profile-isolation backbone: nothing from
another profile, nothing invented.

All output is plain JSON-serializable dicts (config JSONB column).
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.domain.enums import DocumentKind
from app.domain.errors import ValidationFailedError
from app.models.document import Document
from app.repositories.document import DocumentChunkRepository, DocumentRepository
from app.repositories.evidence import EvidenceRepository
from app.repositories.misc import InterviewFeedbackRepository, RoleRepository
from app.repositories.user import CandidateProfileRepository

RESUME_MAX_CHARS = 8000
JD_MAX_CHARS = 4000
EVIDENCE_LIMIT = 40
PRIOR_FEEDBACK_LIMIT = 3

# Evidence-claim prefixes produced by the extraction pipeline — parsed back
# into structured resume signals deterministically (no extra LLM call).
_CLAIM_PREFIXES = (
    "technology:",
    "project:",
    "achievement:",
    "role:",
    "certification:",
    "strength:",
    "gap:",
)

# Claim prefix -> resume-signals key.
_KIND_TO_SIGNAL = {
    "technology": "technologies",
    "project": "projects",
    "achievement": "achievements",
    "strength": "strengths",
    "gap": "gaps",
}


def _parse_claim(claim: str) -> tuple[str | None, str]:
    """Split a ledger claim into (kind, value) where kind is the prefix."""
    lowered = claim.lower()
    for prefix in _CLAIM_PREFIXES:
        if lowered.startswith(prefix):
            return prefix.rstrip(":"), claim[len(prefix) :].strip()
    return None, claim.strip()


class InterviewContextBuilder:
    """Assembles the per-session grounding snapshot."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        logger: logging.Logger | None = None,
    ) -> None:
        self.session = session
        self._logger = logger or get_logger("app.interview.context")
        self.profiles = CandidateProfileRepository(session)
        self.documents = DocumentRepository(session)
        self.chunks = DocumentChunkRepository(session)
        self.roles = RoleRepository(session)
        self.evidence = EvidenceRepository(session)
        self.feedback = InterviewFeedbackRepository(session)

    async def build(
        self,
        *,
        user_id: int,
        profile_id: int | None,
        role_id: int | None,
    ) -> dict[str, object]:
        """Build (or reuse cached) context snapshot for one session.

        ``missing`` lists which grounding pieces the selected profile lacks
        (profile is required; resume is required for normal interviews;
        jd/evidence/role are optional). Never infers a profile and never
        pulls documents from another profile.
        """
        profile = await self._profile(user_id, profile_id)
        resume = await self._resume(user_id, profile_id)
        jd = await self._jd(user_id, profile_id)
        role = await self._role(user_id, profile_id, role_id)
        evidence = await self._evidence(user_id, profile_id)
        prior_feedback = await self._prior_feedback(user_id, profile_id)
        missing: list[str] = []
        if profile is None:
            missing.append("profile")
        if resume is None:
            missing.append("resume")
        return {
            "built_at": datetime.now(UTC).isoformat(),
            "user_id": user_id,
            "profile_id": profile_id,
            "profile": profile,
            "resume": resume,
            "jd": jd,
            "role": role,
            "evidence": evidence,
            "prior_feedback": prior_feedback,
            "missing": missing,
        }

    # -- sections ------------------------------------------------------------

    async def _profile(self, user_id: int, profile_id: int | None) -> dict[str, object] | None:
        # Explicit profile only — no silent first-profile fallback.
        if profile_id is None:
            return None
        profile = await self.profiles.get_for_user(user_id, profile_id)
        if profile is None:
            return None
        return {
            "id": profile.id,
            "name": profile.name,
            "headline": profile.headline,
            "positioning": profile.positioning,
            "seniority_target": profile.seniority_target,
        }

    async def _resume(self, user_id: int, profile_id: int | None) -> dict[str, object] | None:
        # STRICTLY profile-scoped: never falls back to other profiles' docs.
        # Explicit legacy/global rows (profile_id IS NULL) are the only
        # non-profile rows considered, and only when a profile_id is set.
        docs = list(
            await self.documents.list_for_user(
                user_id, kind=DocumentKind.RESUME, profile_id=profile_id
            )
        )
        if not docs and profile_id is not None:
            docs = list(
                await self.documents.list_for_user(
                    user_id, kind=DocumentKind.RESUME, legacy_only=True
                )
            )
        if not docs:
            return None
        selected = await self._preferred_or_latest(user_id, profile_id, docs, "resume")
        text = await self._document_text(selected.id)
        if not text:
            return None
        return {
            "document_id": selected.id,
            "filename": selected.filename,
            "status": str(selected.status),
            "ready": str(selected.status) == "parsed",
            "text": text[:RESUME_MAX_CHARS],
        }

    async def _jd(self, user_id: int, profile_id: int | None) -> dict[str, object] | None:
        # STRICTLY profile-scoped; legacy rows (profile_id IS NULL) allowed
        # as explicit global docs, never arbitrary user-scoped documents.
        docs = list(
            await self.documents.list_for_user(user_id, kind=DocumentKind.JD, profile_id=profile_id)
        )
        if not docs and profile_id is not None:
            docs = list(
                await self.documents.list_for_user(user_id, kind=DocumentKind.JD, legacy_only=True)
            )
        if not docs:
            return None
        selected = await self._preferred_or_latest(user_id, profile_id, docs, "jd")
        text = await self._document_text(selected.id)
        if not text:
            return None
        return {
            "document_id": selected.id,
            "filename": selected.filename,
            "status": str(selected.status),
            "ready": str(selected.status) == "parsed",
            "text": text[:JD_MAX_CHARS],
        }

    async def _preferred_or_latest(
        self,
        user_id: int,
        profile_id: int | None,
        docs: Sequence[Document],
        kind: str,
    ) -> Document:
        """Explicit persisted preference wins; otherwise the latest by id.
        A stale preference (document removed) falls back to latest — the
        pointer is SET NULL on delete, this guards any race."""
        if profile_id is not None:
            profile = await self.profiles.get_for_user(user_id, profile_id)
            if profile is not None:
                preferred_id = (
                    profile.preferred_resume_document_id
                    if kind == "resume"
                    else profile.preferred_jd_document_id
                )
                if preferred_id is not None:
                    for d in docs:
                        if d.id == preferred_id:
                            return d
        return max(docs, key=lambda d: d.id)

    async def _document_text(self, document_id: int) -> str:
        chunks = await self.chunks.list_for_document(document_id)
        return "\n".join(c.content for c in chunks).strip()

    async def _role(
        self, user_id: int, profile_id: int | None, role_id: int | None
    ) -> dict[str, object] | None:
        if role_id is None:
            return None
        role = await self.roles.get(role_id)
        if role is None:
            return None
        # Ownership invariant: a role may ground an interview only when it
        # belongs to the same user AND the same profile (legacy rows with
        # profile_id IS NULL remain valid). A foreign role would leak
        # another profile's target role + competencies into this profile's
        # questions and report — reject it explicitly, never silently omit.
        if role.user_id != user_id or (
            role.profile_id is not None and role.profile_id != profile_id
        ):
            raise ValidationFailedError(
                "role does not belong to this profile",
                details={"role_id": role_id, "profile_id": profile_id},
            )
        comps = await self.roles.list_competencies(role.id)
        return {
            "id": role.id,
            "title": role.title,
            "seniority": role.seniority,
            "summary": role.summary,
            "competencies": [
                {
                    "name": c.name,
                    "category": str(c.category),
                    "level": c.level,
                    "importance": str(c.importance),
                }
                for c in comps
            ],
        }

    async def _evidence(self, user_id: int, profile_id: int | None) -> list[dict[str, object]]:
        rows = await self.evidence.list_for_user(
            user_id, profile_id=profile_id, limit=EVIDENCE_LIMIT
        )
        return [
            {
                "claim": e.claim,
                "source_kind": str(e.source_kind),
                "source_ref": e.source_ref,
                "status": str(e.status),
            }
            for e in rows
        ]

    async def _prior_feedback(
        self, user_id: int, profile_id: int | None
    ) -> list[dict[str, object]]:
        rows = await self.feedback.latest_for_profile(
            user_id, profile_id=profile_id, limit=PRIOR_FEEDBACK_LIMIT
        )
        return [
            {
                "weaknesses": list(f.weaknesses or []),
                "gaps": list(f.gaps or []),
                "topics": list(f.topics or []),
                "avg_overall": f.avg_overall,
            }
            for f in rows
        ]


def resume_signals(evidence: list[dict[str, object]]) -> dict[str, list[str]]:
    """Deterministic resume signals from profile-scoped evidence claims.

    Returns {technologies, projects, achievements, strengths, gaps} parsed
    from the extraction pipeline's claim prefixes.
    """
    signals: dict[str, list[str]] = {
        "technologies": [],
        "projects": [],
        "achievements": [],
        "strengths": [],
        "gaps": [],
    }
    for item in evidence:
        kind, value = _parse_claim(str(item.get("claim", "")))
        if not kind or not value:
            continue
        key = _KIND_TO_SIGNAL.get(kind)
        if key is not None and value not in signals[key]:
            signals[key].append(value)
    return signals


__all__ = ["InterviewContextBuilder", "resume_signals"]
