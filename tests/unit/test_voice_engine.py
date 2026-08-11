"""VoiceEngine unit tests: state machine, interruption, turn loop.

Uses stub ASR/TTS and a stub WebSocket; no real oMLX, no DB (the interview
service is stubbed at the engine seam via a fake interview object).
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

    async def synthesize(self, text: str) -> tuple[bytes, int]:
        self.synthesizes.append(text)
        return self.pcm, self.sr


class StubInterview:
    """Seam-stub of InterviewService surface used by the engine."""

    def __init__(self) -> None:
        self.started = False
        self.next_question_text = "Tell me about a hard problem you solved."
        self.question_seq = 0
        self.answer_texts: list[str] = []
        self.overall = 6.5

    async def begin(self, session_id: int, user_id: int) -> object:
        self.started = True
        return object()

    async def next_question(self, session_id: int, user_id: int) -> tuple[object, object]:
        self.question_seq += 1
        q = type(
            "Q",
            (),  # noqa: UP014 — dynamic stub type
            {"id": self.question_seq, "text": self.next_question_text, "difficulty": "medium"},
        )()
        turn = type("T", (), {})()
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
        return type("A", (), {"id": 1})()

    async def stop(self, session_id: int, user_id: int) -> object:
        return object()

    async def cancel(self, session_id: int, user_id: int) -> object:
        return object()

    class _Repo:
        async def get_or_raise(self, obj_id: int, *, name: str | None = None) -> object:
            return type("S", (), {"user_id": 1, "status": type("St", (), {"value": "created"})()})()

        async def get_by_answer(self, answer_id: int) -> object | None:
            return type("E", (), {"overall": 6.5})()

    sessions = _Repo()
    evaluations = _Repo()


def _engine(ws: StubWS) -> VoiceEngine:
    return VoiceEngine(
        interview=StubInterview(),  # type: ignore[arg-type]
        asr=StubASR(),  # type: ignore[arg-type]
        tts=StubTTS(),  # type: ignore[arg-type]
        session_id=7,
        user_id=1,
        ws=ws,
    )


async def _run_until(engine: VoiceEngine, ws: StubWS, target: VoiceState) -> None:
    """Run the engine loop until the target state is observed (or inbox empty)."""
    task = asyncio.create_task(engine.run(ws))
    for _ in range(200):
        if engine.state == target:
            break
        if not ws.inbox and engine.state == target:
            break
        await asyncio.sleep(0.005)
    task.cancel()
    try:
        await task
    except (asyncio.CancelledError, RuntimeError):
        pass


def _states(ws: StubWS) -> list[str]:
    return [str(e["state"]) for e in ws.json_out if e.get("type") == "state"]


@pytest.mark.asyncio
async def test_engine_streams_question_then_listens() -> None:
    ws = StubWS()
    engine = _engine(ws)
    task = asyncio.create_task(engine.run(ws))
    for _ in range(500):
        if engine.state in (VoiceState.LISTENING, VoiceState.SPEAKING) and ws.bytes_out:
            break
        await asyncio.sleep(0.005)
    # Question event emitted before audio.
    questions = [e for e in ws.json_out if e.get("type") == "question"]
    assert questions, "expected question event"
    assert questions[0]["text"] == "Tell me about a hard problem you solved."
    # TTS audio streamed as bytes.
    assert ws.bytes_out, "expected TTS audio chunks"
    # Engine settled in listening after speaking.
    for _ in range(200):
        if engine.state == VoiceState.LISTENING:
            break
        await asyncio.sleep(0.005)
    assert engine.state == VoiceState.LISTENING
    task.cancel()
    try:
        await task
    except (asyncio.CancelledError, RuntimeError):
        pass


@pytest.mark.asyncio
async def test_end_turn_transcribes_and_evaluates() -> None:
    ws = StubWS()
    engine = _engine(ws)
    asr = engine.asr
    task = asyncio.create_task(engine.run(ws))
    for _ in range(500):
        if engine.state == VoiceState.LISTENING:
            break
        await asyncio.sleep(0.005)
    # Send audio then end the turn.
    ws.push_bytes(b"\x00\x01" * 1600)
    ws.push_json({"type": "end_turn"})
    for _ in range(800):
        if any(e.get("type") == "evaluation" for e in ws.json_out):
            break
        await asyncio.sleep(0.005)
    events = {e.get("type") for e in ws.json_out}
    assert "final_transcript" in events
    assert "evaluation" in events
    assert asr.calls, "ASR should have been called"
    assert engine.interview.answer_texts == ["my spoken answer"]
    # Loop continues: a second question was asked.
    questions = [e for e in ws.json_out if e.get("type") == "question"]
    assert len(questions) >= 2
    task.cancel()
    try:
        await task
    except (asyncio.CancelledError, RuntimeError):
        pass


@pytest.mark.asyncio
async def test_interrupt_cancels_tts_and_does_not_repeat_question() -> None:
    ws = StubWS()
    engine = _engine(ws)
    task = asyncio.create_task(engine.run(ws))
    for _ in range(500):
        if engine.state in (VoiceState.SPEAKING, VoiceState.LISTENING):
            break
        await asyncio.sleep(0.005)
    questions_before = [e for e in ws.json_out if e.get("type") == "question"]
    ws.push_json({"type": "interrupt"})
    for _ in range(300):
        if engine.state == VoiceState.LISTENING:
            break
        await asyncio.sleep(0.005)
    assert engine.state == VoiceState.LISTENING
    questions_after = [e for e in ws.json_out if e.get("type") == "question"]
    assert len(questions_after) == len(questions_before), (
        "interrupt must not duplicate the question"
    )
    task.cancel()
    try:
        await task
    except (asyncio.CancelledError, RuntimeError):
        pass


@pytest.mark.asyncio
async def test_pause_resume_stop() -> None:
    ws = StubWS()
    engine = _engine(ws)
    task = asyncio.create_task(engine.run(ws))
    for _ in range(500):
        if engine.state == VoiceState.LISTENING:
            break
        await asyncio.sleep(0.005)
    ws.push_json({"type": "pause"})
    for _ in range(200):
        if engine.state == VoiceState.PAUSED:
            break
        await asyncio.sleep(0.005)
    assert engine.state == VoiceState.PAUSED
    ws.push_json({"type": "resume"})
    for _ in range(200):
        if engine.state == VoiceState.LISTENING:
            break
        await asyncio.sleep(0.005)
    assert engine.state == VoiceState.LISTENING
    ws.push_json({"type": "stop"})
    for _ in range(300):
        if engine.state == VoiceState.COMPLETED:
            break
        await asyncio.sleep(0.005)
    assert engine.state == VoiceState.COMPLETED
    assert engine.interview.answer_texts == []
    task.cancel()
    try:
        await task
    except (asyncio.CancelledError, RuntimeError):
        pass
