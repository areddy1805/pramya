"""Core domain Pydantic schemas.

Schemas live close to the domain; API routers map between these and
request/response models. Typed everywhere — no untyped dicts for domain data.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import EvidenceStatus, InterviewKind


class TimestampedModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class CandidateProfile(TimestampedModel):
    id: int
    user_id: int
    seniority_target: str | None = None
    headline: str | None = None
    timezone: str | None = None


class EvidenceReference(BaseModel):
    """Pointer to a piece of supporting evidence for an evaluation."""

    evidence_id: int
    status: EvidenceStatus
    claim: str
    source: str


class EvaluationDimensions(BaseModel):
    """Dimension scores from the evaluation engine (0–10 scale)."""

    correctness: float | None = Field(default=None, ge=0, le=10)
    technical_depth: float | None = Field(default=None, ge=0, le=10)
    clarity: float | None = Field(default=None, ge=0, le=10)
    structure: float | None = Field(default=None, ge=0, le=10)
    relevance: float | None = Field(default=None, ge=0, le=10)
    evidence: float | None = Field(default=None, ge=0, le=10)
    communication: float | None = Field(default=None, ge=0, le=10)
    tradeoff_awareness: float | None = Field(default=None, ge=0, le=10)
    reasoning: float | None = Field(default=None, ge=0, le=10)
    confidence: float | None = Field(default=None, ge=0, le=10)
    specificity: float | None = Field(default=None, ge=0, le=10)
    seniority_alignment: float | None = Field(default=None, ge=0, le=10)
    completeness: float | None = Field(default=None, ge=0, le=10)


class InterviewConfig(BaseModel):
    """User-supplied interview configuration."""

    kind: InterviewKind = InterviewKind.GENERAL
    duration_minutes: int = Field(default=30, ge=5, le=120)
    focus_competency_ids: list[int] = Field(default_factory=list)
    mode: Literal["text", "voice"] = "text"


class EvaluationRecord(BaseModel):
    """One immutable evaluation of an answer."""

    id: int
    answer_id: int
    dimensions: EvaluationDimensions
    overall: float = Field(ge=0, le=10)
    confidence: float = Field(ge=0, le=1)
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    evidence_refs: list[EvidenceReference] = Field(default_factory=list)
    missing_evidence: list[str] = Field(default_factory=list)
    hints_used: int = 0
    follow_ups: list[str] = Field(default_factory=list)
    evaluator_version: str
    created_at: datetime
