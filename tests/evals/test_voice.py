"""Voice evals (Phase F): transcription quality, turn finalization,
interruption correctness, stale-audio prevention.

Deterministic assertions run against the real VoiceEngine with stub
ASR/TTS/WS (no oMLX, no network). The optional semantic transcript
quality check uses the router judge when DeepSeek is configured.
"""

from __future__ import annotations

import asyncio
from typing import Any

from tests.evals.conftest import REQUIRES_DEEPSEEK
from tests.unit.test_voice_engine import (
    StubASR,
    StubInterview,
    StubTranscripts,
    StubTTS,
    StubWS,
    _cancel_task,
)

from app.domain.enums import VoiceState
from app.voice.engine import VoiceEngine


def _engine(ws: StubWS, *, asr: StubASR | None = None, tts: StubTTS | None = None) -> VoiceEngine:
    return VoiceEngine(
        interview=StubInterview(),  # type: ignore[arg-type]
        asr=asr or StubASR(),  # type: ignore[arg-type]
        tts=tts or StubTTS(),  # type: ignore[arg-type]
        session_id=7,
        user_id=1,
        ws=ws,
        silence_seconds=0.05,
        speech_rms=10.0,
        transcripts=StubTranscripts(),  # type: ignore[arg-type]
    )


async def _wait_state(engine: VoiceEngine, target: VoiceState, ms: int = 3000) -> bool:
    for _ in range(ms // 5):
        if engine.state == target:
            return True
        await asyncio.sleep(0.005)
    return engine.state == target


async def _wait_event(ws: StubWS, etype: str, ms: int = 3000) -> bool:
    for _ in range(ms // 5):
        if any(e.get("type") == etype for e in ws.json_out):
            return True
        await asyncio.sleep(0.005)
    return any(e.get("type") == etype for e in ws.json_out)


async def _wait_state_event(ws: StubWS, state: str, ms: int = 2000) -> bool:
    for _ in range(ms // 5):
        if any(e.get("type") == "state" and e.get("state") == state for e in ws.json_out):
            return True
        await asyncio.sleep(0.005)
    return False


def _record(
    eval_results: Any, case_id: str, metric: str, ok: bool, detail: str = "", score: float = 0.0
) -> None:
    eval_results.record(
        "voice",
        case_id,
        metric,
        score=1.0 if ok else score,
        threshold=1.0,
        passed=ok,
        detail=detail,
    )


async def test_voice_turn_finalization(golden_voice: dict[str, Any], eval_results: Any) -> None:
    """voice-001: silence watchdog finalizes the turn -> final transcript + answer."""
    case = next(c for c in golden_voice["cases"] if c["id"] == "voice-001")
    ws = StubWS()
    engine = _engine(ws)
    task = asyncio.create_task(engine.run(ws))
    try:
        assert await _wait_state(engine, VoiceState.LISTENING)
        ws.push_bytes(b"\x7f\x7f" * 3200)  # speech
        ws.push_bytes(b"\x00\x00" * 3200)  # silence -> finalize
        turn_ended = await _wait_event(ws, "turn_ended", ms=5000)
        transcript = await _wait_event(ws, "final_transcript", ms=5000)
        _record(
            eval_results,
            case["id"],
            "turn_finalization",
            turn_ended and transcript,
            detail=f"turn_ended={turn_ended} final_transcript={transcript}",
        )
        assert turn_ended and transcript
    finally:
        await _cancel_task(task)


async def test_voice_interruption_correctness(
    golden_voice: dict[str, Any], eval_results: Any
) -> None:
    """voice-002: barge-in during TTS -> interrupted -> listening, no stale audio."""
    case = next(c for c in golden_voice["cases"] if c["id"] == "voice-002")
    ws = StubWS()
    tts = StubTTS(gate=asyncio.Event())
    engine = _engine(ws, tts=tts)
    task = asyncio.create_task(engine.run(ws))
    try:
        assert await _wait_event(ws, "tts_start", ms=5000)  # mid-TTS (gated)
        gen_before = engine._generation
        ws.push_json({"type": "interrupt"})
        interrupted = await _wait_state_event(ws, "interrupted", ms=2000)
        back_to_listening = await _wait_state(engine, VoiceState.LISTENING)
        gen_bumped = engine._generation > gen_before
        tts.gate.set()
        await asyncio.sleep(0.05)
        stale = bool(ws.bytes_out)  # any bytes after interrupt = stale audio bug
        _record(
            eval_results,
            case["id"],
            "interruption_correctness",
            interrupted and back_to_listening and gen_bumped and not stale,
            detail=f"interrupted={interrupted} listening={back_to_listening} gen_bumped={gen_bumped} stale_bytes={stale}",  # noqa: E501
        )
        assert interrupted and back_to_listening and gen_bumped
        assert not stale, "stale TTS audio transmitted after interrupt"
    finally:
        await _cancel_task(task)


async def test_voice_stale_audio_prevention(
    golden_voice: dict[str, Any], eval_results: Any
) -> None:
    """voice-003: after interrupt, no old-generation chunks ever reach the wire."""
    case = next(c for c in golden_voice["cases"] if c["id"] == "voice-003")
    ws = StubWS()
    tts = StubTTS(gate=asyncio.Event())
    engine = _engine(ws, tts=tts)
    task = asyncio.create_task(engine.run(ws))
    try:
        assert await _wait_event(ws, "tts_start", ms=5000)
        ws.push_json({"type": "interrupt"})
        assert await _wait_state_event(ws, "interrupted", ms=2000)
        tts.gate.set()
        await asyncio.sleep(0.05)
        bytes_after = len(ws.bytes_out)
        stop_for_stale = any(e.get("type") == "tts_stop" for e in ws.json_out)
        _record(
            eval_results,
            case["id"],
            "stale_audio_prevention",
            bytes_after == 0,
            detail=f"bytes_after_interrupt={bytes_after} stale_tts_stop={stop_for_stale}",
        )
        assert bytes_after == 0, "old-generation TTS chunks leaked to the wire"
    finally:
        await _cancel_task(task)


@REQUIRES_DEEPSEEK
async def test_voice_transcription_quality(
    judge: Any, golden_voice: dict[str, Any], eval_results: Any
) -> None:
    """voice-004: golden ASR transcripts scored for semantic quality."""
    case = next(c for c in golden_voice["cases"] if c["id"] == "voice-004")
    from deepeval.metrics import AnswerRelevancyMetric
    from deepeval.test_case import LLMTestCase

    for i, pair in enumerate(case["golden_pairs"]):
        metric = AnswerRelevancyMetric(
            model=judge, threshold=0.5, async_mode=True, include_reason=True
        )
        await metric.a_measure(
            LLMTestCase(
                input=pair["reference"],
                actual_output=pair["asr"],
            )
        )
        ok = metric.score >= golden_voice["thresholds"]["transcription_quality"]
        eval_results.record(
            "voice",
            f"voice-004.{i}",
            "transcription_quality",
            score=metric.score,
            threshold=golden_voice["thresholds"]["transcription_quality"],
            passed=ok,
            detail=metric.reason or "",
        )
        assert ok, f"transcript pair {i}: score {metric.score:.2f}"
