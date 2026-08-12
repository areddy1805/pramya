"""Role analysis service (Phase 2.5).

JD text -> structured role model (InferenceRouter; deepseek-v4-flash for
analysis quality, 4B fallback) -> persisted Role + Competency graph +
CandidateCompetency seed rows. Task class COMPLEX_REASONING per the policy
table (JD analysis materially benefits from stronger reasoning).
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.contracts import ChatMessage
from app.ai.langchain.structured import generate_structured
from app.ai.policy import TaskClass
from app.ai.router import InferenceRouter
from app.domain.enums import CompetencyCategory, CompetencyImportance
from app.domain.errors import ValidationFailedError
from app.domain.schemas import RoleAnalysis
from app.models.role import Competency, Role
from app.repositories.misc import RoleRepository
from app.services.prompts import load_prompt

_PROMPT = "role_analysis/jd_analysis.txt"
_DEFAULT_PROMPT = (
    "Analyze the job description and produce a structured role model with "
    "competencies. Never invent requirements absent from the JD."
)


class RoleAnalysisService:
    """JD -> role model + competency graph, persisted."""

    def __init__(
        self,
        session: AsyncSession,
        router: InferenceRouter,
        *,
        prompt_path: Path | None = None,
    ) -> None:
        self.session = session
        self.router = router
        self.roles = RoleRepository(session)
        self.prompt_text = (
            prompt_path.read_text()
            if prompt_path is not None and prompt_path.exists()
            else load_prompt(_PROMPT, fallback=_DEFAULT_PROMPT)
        )

    async def analyze(
        self,
        user_id: int,
        jd_text: str,
        *,
        source_document_id: int | None = None,
    ) -> Role:
        """Analyze JD text, persist role + competencies, return the role."""
        if not jd_text.strip():
            raise ValidationFailedError("JD text is empty")

        messages = [
            ChatMessage(role="system", content=self.prompt_text),
            ChatMessage(
                role="user",
                content=f"<<<DOCUMENT DATA>>>\n{jd_text}\n<<<END DOCUMENT DATA>>>",
            ),
        ]
        analysis, _result = await generate_structured(
            self.router, TaskClass.COMPLEX_REASONING, messages, RoleAnalysis
        )
        if not analysis.competencies:
            raise ValidationFailedError("role analysis produced no competencies")

        role = Role(
            user_id=user_id,
            source_document_id=source_document_id,
            title=analysis.title,
            seniority=analysis.seniority,
            summary=analysis.summary,
        )
        await self.roles.add(role)

        competencies = self._build_competencies(analysis, role.id)
        await self.roles.add_all_competencies(competencies)
        return role

    @staticmethod
    def _build_competencies(analysis: RoleAnalysis, role_id: int) -> list[Competency]:
        rows: list[Competency] = []
        for idx, comp in enumerate(analysis.competencies):
            rows.append(
                Competency(
                    role_id=role_id,
                    name=comp.name,
                    category=_category(comp.category),
                    level=comp.level,
                    importance=_importance(comp.importance),
                    weight=comp.weight,
                    importance_rank=idx,
                )
            )
        return rows


def _category(value: str) -> CompetencyCategory:
    try:
        return CompetencyCategory(value)
    except ValueError:
        return CompetencyCategory.OTHER


def _importance(value: str) -> CompetencyImportance:
    try:
        return CompetencyImportance(value)
    except ValueError:
        return CompetencyImportance.PREFERRED
