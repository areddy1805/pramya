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
    calls: list[str] = field(default_factory=list)  # ordered: warmup/synthesize

    async def synthesize(self, text: str) -> tuple[bytes, int]:
        self.synthesizes.append(text)
        self.calls.append(f"syn:{text}")
        if self.gate is not None:
            await self.gate.wait()
        return self.pcm, self.sr

    async def synthesize_stream(self, text: str, *, streaming_interval: float = 1.0):
        """Streaming surface: yields PCM in 200ms (9600-byte) frames."""
        self.synthesizes.append(text)
        self.calls.append(f"syn:{text}")
        if self.gate is not None:
            await self.gate.wait()
        for i in range(0, len(self.pcm), 9600):
            if self.gate is not None and not self.gate.is_set():
                await self.gate.wait()
            yield self.pcm[i : i + 9600]
            if self.chunk_delay:
                await asyncio.sleep(self.chunk_delay)

    async def warmup(self) -> None:
        self.calls.append("warmup")


class StubTranscripts:
    def __init__(self) -> None:
        self.segments: list[dict[str, object]] = []

    async def max_seq_for_turn(self, turn_id: int) -> int:
        return sum(1 for s in self.segments if s.get("turn_id") == turn_id)

    async def add(self, obj: object) -> None:
        turn_id = obj.turn_id  # type: ignore[attr-defined]
        text = obj.text  # type: ignore[attr-defined]
        timestamps = getattr(obj, "timestamps", None)
        speaker = getattr(obj, "speaker", "unknown")
        self.segments.append(
            {"turn_id": turn_id, "text": text, "timestamps": timestamps, "speaker": speaker}
        )


class StubAudios:
    """Captures AudioSegment rows written by the engine (Phase H)."""

    def __init__(self) -> None:
        self.added: list[object] = []

    async def add(self, obj: object) -> None:
        self.added.append(obj)


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
        self.next_question_stream_tokens = ["Tell me about a ", "hard problem ", "you solved."]
        self.question_seq = 0
        self.turn_seq = 0
        self.answer_texts: list[str] = []
        self.overall = 6.5
        self.session = _AsyncNoopSession()
        self.session_status = "created"
        self.last_question_text = "Tell me about a hard problem you solved."
        self.sessions = self._Sessions(self)
        self.questions = self._Questions(self)
        self.turns = self._Turns()
        self.evaluations = _Evaluations()

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

    async def next_question_streaming(self, session_id: int, user_id: int):
        """Streaming seam: tokens then the persisted question pair."""
        self.question_seq += 1
        self.turn_seq += 1
        # Stream the question text in word-ish chunks so the segmenter sees a
        # realistic token stream.
        for tok in self.next_question_stream_tokens:
            yield ("token", tok)
        q = type(
            "Q",
            (),
            {"id": self.question_seq, "text": self.next_question_text, "difficulty": "medium"},
        )()
        turn = type("T", (), {"id": self.turn_seq})()
        yield ("question", (q, turn))

    async def submit_answer(
        self,
        session_id: int,
        user_id: int,
        *,
        question_id: int,
        answer_text: str,
        idempotency_key: str | None,
        mode: str,
        await_evaluation: bool = True,
    ) -> object:
        self.answer_texts.append(answer_text)
        self.turn_seq += 1
        return type("A", (), {"id": 1})()

    async def evaluate_answer(
        self,
        session_id: int,
        user_id: int,
        *,
        question_id: int,
        answer_text: str,
        hints_used: int = 0,
    ) -> object:
        return type("E", (), {"overall": self.overall})()

    async def stop(self, session_id: int, user_id: int) -> object:
        return object()

    async def cancel(self, session_id: int, user_id: int) -> object:
        return object()

    class _Sessions:
        def __init__(self, interview: StubInterview) -> None:
            self._interview = interview

        async def get_or_raise(self, obj_id: int, *, name: str | None = None) -> object:
            return type("S", (), {"user_id": 1, "status": self._interview.session_status})()

    class _Turns:
        async def latest_for_session(self, session_id: int) -> object:
            return type("T", (), {"id": 99})()

    class _Questions:
        def __init__(self, interview: StubInterview) -> None:
            self._interview = interview

        async def list_for_session(self, session_id: int) -> list[object]:
            return [type("Q", (), {"text": self._interview.last_question_text})()]


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
        playback_timeout_seconds=0.5,  # fast failure-mode guard in tests
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


