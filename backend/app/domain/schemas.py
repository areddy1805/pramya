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
    focus_competency_ids: list[int] = Field(default_factory=lambda: [])
    mode: Literal["text", "voice"] = "text"


class EvaluationRecord(BaseModel):
    """One immutable evaluation of an answer."""

    id: int
    answer_id: int
    dimensions: EvaluationDimensions
    overall: float = Field(ge=0, le=10)
    confidence: float = Field(ge=0, le=1)
    strengths: list[str] = Field(default_factory=lambda: [])
    weaknesses: list[str] = Field(default_factory=lambda: [])
    evidence_refs: list[EvidenceReference] = Field(default_factory=lambda: [])
    missing_evidence: list[str] = Field(default_factory=lambda: [])
    hints_used: int = 0
    follow_ups: list[str] = Field(default_factory=lambda: [])
    evaluator_version: str
    created_at: datetime


# --- Structured AI outputs (Phase 2.4/2.5) -----------------------------------
# These Pydantic models are the JSON-Schema contracts for LLM outputs. They
# are validated before any state mutation; invalid output never persists.


class ExtractedRole(BaseModel):
    title: str
    company: str | None = None
    years: float | None = Field(default=None, ge=0, le=60)
    summary: str | None = None


class ExtractedProject(BaseModel):
    name: str
    description: str | None = None
    technologies: list[str] = Field(default_factory=lambda: [])
    achievements: list[str] = Field(default_factory=lambda: [])


class ResumeExtraction(BaseModel):
    """Structured candidate extraction from a resume (task 2.4)."""

    headline: str | None = None
    seniority_target: str | None = None
    roles: list[ExtractedRole] = Field(default_factory=lambda: [])
    technologies: list[str] = Field(default_factory=lambda: [])
    projects: list[ExtractedProject] = Field(default_factory=lambda: [])
    achievements: list[str] = Field(default_factory=lambda: [])
    claims: list[str] = Field(default_factory=lambda: [])
    certifications: list[str] = Field(default_factory=lambda: [])
    strengths: list[str] = Field(default_factory=lambda: [])
    gaps: list[str] = Field(default_factory=lambda: [])


class RoleCompetency(BaseModel):
    name: str
    category: str = "other"  # CompetencyCategory value
    level: int = Field(ge=1, le=5)
    # Importance is REQUIRED (no default): the schema must not mask what
    # the model decided. Retry-with-feedback covers transient omissions.
    importance: str  # CompetencyImportance value
    weight: float = Field(default=0.1, ge=0, le=1)


class RoleAnalysis(BaseModel):
    """Structured role model from a JD (task 2.5)."""

    title: str
    seniority: str | None = None
    summary: str | None = None
    required_skills: list[str] = Field(default_factory=lambda: [])
    preferred_skills: list[str] = Field(default_factory=lambda: [])
    responsibilities: list[str] = Field(default_factory=lambda: [])
    competencies: list[RoleCompetency] = Field(default_factory=lambda: [])
    # Implied skills the JD references but does not name (e.g. system design
    # for "scale to millions"). Distinct from required/preferred.
    implied_skills: list[str] = Field(default_factory=lambda: [])


class AnswerEvidence(BaseModel):
    """Evidence claim extracted from an interview answer (Phase 3)."""

    claim: str
    status: EvidenceStatus = EvidenceStatus.OBSERVED
    strength: float = Field(default=0.5, ge=0, le=1)
    competency_hint: str | None = None


class AnswerEvaluation(BaseModel):
    """Structured evaluation of one answer (Phase 3)."""

    dimensions: EvaluationDimensions
    overall: float = Field(ge=0, le=10)
    # LLM output is untrusted: optional numeric fields get safe defaults
    # rather than failing the whole evaluation on a missing field.
    confidence: float = Field(default=0.5, ge=0, le=1)
    strengths: list[str] = Field(default_factory=lambda: [])
    weaknesses: list[str] = Field(default_factory=lambda: [])
    missing_evidence: list[str] = Field(default_factory=lambda: [])
    follow_ups: list[str] = Field(default_factory=lambda: [])
    evidence: list[AnswerEvidence] = Field(default_factory=lambda: [])


class InterviewQuestion(BaseModel):
    """Structured question generation output (Phase 3)."""

    text: str
    type: str = "general"  # QuestionType value
    difficulty: str = "medium"  # QuestionDifficulty value
    rationale: str | None = None
    hint_levels: list[str] = Field(default_factory=lambda: [])
    target_competency: str | None = None
    # Provenance (productization): taxonomy category + grounding source and
    # the specific entity the question targets.
    category: str | None = None
    source: str | None = None
    source_ref: str | None = None


class InterviewerReasoning(BaseModel):
    """Interviewer's post-answer reasoning (productization step 4).

    Decides what the next question should do with this answer: dig deeper
    into the same thread (deep/light follow-up), challenge the claim,
    clarify ambiguity, change topic, or move on. Also surfaces detected
    gaps and coverage tags for the deterministic tracker.
    """

    decision: Literal[
        "follow_up_deep",
        "follow_up_light",
        "move_on",
        "challenge",
        "clarify",
        "change_topic",
    ] = "move_on"
    reason: str = ""
    topic: str | None = None
    gaps_detected: list[str] = Field(default_factory=lambda: [])
    coverage_tags: list[str] = Field(default_factory=lambda: [])


class HintOutput(BaseModel):
    hint: str


class InterviewPlan(BaseModel):
    """Session plan: which competencies to probe and how (Phase 3)."""

    focus_competencies: list[str] = Field(default_factory=lambda: [])
    opening: str | None = None
    plan_summary: str | None = None


class TranscriptAnalysis(BaseModel):
    """Structured analysis of a pasted transcript (Phase 10)."""

    questions: list[str] = Field(default_factory=lambda: [])
    answers: list[str] = Field(default_factory=lambda: [])
    follow_ups: list[str] = Field(default_factory=lambda: [])
    weaknesses: list[str] = Field(default_factory=lambda: [])
    strengths: list[str] = Field(default_factory=lambda: [])


class DebriefAnalysis(BaseModel):
    """Structured analysis of a real-interview debrief (Phase 10)."""

    weaknesses: list[str] = Field(default_factory=lambda: [])
    strengths: list[str] = Field(default_factory=lambda: [])
    recommendations: list[str] = Field(default_factory=lambda: [])
    competency_hints: list[str] = Field(default_factory=lambda: [])


class StoryAnalysis(BaseModel):
    """Structured STAR story analysis (Phase 10)."""

    situation: str | None = None
    task: str | None = None
    action: str | None = None
    result: str | None = None
    metrics: str | None = None
    conflict: str | None = None
    learning: str | None = None
    strength: str | None = None
    competency_hints: list[str] = Field(default_factory=lambda: [])
