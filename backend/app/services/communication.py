"""Deterministic communication analysis (Phase H).

Measured characteristics computed ONLY from persisted interview data
(transcript segments + their timestamps). Nothing is fabricated: when a
metric cannot be derived from available data it is reported as None.

No LLM is involved — this is pure text/timing arithmetic.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Filler / hesitation words (case-insensitive, counted as tokens).
FILLER_WORDS: frozenset[str] = frozenset(
    {
        "um",
        "uh",
        "hmm",
        "er",
        "ah",
        "like",
        "basically",
        "actually",
        "literally",
        "you know",
        "i mean",
        "sort of",
        "kind of",
        "i guess",
        "well",
        "right",
        "so yeah",
        "yeah so",
    }
)

_SENTENCE_END = re.compile(r"[.!?]+")
_TOKEN = re.compile(r"[a-z0-9']+")


@dataclass
class SegmentInput:
    """One persisted transcript segment (interviewer or candidate)."""

    text: str
    role: str  # "interviewer" | "candidate"
    timestamps: dict[str, object] | None = None


@dataclass
class CommunicationAnalysis:
    """Measured communication characteristics for one interview session."""

    # Scope: how many candidate answers were measured.
    answers_count: int = 0
    # Speech duration (s) summed over candidate segments with timestamps.
    total_speaking_seconds: float | None = None
    # Avg ms from question presentation to first candidate speech.
    avg_response_latency_ms: float | None = None
    # Verbosity (words per answer) over measured answers.
    avg_words_per_answer: float | None = None
    longest_answer_words: int = 0
    # Structure: avg sentences per answer (rough split on .!?).
    avg_sentences_per_answer: float | None = None
    # Filler frequency.
    filler_count: int = 0
    fillers_per_1000_words: float = 0.0
    # Interruptions recorded by the voice engine during the session.
    interruption_count: int = 0
    # Pauses (s) counted when a candidate segment records them.
    pauses_count: int = 0
    total_pause_seconds: float = 0.0
    # Field-level explanation of what was actually measured (honesty).
    notes: list[str] = field(default_factory=list[str])


def _words(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


def count_fillers(text: str) -> int:
    """Count filler phrases in a text (overlapping multi-word fillers each count)."""
    lowered = text.lower()
    count = 0
    for filler in FILLER_WORDS:
        if " " in filler:
            count += len(re.findall(re.escape(filler), lowered))
        else:
            count += len(re.findall(rf"\b{re.escape(filler)}\b", lowered))
    return count


def _num_ts(ts: dict[str, object] | None, key: str) -> float | None:
    if not ts:
        return None
    value = ts.get(key)
    if isinstance(value, (int, float)):
        return float(value)
    return None


def analyze_communication(
    segments: list[SegmentInput],
    *,
    interruption_count: int = 0,
) -> CommunicationAnalysis:
    """Compute communication characteristics from persisted segments.

    ``segments`` are the session's transcript segments in seq order. The
    candidate role is used for speech/latency/verbosity metrics; the
    interviewer side only contributes question timing where available.
    """
    result = CommunicationAnalysis(interruption_count=interruption_count)
    candidate_segments = [s for s in segments if s.role == "candidate"]
    if not candidate_segments:
        result.notes.append("no candidate speech recorded; nothing to measure")
        return result

    result.answers_count = len(candidate_segments)
    word_counts = [_words(s.text) for s in candidate_segments]
    result.avg_words_per_answer = round(sum(len(w) for w in word_counts) / len(word_counts), 1)
    result.longest_answer_words = max((len(w) for w in word_counts), default=0)
    sentences = [len(_SENTENCE_END.findall(s.text.strip())) for s in candidate_segments]
    if any(sentences):
        result.avg_sentences_per_answer = round(sum(sentences) / len(sentences), 1)

    fillers = sum(count_fillers(s.text) for s in candidate_segments)
    total_words = sum(len(w) for w in word_counts)
    result.filler_count = fillers
    if total_words:
        result.fillers_per_1000_words = round(fillers * 1000 / total_words, 1)

    # Timing metrics come only from persisted timestamps.
    speaking = 0.0
    measured_speaking = 0
    latencies: list[float] = []
    pauses = 0
    pause_seconds = 0.0
    for s in candidate_segments:
        ts = s.timestamps
        duration = _num_ts(ts, "audio_ms")
        if duration is not None:
            speaking += duration / 1000.0
            measured_speaking += 1
        latency = _num_ts(ts, "response_latency_ms")
        if latency is not None:
            latencies.append(latency)
        if ts:
            for key in ("pauses_ms",):
                value = ts.get(key)
                if isinstance(value, (int, float)):
                    pauses += 1
                    pause_seconds += float(value) / 1000.0
    if measured_speaking:
        result.total_speaking_seconds = round(speaking, 1)
    else:
        result.notes.append("no audio timestamps persisted; speaking duration unmeasured")
    if latencies:
        result.avg_response_latency_ms = round(sum(latencies) / len(latencies), 1)
    else:
        result.notes.append("no response latency timestamps; latency unmeasured")
    if pauses:
        result.pauses_count = pauses
        result.total_pause_seconds = round(pause_seconds, 1)
    else:
        result.notes.append("no pause measurements persisted; pauses unmeasured")

    if not result.notes:
        result.notes.append("all metrics measured from persisted transcript + audio data")
    return result