async def _open_listening(ws: StubWS, engine: VoiceEngine, ms: int = 3000) -> None:
    """Confirm playback completion so the engine opens the listening window."""
    if engine.state is VoiceState.LISTENING:
        return
    if not await _wait_event(ws, "tts_stop", ms=ms):
        raise AssertionError("no tts_stop received")
    gen = next(e["generation"] for e in ws.json_out if e.get("type") == "tts_stop")
    ws.push_json({"type": "playback_complete", "generation": gen})
    if not await _wait_state(engine, ws, VoiceState.LISTENING, ms=ms):
        raise AssertionError("engine did not reach LISTENING after playback_complete")


async def _cancel_task(task: asyncio.Task[None]) -> None:
    task.cancel()
    try:
        await task
    except (asyncio.CancelledError, RuntimeError):
        pass


@pytest.mark.asyncio
async def test_engine_streams_question_then_listens_after_playback_complete() -> None:
    """Speaker-integrity contract: tts_stop does NOT open listening.

    The engine must stay SPEAKING until the client confirms ACTUAL playback
    completion (playback_complete). The physical-mic defect — interviewer
    audio captured as a candidate answer — is impossible while LISTENING is
    only reachable via playback confirmation (or the failure-mode guard).
    """
    ws = StubWS()
    engine = _engine(ws)
    task = asyncio.create_task(engine.run(ws))
    assert await _wait_event(ws, "question", ms=5000)
    assert ws.bytes_out, "expected TTS audio chunks"
    assert await _wait_event(ws, "tts_stop", ms=5000)
    # Defect regression: after tts_stop the engine must NOT be listening yet.
    await asyncio.sleep(0.05)
    assert engine.state is VoiceState.SPEAKING, (
        "LISTENING must not begin on tts_stop alone (playback may still sound)"
    )
    assert "listening" not in _states(ws)
    # Mic frames during SPEAKING are discarded, never ASR'd.
    ws.push_bytes(b"\x7f\x7f" * 3200)
    await asyncio.sleep(0.05)
    assert engine._discarded_tts_frames >= 1
    assert engine.asr.calls == []  # type: ignore[attr-defined]  # no candidate ASR
    # Playback confirmation opens the authoritative listening window.
    gen = next(e["generation"] for e in ws.json_out if e.get("type") == "tts_stop")
    ws.push_json({"type": "playback_complete", "generation": gen})
    assert await _wait_state(engine, ws, VoiceState.LISTENING)
    ws.push_bytes(b"\x00\x01" * 3200)
    ws.push_json({"type": "end_turn"})
    assert await _wait_event(ws, "final_transcript", ms=5000)
    assert engine.asr.calls, "candidate frames must reach ASR after playback_complete"  # type: ignore[attr-defined]
    assert engine.interview.answer_texts == ["my spoken answer"]
    questions = [e for e in ws.json_out if e.get("type") == "question"]
    assert questions[0]["text"] == "Tell me about a hard problem you solved."
    assert "tts_start" in {e.get("type") for e in ws.json_out}
    await _cancel_task(task)


@pytest.mark.asyncio
async def test_stale_playback_complete_ignored() -> None:
    """A delayed playback_complete from a previous generation must not open
    the mic window (generation-gated handshake)."""
    ws = StubWS()
    engine = _engine(ws)
    task = asyncio.create_task(engine.run(ws))
    assert await _wait_event(ws, "tts_stop", ms=5000)
    assert await _wait_state(engine, ws, VoiceState.SPEAKING)
    gen = next(e["generation"] for e in ws.json_out if e.get("type") == "tts_stop")
    ws.push_json({"type": "playback_complete", "generation": gen + 99})
    await asyncio.sleep(0.05)
    assert engine.state is VoiceState.SPEAKING, "stale generation must not unlock capture"
    await _cancel_task(task)


