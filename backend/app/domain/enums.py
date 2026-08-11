"""State enums for Pramya domain objects.

These are the single source of truth for state values. Business logic and
LangGraph state reference these enums, never magic strings.
"""

from __future__ import annotations

from enum import StrEnum


class InterviewSessionStatus(StrEnum):
    CREATED = "created"
    PLANNING = "planning"
    QUESTIONING = "questioning"
    PAUSED = "paused"
    INTERRUPTED = "interrupted"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    ERROR = "error"


class InterviewKind(StrEnum):
    GENERAL = "general"
    RESUME_DEEP_DIVE = "resume_deep_dive"
    JOB_DESCRIPTION = "job_description"
    TECHNICAL = "technical"
    BEHAVIORAL = "behavioral"
    PROJECT_DEEP_DIVE = "project_deep_dive"
    SYSTEM_DESIGN = "system_design"
    CODING_REASONING = "coding_reasoning"


class InterviewTurnKind(StrEnum):
    QUESTION = "question"
    ANSWER = "answer"
    FEEDBACK = "feedback"


class EvidenceStatus(StrEnum):
    """Evidence provenance ladder. Never present inference as fact."""

    CLAIMED = "claimed"
    OBSERVED = "observed"
    DEMONSTRATED = "demonstrated"
    INFERRED = "inferred"
    UNKNOWN = "unknown"


class EvidenceSourceKind(StrEnum):
    RESUME = "resume"
    JD = "jd"
    ANSWER = "answer"
    DEBRIEF = "debrief"
    CORRECTION = "correction"
    OBSERVATION = "observation"


class DocumentKind(StrEnum):
    RESUME = "resume"
    JD = "jd"
    DEBRIEF = "debrief"
    TRANSCRIPT = "transcript"


class DocumentStatus(StrEnum):
    PENDING = "pending"
    PARSING = "parsing"
    PARSED = "parsed"
    FAILED = "failed"


class VoiceState(StrEnum):
    """Voice pipeline states (mirrored client-side; authoritative server-side)."""

    IDLE = "idle"
    LISTENING = "listening"
    PROCESSING = "processing"
    SPEAKING = "speaking"
    PAUSED = "paused"
    INTERRUPTED = "interrupted"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    ERROR = "error"


class TurnDirection(StrEnum):
    INPUT = "input"
    OUTPUT = "output"


class PracticeItemStatus(StrEnum):
    OPEN = "open"
    DONE = "done"
    DISMISSED = "dismissed"


class CompetencyCategory(StrEnum):
    FRONTEND = "frontend"
    BACKEND = "backend"
    ARCHITECTURE = "architecture"
    BEHAVIORAL = "behavioral"
    DOMAIN = "domain"
    DATA = "data"
    AI = "ai"
    DEVOPS = "devops"
    PRODUCT = "product"
    OTHER = "other"


class CompetencyImportance(StrEnum):
    REQUIRED = "required"
    PREFERRED = "preferred"
    NICE_TO_HAVE = "nice_to_have"


class QuestionDifficulty(StrEnum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class AssessmentMode(StrEnum):
    TEXT = "text"
    VOICE = "voice"


class QuestionType(StrEnum):
    """Type of interview question (interview content, not session mode)."""

    TECHNICAL = "technical"
    BEHAVIORAL = "behavioral"
    SYSTEM_DESIGN = "system_design"
    CODING_REASONING = "coding_reasoning"
    PROJECT_DEEP_DIVE = "project_deep_dive"
    SITUATIONAL = "situational"
    GENERAL = "general"
    FOLLOW_UP = "follow_up"


class PracticeKind(StrEnum):
    """Kind of practice session (targeted exercise, mock, drill)."""

    MOCK_INTERVIEW = "mock_interview"
    TARGETED_EXERCISE = "targeted_exercise"
    GENERAL = "general"
    DEEP_DIVE = "deep_dive"
    CODING_REASONING = "coding_reasoning"
    BEHAVIORAL = "behavioral"
    SYSTEM_DESIGN = "system_design"


class EvaluationDimension(StrEnum):
    CORRECTNESS = "correctness"
    TECHNICAL_DEPTH = "technical_depth"
    CLARITY = "clarity"
    STRUCTURE = "structure"
    RELEVANCE = "relevance"
    EVIDENCE = "evidence"
    COMMUNICATION = "communication"
    TRADEOFF_AWARENESS = "tradeoff_awareness"
    REASONING = "reasoning"
    CONFIDENCE = "confidence"
    SPECIFICITY = "specificity"
    SENIORITY_ALIGNMENT = "seniority_alignment"
    COMPLETENESS = "completeness"
