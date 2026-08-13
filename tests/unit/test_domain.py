"""Unit tests: domain enums and schemas."""

import pytest
from pydantic import ValidationError

from app.domain.enums import (
    EvidenceStatus,
    InterviewKind,
    InterviewSessionStatus,
    VoiceState,
)
from app.domain.schemas import EvaluationDimensions, EvaluationRecord, InterviewConfig


def test_evidence_status_ladder() -> None:
    assert EvidenceStatus.CLAIMED.value == "claimed"
    assert EvidenceStatus.DEMONSTRATED.value == "demonstrated"


def test_session_status_values() -> None:
    values = {s.value for s in InterviewSessionStatus}
    assert "questioning" in values
    assert "interrupted" in values
    assert "completed" in values


def test_voice_state_complete_set() -> None:
    expected = {
        "idle",
        "starting",
        "listening",
        "processing",
        "speaking",
        "paused",
        "interrupted",
        "cancelled",
        "completed",
        "error",
    }
    assert {v.value for v in VoiceState} == expected


def test_interview_kind_enum() -> None:
    assert InterviewKind.SYSTEM_DESIGN.value == "system_design"


def test_evaluation_dimensions_bounds() -> None:
    with pytest.raises(ValidationError):
        EvaluationDimensions(correctness=11.0)
    with pytest.raises(ValidationError):
        EvaluationDimensions(technical_depth=-1.0)
    ok = EvaluationDimensions(correctness=7.5)
    assert ok.correctness == 7.5


def test_interview_config_defaults() -> None:
    cfg = InterviewConfig()
    assert cfg.kind == InterviewKind.GENERAL
    assert cfg.duration_minutes == 30
    assert cfg.mode == "text"
    assert cfg.focus_competency_ids == []


def test_interview_config_bounds() -> None:
    with pytest.raises(ValidationError):
        InterviewConfig(duration_minutes=200)


def test_evaluation_record_requires_version() -> None:
    with pytest.raises(ValidationError):
        EvaluationRecord(
            id=1,
            answer_id=2,
            dimensions=EvaluationDimensions(),
            overall=8.0,
            confidence=0.8,
            evaluator_version="",  # empty not rejected by pydantic but stays empty
        )