@pytest.mark.asyncio
async def test_playback_timeout_guard_opens_listening() -> None:
    """Failure-mode guard: a dead client must not deadlock the session. The
    guard is NOT the enabling mechanism — normal flow is playback_complete."""
    ws = StubWS()
    engine = _engine(ws)
    task = asyncio.create_task(engine.run(ws))
    assert await _wait_event(ws, "tts_stop", ms=5000)
    assert await _wait_state(engine, ws, VoiceState.SPEAKING)
    assert await _wait_state(engine, ws, VoiceState.LISTENING, ms=2000)  # guard fires
    assert engine._playback_confirmed is False
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
    await _open_listening(ws, engine)
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
    await _open_listening(ws, engine)
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
    await _open_listening(ws, engine)
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
    await _open_listening(ws, engine)
    ws.push_bytes(b"\x00\x01" * 3200)
    ws.push_json({"type": "end_turn"})
    assert await _wait_event(ws, "evaluation", ms=5000)
    await asyncio.sleep(0.05)
    segments = engine._transcripts.segments
    texts = [s["text"] for s in segments]
    assert any("Tell me about" in t for t in texts), "question transcript missing"
    assert any(t == "my spoken answer" for t in texts), "answer transcript missing"
    # Speaker integrity (C/D): interviewer question and candidate answer must
    # carry unambiguous, distinct speaker identity — never merged.
    q = next(s for s in segments if "Tell me about" in s["text"])
    a = next(s for s in segments if s["text"] == "my spoken answer")
    assert q["speaker"] == "interviewer", "question must be interviewer"
    assert a["speaker"] == "candidate", "answer must be candidate"
    assert a["timestamps"]["role"] == "candidate"
    await _cancel_task(task)


@pytest.mark.asyncio
async def test_cancel_reaches_cancelled() -> None:
    ws = StubWS()
    engine = _engine(ws)
    task = asyncio.create_task(engine.run(ws))
    await _open_listening(ws, engine)
    ws.push_json({"type": "cancel"})
    assert await _wait_state(engine, ws, VoiceState.CANCELLED)
    await _cancel_task(task)


@pytest.mark.asyncio
async def test_heartbeat_ack_returns_state() -> None:
    """Phase H: heartbeat control is answered with the authoritative state."""
    ws = StubWS()
    engine = _engine(ws)
    task = asyncio.create_task(engine.run(ws))
    await _open_listening(ws, engine)
    ws.push_json({"type": "heartbeat"})
    assert await _wait_event(ws, "heartbeat_ack", ms=3000)
    ack = [e for e in ws.json_out if e.get("type") == "heartbeat_ack"][-1]
    assert ack.get("state") == "listening"
    await _cancel_task(task)


@pytest.mark.asyncio
async def test_reconnect_emits_resume_with_last_question() -> None:
    """Phase H: connecting to an in-progress session resyncs the client."""
    ws = StubWS()
    engine = _engine(ws)
    engine.interview.session_status = "questioning"  # type: ignore[attr-defined]
    task = asyncio.create_task(engine.run(ws))
    assert await _wait_event(ws, "resume", ms=5000)
    resume = [e for e in ws.json_out if e.get("type") == "resume"][0]
    assert resume.get("question") == "Tell me about a hard problem you solved."
    assert engine.interview.started is False  # never re-begins an active session
    await _cancel_task(task)


@pytest.mark.asyncio
async def test_answer_audio_persisted_when_store_enabled(tmp_path) -> None:
    """Phase H: candidate audio is written as WAV + audio_segment row."""
    ws = StubWS()
    interview = StubInterview()
    audios = StubAudios()
    engine = VoiceEngine(
        interview=interview,  # type: ignore[arg-type]
        asr=StubASR(),  # type: ignore[arg-type]
        tts=StubTTS(),  # type: ignore[arg-type]
        session_id=7,
        user_id=1,
        ws=ws,
        silence_seconds=0.05,
        speech_rms=10.0,
        transcripts=StubTranscripts(),  # type: ignore[arg-type]
        audios=audios,  # type: ignore[arg-type]
        audio_storage_dir=str(tmp_path),
        store_audio=True,
        retention_days=30,
    )
    task = asyncio.create_task(engine.run(ws))
    await _open_listening(ws, engine)
    ws.push_bytes(b"\x00\x01" * 3200)
    ws.push_json({"type": "end_turn"})
    assert await _wait_event(ws, "answer_submitted", ms=5000)
    await asyncio.sleep(0.05)
    assert len(audios.added) == 1
    row = audios.added[0]
    assert row.storage_key == "7/99.wav"  # type: ignore[attr-defined]
    assert row.duration_ms == 200  # type: ignore[attr-defined]  # 3200 samples @16k
    assert row.retention_until is not None  # type: ignore[attr-defined]
    stored = tmp_path / "7" / "99.wav"
    assert stored.is_file() and stored.stat().st_size > 44  # valid WAV header + data
    # Answer transcript now carries measured timestamps (role + latency).
    cand = [s for s in engine._transcripts.segments if s.get("text") == "my spoken answer"]
    assert cand and cand[0]["timestamps"], "answer timestamps missing"
    assert cand[0]["timestamps"]["role"] == "candidate"
    assert "response_latency_ms" in cand[0]["timestamps"]
    await _cancel_task(task)


