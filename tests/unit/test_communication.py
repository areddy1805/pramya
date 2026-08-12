"""Deterministic communication analysis unit tests (Phase H).

The analyzer must never fabricate metrics: values are derived only from
persisted transcript text + timestamps.
"""

from __future__ import annotations

from app.services.communication import (
    SegmentInput,
    analyze_communication,
    count_fillers,
)


def _candidate(text: str, **ts: object) -> SegmentInput:
    return SegmentInput(text=text, role="candidate", timestamps=ts or None)


def test_no_candidate_segments_is_honest() -> None:
    result = analyze_communication([SegmentInput(text="Hi", role="interviewer")])
    assert result.answers_count == 0
    assert result.avg_words_per_answer is None
    assert result.total_speaking_seconds is None
    assert result.notes, "expected an explanatory note when nothing is measured"


def test_verbosity_and_sentence_metrics() -> None:
    segments = [
        _candidate("I led the migration. It shipped on time!"),
        _candidate("Great question."),
    ]
    result = analyze_communication(segments)
    assert result.answers_count == 2
    assert result.avg_words_per_answer == 5.0  # (8 + 2) / 2
    assert result.longest_answer_words == 8
    assert result.avg_sentences_per_answer == 1.5  # (2 + 1) / 2
    assert result.notes == [] or any("measured" in n for n in result.notes)


def test_filler_detection() -> None:
    assert count_fillers("um, well, I mean, like, basically, you know") == 6
    assert count_fillers("the terminal operators") == 0  # no filler tokens
    result = analyze_communication([_candidate("Um, well, I mean it worked.")])
    assert result.filler_count == 3
    # 6 words total ("um well i mean it worked") -> 3 * 1000 / 6
    assert result.fillers_per_1000_words == 500.0


def test_timing_metrics_from_timestamps() -> None:
    segments = [
        _candidate(
            "Yes",
            audio_ms=4000,
            response_latency_ms=1200,
        ),
        _candidate(
            "I handled it",
            audio_ms=6000,
            response_latency_ms=800,
        ),
    ]
    result = analyze_communication(segments)
    assert result.total_speaking_seconds == 10.0
    assert result.avg_response_latency_ms == 1000.0


def test_missing_timestamps_report_none_not_fabricated() -> None:
    result = analyze_communication([_candidate("plain text answer")])
    assert result.total_speaking_seconds is None
    assert result.avg_response_latency_ms is None
    assert result.pauses_count == 0
    assert any("unmeasured" in n for n in result.notes)


def test_interruption_count_propagates() -> None:
    result = analyze_communication([_candidate("ok")], interruption_count=3)
    assert result.interruption_count == 3


def test_pauses_recorded_when_present() -> None:
    result = analyze_communication(
        [_candidate("ok", pauses_ms=2500), _candidate("fine", pauses_ms=1500)]
    )
    assert result.pauses_count == 2
    assert result.total_pause_seconds == 4.0
