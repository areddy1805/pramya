"""VoiceEngine unit tests (H.1-H.8): concurrency, turn finalization,
generation invalidation, pause/resume/stop, persistence hooks.

Uses stub WS/ASR/TTS + a stub interview seam; no real oMLX, no DB. The
critical H.1 property is covered directly: while the engine is speaking
(TTS streaming), the receive loop must still process interrupt/pause/stop.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

import pytest

from app.domain.enums import VoiceState
from app.voice.engine import VoiceEngine


class StubWS:
    """Collects sent JSON + bytes; feeds queued (kind, payload) messages."""

    def __init__(self) -> None:
        self.inbox: list[tuple[str, object]] = []
        self.json_out: list[dict[str, object]] = []
        self.bytes_out: list[bytes] = []
        self.closed = False
        self._ready = asyncio.Event()

    def push_json(self, payload: dict[str, object]) -> None:
        self.inbox.append(("json", payload))
        self._ready.set()

    def push_bytes(self, payload: bytes) -> None:
        self.inbox.append(("bytes", payload))
        self._ready.set()

    async def receive(self) -> tuple[str, object]:
        while not self.inbox:
            self._ready.clear()
            await self._ready.wait()
        return self.inbox.pop(0)

    async def send_json(self, payload: dict[str, object]) -> None:
        self.json_out.append(payload)

    async def send_bytes(self, payload: bytes) -> None:
        self.bytes_out.append(payload)

    async def close(self, code: int = 1000) -> None:
        self.closed = True


@dataclass
class StubASR:
    text: str = "my spoken answer"
    calls: list[bytes] = field(default_factory=list)

    async def transcribe(self, pcm16: bytes, *, sample_rate: int = 16000) -> str:
        self.calls.append(pcm16)
        return self.text


@dataclass
class StubTTS:
    pcm: bytes = b"\x00\x00" * 96000  # 2 s @ 24 kHz
    sr: int = 24000
    synthesizes: list[str] = field(default_factory=list)
    gate: asyncio.Event | None = None  # if set, synthesize blocks until released
    chunk_delay: float = 0.0  # per-chunk sleep (deterministic mid-stream interrupts)

    async def synthesize(self, text: str) -> tuple[bytes, int]:
        self.synthesizes.append(text)
        if self.gate is not None:
            await self.gate.wait()
        return self.pcm, self.sr


class StubTranscripts:
    def __init__(self) -> None:
        self.segments: list[dict[str, object]] = []

    async def max_seq_for_turn(self, turn_id: int) -> int:
        return sum(1 for s in self.segments if s.get("turn_id") == turn_id)

    async def add(self, obj: object) -> None:
        turn_id = obj.turn_id  # type: ignore[attr-defined]
        text = obj.text  # type: ignore[attr-defined]
        self.segments.append({"turn_id": turn_id, "text": text})


class _Evaluations:
    """Stub evaluation repo."""

    async def get_by_answer(self, answer_id: int) -> object:
        return type("E", (), {"overall": 6.5})()


class _AsyncNoopSession:
    async def commit(self) -> None:
        return None


class StubInterview:
    """Seam-stub of the InterviewService surface used by the engine."""

    def __init__(self) -> None:
        self.started = False
        self.next_question_text = "Tell me about a hard problem you solved."
        self.question_seq = 0
        self.turn_seq = 0
        self.answer_texts: list[str] = []
        self.overall = 6.5
        self.session = _AsyncNoopSession()

    async def begin(self, session_id: int, user_id: int) -> object:
        self.started = True
        return object()

    async def next_question(self, session_id: int, user_id: int) -> tuple[object, object]:
        self.question_seq += 1
        self.turn_seq += 1
        q = type(
            "Q",
            (),
            {"id": self.question_seq, "text": self.next_question_text, "difficulty": "medium"},
        )()
        turn = type("T", (), {"id": self.turn_seq})()
        return q, turn

    async def submit_answer(
        self,
        session_id: int,
        user_id: int,
        *,
        question_id: int,
        answer_text: str,
        idempotency_key: str | None,
        mode: str,
    ) -> object:
        self.answer_texts.append(answer_text)
        self.turn_seq += 1
        return type("A", (), {"id": 1})()

    async def stop(self, session_id: int, user_id: int) -> object:
        return object()

    async def cancel(self, session_id: int, user_id: int) -> object:
        return object()

    class _Sessions:
        async def get_or_raise(self, obj_id: int, *, name: str | None = None) -> object:
            return type("S", (), {"user_id": 1, "status": "created"})()

    class _Turns:
        async def latest_for_session(self, session_id: int) -> object:
            return type("T", (), {"id": 99})()

    sessions = _Sessions()
    turns = _Turns()
    evaluations = _Evaluations()


async def _async_noop() -> None:
    return None


def _engine(ws: StubWS) -> VoiceEngine:
    interview = StubInterview()
    return VoiceEngine(
        interview=interview,  # type: ignore[arg-type]
        asr=StubASR(),  # type: ignore[arg-type]
        tts=StubTTS(),  # type: ignore[arg-type]
        session_id=7,
        user_id=1,
        ws=ws,
        silence_seconds=0.05,  # fast silence finalization in tests
        speech_rms=10.0,  # near-zero: any audio counts as speech
        transcripts=StubTranscripts(),  # type: ignore[arg-type]
    )


def _states(ws: StubWS) -> list[str]:
    return [str(e["state"]) for e in ws.json_out if e.get("type") == "state"]


async def _wait_state(engine: VoiceEngine, ws: StubWS, target: VoiceState, ms: int = 3000) -> bool:
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


async def _wait_state_event(ws: StubWS, state: str, ms: int = 3000) -> bool:
    for _ in range(ms // 5):
        if any(e.get("type") == "state" and str(e.get("state")) == state for e in ws.json_out):
            return True
        await asyncio.sleep(0.005)
    return any(e.get("type") == "state" and str(e.get("state")) == state for e in ws.json_out)


async def _cancel_task(task: asyncio.Task[None]) -> None:
    task.cancel()
    try:
        await task
    except (asyncio.CancelledError, RuntimeError):
        pass


@pytest.mark.asyncio
async def test_engine_streams_question_then_listens() -> None:
    ws = StubWS()
    engine = _engine(ws)
    task = asyncio.create_task(engine.run(ws))
    assert await _wait_event(ws, "question", ms=5000)
    assert ws.bytes_out, "expected TTS audio chunks"
    assert await _wait_state(engine, ws, VoiceState.LISTENING)
    questions = [e for e in ws.json_out if e.get("type") == "question"]
    assert questions[0]["text"] == "Tell me about a hard problem you solved."
    assert "tts_start" in {e.get("type") for e in ws.json_out}
    await _cancel_task(task)


@pytest.mark.asyncio
async def test_interrupt_while_speaking_is_processed_by_hot_loop() -> None:
    """H.1: the receive loop stays hot while TTS is generating (gated)."""
    ws = StubWS()
    tts = StubTTS(gate=asyncio.Event())
    engine = _engine(ws)
    engine.tts = tts  # type: ignore[assignment]
    task = asyncio.create_task(engine.run(ws))
    # tts_start is emitted BEFORE synthesize blocks on the gate, so the
    # engine is provably mid-TTS when we interrupt.
    assert await _wait_event(ws, "tts_start", ms=5000)
    ws.push_json({"type": "interrupt"})
    # The server must process the interrupt while TTS is still gated.
    assert await _wait_state_event(ws, "interrupted", ms=2000)
    assert await _wait_state(engine, ws, VoiceState.LISTENING)
    tts.gate.set()
    await asyncio.sleep(0.05)
    assert not ws.bytes_out, "stale TTS chunks sent after interrupt"
    await _cancel_task(task)


@pytest.mark.asyncio
async def test_interrupt_does_not_duplicate_question() -> None:
    ws = StubWS()
    tts = StubTTS(gate=asyncio.Event())
    engine = _engine(ws)
    engine.tts = tts  # type: ignore[assignment]
    task = asyncio.create_task(engine.run(ws))
    assert await _wait_event(ws, "tts_start", ms=5000)
    questions_before = [e for e in ws.json_out if e.get("type") == "question"]
    ws.push_json({"type": "interrupt"})
    assert await _wait_state_event(ws, "interrupted", ms=2000)
    tts.gate.set()
    await asyncio.sleep(0.05)
    questions_after = [e for e in ws.json_out if e.get("type") == "question"]
    assert len(questions_after) == len(questions_before)
    await _cancel_task(task)


@pytest.mark.asyncio
async def test_generation_bumped_on_interrupt() -> None:
    """H.7: interrupt must invalidate the current TTS generation."""
    ws = StubWS()
    tts = StubTTS(gate=asyncio.Event())
    engine = _engine(ws)
    engine.tts = tts  # type: ignore[assignment]
    task = asyncio.create_task(engine.run(ws))
    assert await _wait_event(ws, "tts_start", ms=5000)
    gen_before = engine._generation
    ws.push_json({"type": "interrupt"})
    assert await _wait_state_event(ws, "interrupted", ms=2000)
    assert engine._generation > gen_before, "generation must bump on interrupt"
    tts.gate.set()
    await _cancel_task(task)


@pytest.mark.asyncio
async def test_manual_end_turn_transcribes_and_evaluates() -> None:
    """H.2 manual: [Done speaking] -> final ASR -> answer -> eval -> next Q."""
    ws = StubWS()
    engine = _engine(ws)
    task = asyncio.create_task(engine.run(ws))
    assert await _wait_state(engine, ws, VoiceState.LISTENING)
    ws.push_bytes(b"\x00\x01" * 3200)
    ws.push_json({"type": "end_turn"})
    assert await _wait_event(ws, "evaluation", ms=5000)
    events = {e.get("type") for e in ws.json_out}
    assert "final_transcript" in events
    assert "answer_submitted" in events
    assert engine.interview.answer_texts == ["my spoken answer"]
    # Loop continues: a second question is asked.
    questions = [e for e in ws.json_out if e.get("type") == "question"]
    assert len(questions) >= 2
    await _cancel_task(task)


@pytest.mark.asyncio
async def test_auto_end_turn_on_silence() -> None:
    """H.2 automatic: speech detected, then silence -> turn finalizes."""
    ws = StubWS()
    engine = _engine(ws)
    task = asyncio.create_task(engine.run(ws))
    assert await _wait_state(engine, ws, VoiceState.LISTENING)
    # Loud audio (speech) then quiet audio (silence).
    ws.push_bytes(b"\x7f\x7f" * 3200)  # speech energy
    ws.push_bytes(b"\x00\x00" * 3200)  # silence begins
    assert await _wait_event(ws, "turn_ended", ms=5000)
    assert await _wait_event(ws, "final_transcript", ms=5000)
    assert engine.interview.answer_texts == ["my spoken answer"]
    await _cancel_task(task)


@pytest.mark.asyncio
async def test_pause_resume_stop() -> None:
    ws = StubWS()
    engine = _engine(ws)
    task = asyncio.create_task(engine.run(ws))
    assert await _wait_state(engine, ws, VoiceState.LISTENING)
    ws.push_json({"type": "pause"})
    assert await _wait_state(engine, ws, VoiceState.PAUSED)
    ws.push_json({"type": "resume"})
    assert await _wait_state(engine, ws, VoiceState.LISTENING)
    ws.push_json({"type": "stop"})
    assert await _wait_state(engine, ws, VoiceState.COMPLETED)
    assert engine.interview.answer_texts == []
    await _cancel_task(task)


@pytest.mark.asyncio
async def test_pause_during_speaking_cancels_tts() -> None:
    """Pause mid-TTS must cancel the stream and reach PAUSED."""
    ws = StubWS()
    tts = StubTTS(gate=asyncio.Event())
    engine = _engine(ws)
    engine.tts = tts  # type: ignore[assignment]
    task = asyncio.create_task(engine.run(ws))
    assert await _wait_event(ws, "tts_start", ms=5000)
    ws.push_json({"type": "pause"})
    assert await _wait_state(engine, ws, VoiceState.PAUSED)
    tts.gate.set()
    await asyncio.sleep(0.05)
    assert not ws.bytes_out, "TTS continued after pause"
    ws.push_json({"type": "resume"})
    assert await _wait_state(engine, ws, VoiceState.LISTENING)
    await _cancel_task(task)


@pytest.mark.asyncio
async def test_transcript_segments_persisted() -> None:
    """H.8: question + answer transcript rows are persisted per turn."""
    ws = StubWS()
    engine = _engine(ws)
    task = asyncio.create_task(engine.run(ws))
    assert await _wait_state(engine, ws, VoiceState.LISTENING)
    ws.push_bytes(b"\x00\x01" * 3200)
    ws.push_json({"type": "end_turn"})
    assert await _wait_event(ws, "evaluation", ms=5000)
    await asyncio.sleep(0.05)
    segments = engine._transcripts.segments
    texts = [s["text"] for s in segments]
    assert any("Tell me about" in t for t in texts), "question transcript missing"
    assert any(t == "my spoken answer" for t in texts), "answer transcript missing"
    await _cancel_task(task)


@pytest.mark.asyncio
async def test_cancel_reaches_cancelled() -> None:
    ws = StubWS()
    engine = _engine(ws)
    task = asyncio.create_task(engine.run(ws))
    assert await _wait_state(engine, ws, VoiceState.LISTENING)
    ws.push_json({"type": "cancel"})
    assert await _wait_state(engine, ws, VoiceState.CANCELLED)
    await _cancel_task(task)