@pytest.mark.asyncio
async def test_audio_not_stored_when_disabled(tmp_path) -> None:
    """Phase H: store_audio=False skips disk + rows (opt-out path)."""
    ws = StubWS()
    audios = StubAudios()
    engine = VoiceEngine(
        interview=StubInterview(),  # type: ignore[arg-type]
        asr=StubASR(),  # type: ignore[arg-type]
        tts=StubTTS(),  # type: ignore[arg-type]
        session_id=7,
        user_id=1,
        ws=ws,
        silence_seconds=0.05,
        speech_rms=10.0,
        transcripts=StubTranscripts(),  # type: ignore[arg-type]
        audios=audios,  # type: ignore[arg-type]
        audio_storage_dir=str(tmp_path),
        store_audio=False,
    )
    task = asyncio.create_task(engine.run(ws))
    await _open_listening(ws, engine)
    ws.push_bytes(b"\x00\x01" * 3200)
    ws.push_json({"type": "end_turn"})
    assert await _wait_event(ws, "answer_submitted", ms=5000)
    await asyncio.sleep(0.05)
    assert audios.added == []
    await _cancel_task(task)


# -- physical-microphone speaker-integrity (Phase N) -------------------------


@pytest.mark.asyncio
async def test_mic_frames_during_paused_discarded() -> None:
    """G: mic gating stays correct across pause — frames sent while PAUSED
    are discarded, never accepted into an answer window."""
    ws = StubWS()
    engine = _engine(ws)
    task = asyncio.create_task(engine.run(ws))
    await _open_listening(ws, engine)
    ws.push_bytes(b"\x00\x01" * 3200)
    for _ in range(200):
        if engine._accepted_frames >= 1:
            break
        await asyncio.sleep(0.005)
    assert engine._accepted_frames == 1
    ws.push_json({"type": "pause"})
    assert await _wait_state(engine, ws, VoiceState.PAUSED)
    ws.push_bytes(b"\x7f\x7f" * 3200)
    await asyncio.sleep(0.03)
    assert engine._discarded_other_frames >= 1, "frames during PAUSED must be discarded"
    # Resume reopens the listening window (counters reset per window).
    ws.push_json({"type": "resume"})
    assert await _wait_state(engine, ws, VoiceState.LISTENING)
    ws.push_bytes(b"\x00\x01" * 3200)
    for _ in range(200):
        if engine._accepted_frames >= 1:
            break
        await asyncio.sleep(0.005)
    assert engine._accepted_frames == 1, "resume reopened capture cleanly"
    await _cancel_task(task)


@pytest.mark.asyncio
async def test_stop_cancel_rejects_frames() -> None:
    """H: stop/cancel terminate capture — later frames are never ASR'd."""
    ws = StubWS()
    engine = _engine(ws)
    task = asyncio.create_task(engine.run(ws))
    await _open_listening(ws, engine)
    ws.push_json({"type": "stop"})
    assert await _wait_state(engine, ws, VoiceState.COMPLETED)
    asr_calls_before = len(engine.asr.calls)  # type: ignore[attr-defined]
    ws.push_bytes(b"\x7f\x7f" * 3200)
    ws.push_json({"type": "end_turn"})
    await asyncio.sleep(0.05)
    assert len(engine.asr.calls) == asr_calls_before  # type: ignore[attr-defined]
    assert engine.interview.answer_texts == []
    await _cancel_task(task)


@pytest.mark.asyncio
async def test_barge_in_interrupt_discards_playback_residue() -> None:
    """E: explicit barge-in mid-TTS cancels synthesis, clears accumulated
    audio, and opens a clean candidate window — pre-interrupt frames (the
    interviewer's own playback picked up by the mic) never become the answer."""
    ws = StubWS()
    tts = StubTTS(gate=asyncio.Event())
    engine = _engine(ws)
    engine.tts = tts  # type: ignore[assignment]
    task = asyncio.create_task(engine.run(ws))
    assert await _wait_event(ws, "tts_start", ms=5000)
    # Interviewer-playback frames leak into the mic during SPEAKING...
    ws.push_bytes(b"\x7f\x7f" * 3200)
    await asyncio.sleep(0.02)
    assert engine._discarded_tts_frames >= 1
    # ...and the candidate barges in explicitly.
    ws.push_json({"type": "interrupt"})
    assert await _wait_state_event(ws, "interrupted", ms=2000)
    assert await _wait_state(engine, ws, VoiceState.LISTENING)
    tts.gate.set()
    await asyncio.sleep(0.05)
    # Candidate speech after the interrupt is accepted as the answer.
    ws.push_bytes(b"\x00\x01" * 3200)
    ws.push_json({"type": "end_turn"})
    assert await _wait_event(ws, "evaluation", ms=5000)
    assert engine.interview.answer_texts == ["my spoken answer"]
    # The answer audio is the POST-interrupt window only (buffer was cleared).
    assert engine.asr.calls and len(engine.asr.calls[-1]) == 3200 * 2  # type: ignore[attr-defined]
    await _cancel_task(task)


@pytest.mark.asyncio
async def test_voice_barge_in_optin_detects_sustained_speech_during_tts() -> None:
    """Opt-in voice-triggered barge-in: sustained mic energy during SPEAKING
    cancels TTS and opens listening (explicit, threshold-gated detection)."""
    ws = StubWS()
    tts = StubTTS(gate=asyncio.Event())
    engine = _engine(ws)
    engine.tts = tts  # type: ignore[assignment]
    engine.barge_in_enabled = True
    engine.barge_in_rms = 100.0  # low threshold for the test
    engine.barge_in_ms = 40.0
    task = asyncio.create_task(engine.run(ws))
    assert await _wait_event(ws, "tts_start", ms=5000)
    # Sustained loud mic frames while the interviewer is speaking.
    for _ in range(20):
        ws.push_bytes(b"\x7f\x7f" * 1600)
        await asyncio.sleep(0.01)
    assert await _wait_state_event(ws, "interrupted", ms=2000)
    assert await _wait_state(engine, ws, VoiceState.LISTENING)
    assert engine._interruptions == 1
    tts.gate.set()
    await _cancel_task(task)


@pytest.mark.asyncio
async def test_reconnect_restores_state_with_mic_gating() -> None:
    """F: reconnect to an in-progress session restores LISTENING (no playback
    in flight) and capture is accepted only in that authoritative state."""
    ws = StubWS()
    engine = _engine(ws)
    engine.interview.session_status = "questioning"  # type: ignore[attr-defined]
    task = asyncio.create_task(engine.run(ws))
    assert await _wait_event(ws, "resume", ms=5000)
    assert await _wait_state(engine, ws, VoiceState.LISTENING)
    ws.push_bytes(b"\x00\x01" * 3200)
    ws.push_json({"type": "end_turn"})
    assert await _wait_event(ws, "final_transcript", ms=5000)
    assert engine.asr.calls, "mic frames accepted after reconnect in LISTENING"  # type: ignore[attr-defined]
    assert engine._playback_confirmed is True
    await _cancel_task(task)


@pytest.mark.asyncio
async def test_long_run_multi_turn_endurance() -> None:
    """Long-running interview: 40 consecutive Q/A turns must keep the engine
    state bounded — no task accumulation, audio buffers cleared per turn,
    per-turn transcripts persisted, generation counter monotonic."""
    ws = StubWS()
    engine = _engine(ws)
    engine.playback_timeout_seconds = 0.2  # fast turn cycling in tests
    task = asyncio.create_task(engine.run(ws))
    assert await _wait_event(ws, "question", ms=5000)
    for turn in range(40):
        # Open the listening window via the real handshake.
        await _open_listening(ws, engine, ms=2000)
        ws.push_bytes(b"\x00\x01" * 3200)
        ws.push_json({"type": "end_turn"})
        # R11: EVERY answer must produce its own deferred evaluation event
        # (per-answer dedup, not a one-shot evaluation flag).
        for _ in range(1000):
            evals = [e for e in ws.json_out if e.get("type") == "evaluation"]
            if len(evals) >= turn + 1:
                break
            await asyncio.sleep(0.005)
        else:
            raise AssertionError(f"no evaluation on turn {turn}")
        # Let the next-question pipeline settle.
        for _ in range(200):
            if len([e for e in ws.json_out if e.get("type") == "question"]) >= turn + 2:
                break
            await asyncio.sleep(0.005)
    # State invariants after 40 turns.
    assert engine._turns_completed == 40
    assert engine._audio_buf == bytearray(), "audio buffer must be empty between turns"
    # 40 candidate answers persisted with unambiguous speaker identity; the
    # interviewer side has 40+ (a 41st question may already be asked).
    for _ in range(400):
        if (
            len([sg for sg in engine._transcripts.segments if sg.get("speaker") == "candidate"])
            >= 40
        ):
            break
        await asyncio.sleep(0.005)
    cands = [sg for sg in engine._transcripts.segments if sg.get("speaker") == "candidate"]
    inters = [sg for sg in engine._transcripts.segments if sg.get("speaker") == "interviewer"]
    assert len(cands) == 40, f"candidate segments: {len(cands)}"
    assert len(inters) >= 40, f"interviewer segments: {len(inters)}"
    assert all(sg["speaker"] in ("interviewer", "candidate") for sg in engine._transcripts.segments)
    # No orphaned background tasks beyond the expected set.
    expected = {
        engine._tts_task,
        engine._answer_task,
        engine._start_session_task,
        engine._silence_task,
    }
    alive = [t for t in expected if t is not None and not t.done()]
    assert len(alive) <= 2, f"leaked tasks: {len(alive)}"
    # Generations strictly increase per TTS stream (no reuse).
    gens = [e.get("generation") for e in ws.json_out if e.get("type") == "tts_start"]
    assert gens == sorted(gens) and len(gens) == len(set(gens)), "generation must be monotonic"
    await _cancel_task(task)


@pytest.mark.asyncio
async def test_tts_warmup_precedes_first_synthesis() -> None:
    """R4 regression: the TTS model is warmed (awaited) BEFORE the first
    question pipeline synthesizes, so the first real synthesis never queues
    behind the warmup request on the serialized oMLX slot."""
    ws = StubWS()
    tts = StubTTS()
    engine = _engine(ws)
    engine.tts = tts  # type: ignore[assignment]
    task = asyncio.create_task(engine.run(ws))
    assert await _wait_event(ws, "question", ms=5000)
    # The worker synthesizes the first flushed segment right after the
    # question event; poll until it has run.
    for _ in range(400):
        if any(c.startswith("syn:") for c in tts.calls):
            break
        await asyncio.sleep(0.005)
    await _cancel_task(task)
    assert tts.calls and tts.calls[0] == "warmup", f"expected warmup first, got {tts.calls}"
    assert any(c.startswith("syn:") for c in tts.calls)
    warmup_idx = tts.calls.index("warmup")
    syn_idxs = [i for i, c in enumerate(tts.calls) if c.startswith("syn:")]
    assert syn_idxs and warmup_idx < syn_idxs[0]


@pytest.mark.asyncio
async def test_stop_mid_tts_halts_all_audio_sends() -> None:
    """P0: stopping the interview while the interviewer is mid-TTS must halt
    the audio sender immediately — no further bytes reach the browser even
    if synthesis had buffered more audio."""
    ws = StubWS()
    tts = StubTTS(gate=asyncio.Event())
    engine = _engine(ws)
    engine.tts = tts  # type: ignore[assignment]
    engine.playback_timeout_seconds = 0.2
    task = asyncio.create_task(engine.run(ws))
    assert await _wait_event(ws, "tts_start", ms=5000)
    # Let the producer enqueue a few frames, then stop mid-speech.
    await asyncio.sleep(0.05)
    ws.push_json({"type": "stop"})
    assert await _wait_state(engine, ws, VoiceState.COMPLETED, ms=3000)
    sent_before = len(ws.bytes_out)
    # Release the synthesis gate: any frames still in the pipeline must NOT
    # be transmitted after the session is completed.
    tts.gate.set()
    await asyncio.sleep(0.1)
    assert len(ws.bytes_out) == sent_before, "audio sent after stop"
    assert engine._generation >= 1  # generation invalidated
    await _cancel_task(task)


@pytest.mark.asyncio
async def test_cancel_mid_tts_halts_all_audio_sends() -> None:
    """P0: cancelling the interview mid-TTS halts the audio sender too."""
    ws = StubWS()
    tts = StubTTS(gate=asyncio.Event())
    engine = _engine(ws)
    engine.tts = tts  # type: ignore[assignment]
    engine.playback_timeout_seconds = 0.2
    task = asyncio.create_task(engine.run(ws))
    assert await _wait_event(ws, "tts_start", ms=5000)
    await asyncio.sleep(0.05)
    ws.push_json({"type": "cancel"})
    assert await _wait_state(engine, ws, VoiceState.CANCELLED, ms=3000)
    sent_before = len(ws.bytes_out)
    tts.gate.set()
    await asyncio.sleep(0.1)
    assert len(ws.bytes_out) == sent_before, "audio sent after cancel"
    await _cancel_task(task)
