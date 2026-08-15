"""VoiceEngine — concurrent, server-authoritative voice interview machine.

States (mirror app.domain.enums.VoiceState): idle -> starting -> speaking ->
listening -> processing -> speaking, with asynchronous side transitions
(interrupt -> listening, pause -> paused, resume -> active, stop/cancel ->
completed/cancelled). The server is the single source of truth and
broadcasts every transition as a JSON `state` event.

CRITICAL concurrency property (H.1): the WebSocket receive loop NEVER waits
for TTS, ASR, DeepSeek, or DB writes. Long-running work runs in background
tasks (_tts_task, _answer_task); the receive loop stays hot so interrupt /
pause / stop / end_turn are always observable.

Turn finalization (H.2) has two mechanisms:
  automatic — RMS energy detects speech; when speech ends and silence
              exceeds voice_silence_seconds, the turn auto-finalizes;
  manual    — client sends {"type": "end_turn"} ([Done speaking]).

Generation IDs (H.7): every TTS stream carries a generation id; stale
chunks from an older generation are dropped both server-side (checked
before each send) and client-side (state/generation gates).

Persistence (H.8): each completed turn writes TranscriptSegment rows for
the interviewer question and the candidate final transcript.
"""

from __future__ import annotations

import asyncio
import json
import math
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast

from app.core.logging import get_logger
from app.domain.enums import TurnDirection, VoiceState
from app.domain.errors import (
    InterviewStateError,
    NotFoundError,
    PramyaError,
    ValidationFailedError,
)
from app.interview.service import InterviewService
from app.models.interview import AudioSegment, TranscriptSegment
from app.repositories.interview import AudioSegmentRepository, TranscriptSegmentRepository
from app.voice.asr import ASRClient
from app.voice.profile import InterviewerVoiceProfile
from app.voice.segmenter import QuestionStreamExtractor, TextSegmenter
from app.voice.tts import TTSSynthesizer

_logger = get_logger("app.voice.engine")

# Minimum accumulation (samples @16kHz) between partial ASR calls.
PARTIAL_INTERVAL_SAMPLES = 32000  # 2.0 s


def _pcm16_duration_ms(pcm16: bytes, sample_rate: int) -> int:
    """Duration of a PCM16 buffer in ms (bytes / 2 = samples)."""
    samples = len(pcm16) // 2
    return round(samples * 1000 / sample_rate)


class VoiceWS:
    """Minimal WebSocket surface used by the engine (testable via stub)."""

    async def receive(self) -> tuple[str, Any]:  # ("json"|"bytes", payload)
        raise NotImplementedError

    async def send_json(self, payload: dict[str, Any]) -> None:
        raise NotImplementedError

    async def send_bytes(self, payload: bytes) -> None:
        raise NotImplementedError

    async def close(self, code: int = 1000) -> None:
        raise NotImplementedError


def _rms(pcm16: bytes) -> float:
    """RMS energy of PCM16 mono samples (0-32767 scale)."""
    if not pcm16:
        return 0.0
    n = len(pcm16) // 2
    if n == 0:
        return 0.0
    samples = cast(Any, pcm16)
    total = 0
    for i in range(0, len(samples) - 1, 2):
        raw = samples[i] | (samples[i + 1] << 8)
        if raw >= 0x8000:
            raw -= 0x10000
        total += raw * raw
    return math.sqrt(total / n)


@dataclass
class VoiceTurnResult:
    """Outcome of one voice turn (exposed for tests/logs)."""

    transcript: str
    evaluation_overall: float | None = None
    next_question: str | None = None
    turns_completed: int = 0


@dataclass
class VoiceEngine:
    """Runs one voice interview session over a WebSocket."""

    interview: InterviewService
    asr: ASRClient
    tts: TTSSynthesizer
    session_id: int
    user_id: int
    chunk_samples: int = 4800  # 200 ms @ 24 kHz playback chunks
    partial_interval_samples: int = PARTIAL_INTERVAL_SAMPLES
    asr_sample_rate: int = 16000
    tts_sample_rate: int = 24000
    silence_seconds: float = 1.5
    speech_rms: float = 400.0
    ws: VoiceWS | None = None
    transcripts: TranscriptSegmentRepository | None = None  # injectable (tests)
    # Audio persistence (Phase H): candidate audio stored as WAV + audio_segment
    # rows when store_audio is true and a storage dir is configured.
    audios: AudioSegmentRepository | None = None  # injectable (tests)
    audio_storage_dir: str | None = None
    store_audio: bool = True
    retention_days: int = 30
    # Playback-completion gating (physical-mic speaker integrity): the engine
    # stays SPEAKING after tts_stop until the client confirms ACTUAL playback
    # completion (playback_complete control). The timeout is a failure-mode
    # guard for dead/glitched clients — never the enabling mechanism.
    playback_timeout_seconds: float = 45.0
    # Voice-triggered barge-in: sustained mic energy during SPEAKING above
    # barge_in_rms cancels TTS and opens listening. The explicit 'interrupt'
    # control remains the guaranteed barge-in path.
    barge_in_enabled: bool = False
    barge_in_rms: float = 900.0
    barge_in_ms: float = 250.0
    # V1.1 realtime: streaming TTS native yield interval (seconds of audio
    # per streamed chunk) and the deterministic interviewer voice profile.
    tts_streaming_interval: float = 1.0
    voice_profile: InterviewerVoiceProfile | None = None

    def __post_init__(self) -> None:
        self.state: VoiceState = VoiceState.IDLE
        self._state_lock = asyncio.Lock()
        self._speech_lock = asyncio.Lock()  # serialized ASR/TTS (single oMLX slot)
        self._audio_buf = bytearray()
        self._partial_since = 0
        self._speech_active = False
        self._speech_ended_at: float | None = None
        self._last_question_id: int | None = None
        self._last_question_turn_id: int | None = None
        self._last_question_text: str | None = None
        self._turns_completed = 0
        self._interruptions = 0
        self._running = True
        self._disconnected = False
        self._generation = 0  # increments per TTS stream (H.7 stale protection)
        self._resume_state: VoiceState | None = None
        self._tts_task: asyncio.Task[None] | None = None
        self._answer_task: asyncio.Task[None] | None = None
        self._evaluation_task: asyncio.Task[None] | None = None
        self._speech_task: asyncio.Task[None] | None = None
        # Two-lane (R11): the answer's evaluation is deferred to the
        # LISTENING window so it never shares the async DB session with the
        # question pipeline (concurrent AsyncSession use is unsafe).
        self._pending_evaluation: tuple[str, int] | None = None
        self._evaluated_qids: set[int] = set()  # per-answer evaluation dedup
        self._start_session_task: asyncio.Task[None] | None = None
        self._warmup_task: asyncio.Task[None] | None = None
        self._silence_task: asyncio.Task[None] | None = None
        self._transcripts = self.transcripts or TranscriptSegmentRepository(self.interview.session)
        self._audios = self.audios or AudioSegmentRepository(self.interview.session)
        # Turn timing (wall clock for persisted timestamps, monotonic for latency).
        self._turn_started_wall: datetime | None = None
        self._listen_started_at: float | None = None
        self._first_speech_at: float | None = None
        # Playback-completion gating state (physical-mic speaker integrity).
        self._playback_pending_generation: int | None = None
        self._playback_pending_at: float | None = None
        self._playback_timeout_task: asyncio.Task[None] | None = None
        self._playback_confirmed: bool = True  # latest LISTENING was playback-gated
        self._barge_in_since: float | None = None
        # V1.1 realtime metrics (monotonic timestamps, ms resolution).
        self._last_turn_end_ms: float | None = None
        self._last_asr_ms: float | None = None
        self._last_submit_ms: float | None = None
        self._last_llm_first_token_ms: float | None = None
        self._last_llm_done_ms: float | None = None
        self._first_audio_at: float | None = None
        # Mic-gating diagnostics (counts for the current listening window).
        self._discarded_tts_bytes = 0
        self._discarded_tts_frames = 0
        self._discarded_other_bytes = 0
        self._discarded_other_frames = 0
        self._accepted_bytes = 0
        self._accepted_frames = 0

    # -- state ---------------------------------------------------------------

    async def _set_state(self, state: VoiceState) -> None:
        async with self._state_lock:
            if self.state != state:
                self.state = state
                await self._emit({"type": "state", "state": state.value})

    async def _emit(self, payload: dict[str, Any]) -> None:
        if self.ws is None:
            return
        try:
            await self.ws.send_json(payload)
        except Exception:  # noqa: BLE001 — client disconnect is normal
            self._disconnected = True

    async def _send_bytes(self, payload: bytes) -> None:
        if self.ws is None:
            raise RuntimeError("websocket not connected")
        try:
            await self.ws.send_bytes(payload)
        except Exception:  # noqa: BLE001
            self._disconnected = True
            raise

    # -- main loop: HOT (never awaits long work) -----------------------------

    async def run(self, ws: VoiceWS) -> None:
        """Serve the voice session. Receive loop stays hot (H.1)."""
        self.ws = ws
        try:
            await self._set_state(VoiceState.IDLE)
            # Begin + first question run as background tasks. The TTS warmup
            # is AWAITED inside _start_session before the first question
            # pipeline starts, so the first real synthesis never queues
            # behind the warmup request on the serialized oMLX slot (R4
            # sequencing defect fix: warmup -> question -> speak, never
            # question -> [blocked behind warmup]).
            self._start_session_task = asyncio.create_task(self._start_session())
            while self._running and not self._disconnected:
                try:
                    kind, payload = await ws.receive()
                except Exception:
                    break  # client disconnected
                if kind == "bytes":
                    await self._on_audio(payload)
                else:
                    await self._on_control(payload)
        except PramyaError as exc:
            if not self._disconnected:
                await self._emit({"type": "error", "code": exc.code, "message": exc.message})
        except Exception as exc:  # noqa: BLE001 — surface actionable error
            _logger.exception("voice engine error")
            if not self._disconnected:
                await self._emit({"type": "error", "code": "internal_error", "message": str(exc)})
        finally:
            await self._cancel_tts()
            await self._cancel_answer()
            await self._cancel_evaluation()
            await self._cancel_warmup()
            self._stop_playback_timeout()
            try:
                await ws.close()
            except Exception:  # noqa: BLE001 — client already gone
                _logger.debug("websocket already closed on session end")

    async def _warmup_tts(self) -> None:
        """R4: keep the TTS model resident so the first real sentence does not
        pay the model-load cost. Runs once per session inside the session
        task; awaited before the first question pipeline starts."""
        try:
            await self.tts.warmup()
        except Exception:  # noqa: BLE001
            _logger.debug("tts warmup skipped")

    async def _cancel_warmup(self) -> None:
        if self._warmup_task is not None and not self._warmup_task.done():
            self._warmup_task.cancel()
            try:
                await self._warmup_task
            except asyncio.CancelledError:
                pass
            except Exception as exc:  # noqa: BLE001
                _logger.warning("warmup task cancelled with error: %s", exc)
        self._warmup_task = None

    async def _start_session(self) -> None:
        """Begin session if needed, then kick the first question task."""
        try:
            session = await self.interview.sessions.get_or_raise(
                self.session_id, name="interview session"
            )
            if session.user_id != self.user_id:
                raise NotFoundError("interview session not found")
            if str(session.status) in ("created", "planning"):
                await self.interview.begin(self.session_id, self.user_id)
                await self._set_state(VoiceState.STARTING)
                # R4 sequencing: load/warm the TTS model BEFORE the first
                # question pipeline streams, so the first segment synthesis
                # never queues behind the warmup request on the serialized
                # oMLX slot (cold-start correctness; ~1s when already warm).
                await self._warmup_tts()
                await self._ask_next_question()
            else:
                # Reconnect (Phase H): session already in progress. Resync the
                # client with authoritative state + last question so the UI can
                # recover after a dropped connection without restarting.
                text = self._last_question_text
                if text is None:
                    questions = await self.interview.questions.list_for_session(self.session_id)
                    if questions:
                        text = questions[-1].text
                await self._emit(
                    {
                        "type": "resume",
                        "state": str(session.status),
                        "question": text,
                    }
                )
                # Reconnect: no playback is in flight, so the mic window is
                # safe to open immediately (authoritative LISTENING).
                await self._start_listening(playback_confirmed=True)
        except PramyaError as exc:
            if not self._disconnected:
                await self._emit({"type": "error", "code": exc.code, "message": exc.message})
        except Exception as exc:  # noqa: BLE001
            _logger.exception("voice start failed")
            if not self._disconnected:
                await self._emit({"type": "error", "code": "start_failed", "message": str(exc)})

    # -- control messages ----------------------------------------------------

    async def _on_control(self, payload: Any) -> None:
        try:
            msg = json.loads(payload) if isinstance(payload, str) else payload
        except (TypeError, json.JSONDecodeError):
            raise ValidationFailedError("invalid control message") from None
        if not isinstance(msg, dict):
            raise ValidationFailedError("invalid control message")
        typed: dict[str, Any] = cast(dict[str, Any], msg)
        mtype: object = typed.get("type")
        if mtype == "start_turn":
            await self._start_listening()
        elif mtype == "end_turn":
            await self._request_end_turn()
        elif mtype == "playback_complete":
            # Physical-mic speaker integrity: the ONLY way TTS_PLAYING ->
            # LISTENING in the normal flow. Ignored unless it matches the
            # current pending generation.
            gen = typed.get("generation")
            if isinstance(gen, int):
                await self._on_playback_complete(gen)
            else:
                raise ValidationFailedError("playback_complete requires generation")
        elif mtype == "interrupt":
            await self._interrupt()
        elif mtype == "pause":
            await self._pause()
        elif mtype == "resume":
            await self._resume()
        elif mtype == "heartbeat":
            # Keepalive (Phase H): client liveness probe -> state ack.
            await self._emit({"type": "heartbeat_ack", "state": self.state.value})
        elif mtype == "stop":
            await self._stop()
        elif mtype == "cancel":
            await self._cancel()
        else:
            raise ValidationFailedError(f"unknown control message: {mtype}")

    # -- speaking (background task) ------------------------------------------

    async def _ask_next_question(self) -> None:
        """Start the streaming question pipeline as a background task."""
        self._tts_task = asyncio.create_task(self._speak_next_question())

    async def _speak_next_question(self) -> None:
        """V1.1 realtime pipeline: DeepSeek stream -> segmenter -> TTS stream
        -> WS audio chunks, with LLM/TTS overlap.

        The interviewer question is generated by the LangGraph workflow with
        streaming (R5); tokens feed the segmenter (R6); each complete
        sentence is synthesized by the streaming TTS worker (R7) as soon as
        it is safe, so the first audible audio arrives long before the full
        response exists. The worker serializes synthesis on the single oMLX
        slot; interruption cancels both the pipeline and the worker and
        bumps the generation (stale audio never transmitted).
        """
        try:
            self._generation += 1
            generation = self._generation
            await self._set_state(VoiceState.THINKING)
            await self._emit({"type": "tts_start", "generation": generation})

            segments: asyncio.Queue[str | None] = asyncio.Queue()
            speech_task = asyncio.create_task(self._speech_worker(segments, generation))
            self._speech_task = speech_task
            segmenter = TextSegmenter()
            # Presentation boundary (P0): only the QUESTION: text section of
            # the model stream is speakable — never TYPE/DIFFICULTY/RATIONALE/
            # TARGET/HINTS metadata, never JSON of the structured question.
            extractor = QuestionStreamExtractor()
            t_qstart = time.monotonic()
            self._first_audio_at = None  # per-question watermark (was stale across turns)
            llm_first_token_ms: float | None = None
            llm_done_ms: float | None = None
            question: Any = None
            turn: Any = None

            async for kind, payload in self.interview.next_question_streaming(
                self.session_id, self.user_id
            ):
                if kind == "token" and isinstance(payload, str):
                    if llm_first_token_ms is None:
                        llm_first_token_ms = round((time.monotonic() - t_qstart) * 1000, 1)
                    for t in extractor.feed(payload):
                        for seg in segmenter.feed(t):
                            await segments.put(seg)
                elif kind == "question":
                    question, turn = cast("tuple[Any, Any]", payload)
                    self._last_question_id = question.id
                    self._last_question_turn_id = turn.id
                    # Flush extractor remainder, then segmenter remainder.
                    for t in extractor.flush():
                        for seg in segmenter.feed(t):
                            await segments.put(seg)
                    tail = segmenter.flush()
                    if tail:
                        await segments.put(tail)
            llm_done_ms = round((time.monotonic() - t_qstart) * 1000, 1)
            self._last_llm_first_token_ms = llm_first_token_ms
            self._last_llm_done_ms = llm_done_ms

            if question is not None:
                self._last_question_text = question.text
                await self._persist_question_transcript(
                    question.text, turn.id, started=datetime.now(UTC)
                )
                await self._emit(
                    {
                        "type": "question",
                        "question_id": question.id,
                        "text": question.text,
                        "difficulty": str(question.difficulty),
                    }
                )

            await segments.put(None)  # signal end of stream to the worker
            # Analytical lane (R11): the pending answer evaluation can now run
            # safely — the question pipeline's DB writes are complete and the
            # TTS worker holds no DB. Evals land during this question's speech
            # instead of waiting for the next LISTENING window.
            self._maybe_start_evaluation()
            await speech_task  # wait until ALL audio is sent

            from app.observability import record_event

            record_event(
                "voice_question_waterfall",
                session_id=self.session_id,
                turn_id=turn.id if turn is not None else None,
                question_gen_ms=llm_done_ms,
                llm_first_token_ms=llm_first_token_ms,
                tts_first_audio_ms=(
                    round((self._first_audio_at - t_qstart) * 1000, 1)
                    if self._first_audio_at is not None
                    else None
                ),
                voice_id=self.voice_profile.voice_id if self.voice_profile else None,
                gen_question_chars=len(question.text) if question is not None else 0,
            )

            if self._generation == generation and self.state in (
                VoiceState.THINKING,
                VoiceState.SPEAKING,
            ):
                await self._emit({"type": "tts_stop", "generation": generation})
                # Speaker integrity: stay SPEAKING until the client confirms
                # ACTUAL playback completion. Never transition TTS_PLAYING ->
                # LISTENING on synthesis alone — the browser queue may still be
                # sounding, and the physical mic would capture the interviewer.
                self._playback_pending_generation = generation
                self._playback_pending_at = time.monotonic()
                self._start_playback_timeout()
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            _logger.warning("question pipeline failed, degrading to text: %s", exc)
            if not self._disconnected:
                await self._emit(
                    {
                        "type": "error",
                        "code": "tts_unavailable",
                        "message": "Voice unavailable; answer in text.",
                    }
                )
                await self._set_state(VoiceState.LISTENING)
                await self._start_silence_watchdog()

    async def _speech_worker(self, segments: asyncio.Queue[str | None], generation: int) -> None:
        """Per-segment synthesis with producer/sender overlap.

        Receives complete speakable segments (or None = end of stream).
        The PRODUCER synthesizes each segment as a complete WAV on the single
        oMLX slot and splits it into fixed 200ms PCM16 frames; the SENDER
        relays frames to the browser concurrently, so segment N+1 is
        synthesized while segment N is still playing (continuous speech,
        no chunk-chaining gaps). Each segment's frames are self-contained —
        no cross-segment buffer merging, no native-stream interval artifacts.

        Stops immediately when the generation changes or the engine stops
        (interrupt/barge-in cancels both coroutines and closes the request).
        """
        frame_q: asyncio.Queue[bytes | None] = asyncio.Queue(maxsize=64)
        target_bytes = self.chunk_samples * 2  # 200ms @ 24kHz PCM16

        async def producer() -> None:
            while True:
                seg = await segments.get()
                if seg is None:
                    await frame_q.put(None)
                    return
                if self._generation != generation or not self._running:
                    return
                try:
                    # Dev/observability: log the EXACT TTS-bound text (proves
                    # only question text is spoken, never metadata).
                    _logger.info("tts segment: chars=%d text=%r", len(seg), seg[:160])
                    async with self._speech_lock:
                        if getattr(self.tts, "supports_stream", False):
                            # Streaming provider (Pocket): relay per-chunk PCM
                            # as generated so the FIRST frame reaches the
                            # browser before the segment exists in full.
                            async for frame in self.tts.synthesize_stream(seg):
                                if self._generation != generation or not self._running:
                                    return
                                await frame_q.put(frame)
                        else:
                            pcm, _sr = await self.tts.synthesize(seg)
                            for i in range(0, len(pcm), target_bytes):
                                if self._generation != generation or not self._running:
                                    return
                                frame = pcm[i : i + target_bytes]
                                if len(frame) < target_bytes:
                                    # Pad the final partial frame with silence so the
                                    # sender always relays uniform frames (no tiny
                                    # fragments, no boundary jitter).
                                    frame = frame + b"\x00\x00" * (target_bytes - len(frame))
                                await frame_q.put(frame)
                except asyncio.CancelledError:
                    raise
                except Exception as exc:  # noqa: BLE001
                    # A failed segment must not kill the interview: skip it
                    # and keep speaking the remaining sentences.
                    _logger.warning("tts segment failed (%d chars): %s", len(seg), exc)
                    continue

        async def sender() -> None:
            first_state_sent = False
            while True:
                frame = await frame_q.get()
                if frame is None:
                    return
                if self._generation != generation or not self._running:
                    return
                if not first_state_sent:
                    first_state_sent = True
                    if self._first_audio_at is None:
                        self._first_audio_at = time.monotonic()
                    await self._set_state(VoiceState.SPEAKING)  # audio flowing
                await self._send_bytes(frame)
                await asyncio.sleep(0)

        await asyncio.gather(producer(), sender())

    async def _persist_question_transcript(
        self, text: str, turn_id: int, *, started: datetime | None = None
    ) -> None:
        seq = await self._transcripts.max_seq_for_turn(turn_id)
        timestamps: dict[str, object] | None = None
        if started is not None:
            timestamps = {
                "role": "interviewer",
                "started_at": started.isoformat(),
                "ended_at": datetime.now(UTC).isoformat(),
            }
        await self._transcripts.add(
            TranscriptSegment(
                interview_session_id=self.session_id,
                turn_id=turn_id,
                seq=seq + 1,
                partial=False,
                text=text,
                speaker="interviewer",
                timestamps=timestamps,
            )
        )
        await self.interview.session.commit()

    def _start_playback_timeout(self) -> None:
        """Failure-mode guard: a dead/glitched client must not deadlock the
        session. Normal flow is the playback_complete handshake; this only
        fires when the client never confirms playback."""
        if self._playback_timeout_task is not None and not self._playback_timeout_task.done():
            return
        self._playback_timeout_task = asyncio.create_task(self._playback_timeout_guard())

    async def _playback_timeout_guard(self) -> None:
        await asyncio.sleep(self.playback_timeout_seconds)
        gen = self._playback_pending_generation
        if gen is not None and self.state is VoiceState.SPEAKING and self._generation == gen:
            _logger.warning(
                "playback completion not confirmed within %.1fs (gen %s); "
                "forcing listening with playback_confirmed=False",
                self.playback_timeout_seconds,
                gen,
            )
            await self._start_listening(playback_confirmed=False)

    def _stop_playback_timeout(self) -> None:
        if self._playback_timeout_task is not None and not self._playback_timeout_task.done():
            self._playback_timeout_task.cancel()
        self._playback_timeout_task = None

    async def _on_playback_complete(self, generation: int) -> None:
        """Client confirmed real playback completion -> authoritative LISTENING.

        Only a playback_complete for the CURRENT pending generation opens the
        mic window; stale generations are ignored so a delayed ack from a
        previous stream can never unlock capture.
        """
        if self.state is not VoiceState.SPEAKING:
            return
        if self._playback_pending_generation != generation:
            return
        self._playback_pending_generation = None
        self._stop_playback_timeout()
        await self._start_listening(playback_confirmed=True)

    async def _start_listening(self, playback_confirmed: bool = True) -> None:
        self._audio_buf.clear()
        self._partial_since = 0
        self._speech_active = False
        self._speech_ended_at = None
        self._turn_started_wall = datetime.now(UTC)
        self._listen_started_at = time.monotonic()
        self._first_speech_at = None
        self._playback_confirmed = playback_confirmed
        # Reset per-window mic-gating diagnostics.
        self._discarded_tts_bytes = 0
        self._discarded_tts_frames = 0
        self._discarded_other_bytes = 0
        self._discarded_other_frames = 0
        self._accepted_bytes = 0
        self._accepted_frames = 0
        from app.observability import record_event

        pending_at = self._playback_pending_at
        self._playback_pending_generation = None
        self._playback_pending_at = None
        record_event(
            "voice_listening",
            session_id=self.session_id,
            playback_confirmed=playback_confirmed,
            pending_ms=round((time.monotonic() - pending_at) * 1000, 1) if pending_at else None,
        )
        await self._set_state(VoiceState.LISTENING)
        await self._start_silence_watchdog()
        # Analytical lane: start the deferred evaluation now that the
        # question pipeline is quiescent (no concurrent session use).
        self._maybe_start_evaluation()

    def _maybe_start_evaluation(self) -> None:
        """Launch the deferred evaluation for the pending answer (two-lane).

        Exactly once PER ANSWER: each new answer overwrites
        _pending_evaluation; _evaluated_qids dedupes so a replay of the same
        listening window can never double-evaluate. Runs only when the
        question pipeline is quiescent (LISTENING window), so it never
        contends with the question pipeline on the shared async session.
        """
        pending = self._pending_evaluation
        if pending is None:
            return
        transcript, qid = pending
        if qid in self._evaluated_qids:
            return
        self._evaluated_qids.add(qid)
        self._pending_evaluation = None
        self._evaluation_task = asyncio.create_task(
            self._evaluate_answer_background(transcript, qid)
        )

    async def _start_silence_watchdog(self) -> None:
        if self._silence_task is not None and not self._silence_task.done():
            return
        self._silence_task = asyncio.create_task(self._silence_watchdog())

    async def _stop_silence_watchdog(self) -> None:
        if self._silence_task is not None and not self._silence_task.done():
            self._silence_task.cancel()
            try:
                await self._silence_task
            except asyncio.CancelledError:
                pass
            except Exception as exc:  # noqa: BLE001
                _logger.warning("silence watchdog cancelled with error: %s", exc)
        self._silence_task = None

    # -- audio + ASR ---------------------------------------------------------

    async def _on_audio(self, chunk: bytes) -> None:
        if self.state is VoiceState.LISTENING:
            # Authoritative candidate window: accepted for ASR.
            self._audio_buf.extend(chunk)
            self._accepted_bytes += len(chunk)
            self._accepted_frames += 1
            self._update_speech_state(chunk)
            # Partial transcripts every ~2s of accumulated audio.
            if len(self._audio_buf) - self._partial_since >= self.partial_interval_samples * 2:
                self._partial_since = len(self._audio_buf)
                await self._emit_partial()
        elif self.state in (VoiceState.SPEAKING, VoiceState.THINKING):
            # Interviewer-owned window (speaking or thinking-to-speak):
            # candidate mic must never become the candidate's answer here.
            # Count for diagnostics; never ASR.
            self._discarded_tts_bytes += len(chunk)
            self._discarded_tts_frames += 1
            if self.barge_in_enabled:
                await self._maybe_voice_barge_in(chunk)
        else:
            # processing / paused / interrupted / completed / cancelled / idle:
            # no candidate audio is accepted outside the listening window.
            self._discarded_other_bytes += len(chunk)
            self._discarded_other_frames += 1

    async def _maybe_voice_barge_in(self, chunk: bytes) -> None:
        """Opt-in voice-triggered barge-in: sustained mic energy during
        SPEAKING cancels TTS and opens listening. Explicit interrupt control
        remains the guaranteed path; this is headphone-safe convenience."""
        if _rms(chunk) >= self.barge_in_rms:
            if self._barge_in_since is None:
                self._barge_in_since = time.monotonic()
            elif (time.monotonic() - self._barge_in_since) >= self.barge_in_ms / 1000.0:
                self._barge_in_since = None
                _logger.info(
                    "voice barge-in: sustained mic energy during TTS (session %s)",
                    self.session_id,
                )
                await self._interrupt()
        else:
            self._barge_in_since = None

    def _update_speech_state(self, chunk: bytes) -> None:
        energy = _rms(chunk)
        if energy >= self.speech_rms:
            self._speech_active = True
            self._speech_ended_at = None
            if self._first_speech_at is None:
                self._first_speech_at = time.monotonic()
        elif self._speech_active and self._speech_ended_at is None:
            self._speech_ended_at = time.monotonic()

    async def _silence_watchdog(self) -> None:
        """H.2 automatic finalization: fires even if the client stops sending
        audio (mic paused/glitched), not only on subsequent frames."""
        while self._running and self.state is VoiceState.LISTENING:
            await asyncio.sleep(0.1)
            if (
                self._speech_active
                and self._speech_ended_at is not None
                and (time.monotonic() - self._speech_ended_at) >= self.silence_seconds
            ):
                await self._request_end_turn()
                return

    async def _emit_partial(self) -> None:
        try:
            async with self._speech_lock:
                text = await self.asr.transcribe(
                    bytes(self._audio_buf), sample_rate=self.asr_sample_rate
                )
            if text and self.state is VoiceState.LISTENING:
                await self._emit({"type": "partial_transcript", "text": text, "partial": True})
        except Exception as exc:  # noqa: BLE001
            _logger.warning("partial asr failed: %s", exc)

    # -- answer pipeline (background task) -----------------------------------

    async def _request_end_turn(self) -> None:
        """Manual or automatic end-of-speech -> start the answer task."""
        if self.state is not VoiceState.LISTENING:
            return
        if self._answer_task is not None and not self._answer_task.done():
            return  # already processing
        await self._stop_silence_watchdog()
        await self._emit({"type": "turn_ended"})
        self._answer_task = asyncio.create_task(self._process_answer())

    async def _process_answer(self) -> None:
        """Two-lane answer pipeline (V1.1, R11):

        Critical path: final ASR -> durably record the answer (fast commit)
        -> immediately start the streaming next-question pipeline.
        Analytical lane (background task, never blocks): LangGraph evaluation
        + evidence extraction, emitted asynchronously as an evaluation event.
        """
        try:
            await self._set_state(VoiceState.PROCESSING)
            self._last_turn_end_ms = time.monotonic()
            audio = bytes(self._audio_buf)
            self._audio_buf.clear()
            self._speech_active = False
            self._speech_ended_at = None
            if not audio:
                await self._set_state(VoiceState.LISTENING)
                await self._start_silence_watchdog()
                return
            async with self._speech_lock:
                started_asr = time.monotonic()
                transcript = await self.asr.transcribe(audio, sample_rate=self.asr_sample_rate)
                asr_ms = round((time.monotonic() - started_asr) * 1000, 1)
            self._last_asr_ms = asr_ms
            from app.observability import record_event

            record_event(
                "voice_asr",
                session_id=self.session_id,
                asr_latency_ms=asr_ms,
                audio_bytes=len(audio),
                model="Parakeet-TDT",
            )
            t_submit_start = time.monotonic()
            record_event(
                "voice_answer",
                session_id=self.session_id,
                answer_bytes=len(audio),
                accepted_frames=self._accepted_frames,
                accepted_bytes=self._accepted_bytes,
                discarded_tts_frames=self._discarded_tts_frames,
                discarded_tts_bytes=self._discarded_tts_bytes,
                discarded_other_frames=self._discarded_other_frames,
                playback_confirmed=self._playback_confirmed,
                listening_ms=(
                    round((time.monotonic() - self._listen_started_at) * 1000, 1)
                    if self._listen_started_at is not None
                    else None
                ),
                interruptions=self._interruptions,
            )
            if not transcript.strip():
                await self._emit({"type": "final_transcript", "text": ""})
                await self._set_state(VoiceState.LISTENING)
                await self._start_silence_watchdog()
                return
            await self._emit({"type": "final_transcript", "text": transcript})
            if self._last_question_id is None:
                raise ValidationFailedError("no active question")
            # Persist candidate audio (opt-in) before answering so a crash after
            # submission still leaves the recording available for replay.
            await self._persist_answer_audio(audio)
            answer = await self.interview.submit_answer(
                self.session_id,
                self.user_id,
                question_id=self._last_question_id,
                answer_text=transcript,
                idempotency_key=f"voice-{self.session_id}-{self._last_question_id}",
                mode="voice",
                await_evaluation=False,  # two-lane: evaluation is analytical
            )
            t_submit_end = time.monotonic()
            self._last_submit_ms = round((t_submit_end - t_submit_start) * 1000, 1)
            record_event(
                "voice_answer_waterfall",
                session_id=self.session_id,
                asr_ms=asr_ms,
                submit_ms=self._last_submit_ms,
                answer_chars=len(transcript),
            )
            self._turns_completed += 1
            await self._persist_answer_transcript(
                transcript, audio_ms=_pcm16_duration_ms(audio, self.asr_sample_rate)
            )
            await self._emit({"type": "answer_submitted", "answer_id": answer.id})
            # Analytical lane (R11): evaluation is deferred until the
            # next-question pipeline has finished its DB writes (LISTENING
            # window) — never concurrent with the question pipeline on the
            # shared async session. The answer row is already durable.
            # _last_question_id is guaranteed non-None here (validated above).
            self._pending_evaluation = (transcript, self._last_question_id)
            # Critical path continues immediately: next question streams.
            if self._running:
                await self._ask_next_question()
        except asyncio.CancelledError:
            raise

    async def _evaluate_answer_background(self, transcript: str, qid: int) -> None:
        """Analytical lane: LangGraph evaluation -> persisted + evented.

        Runs during the LISTENING window (deferred from the answer pipeline),
        so it never contends with the question pipeline on the shared async
        session. The next question reads the committed answer turn (never
        this evaluation) — no stale-state race; evidence from the answer
        lands after the next question starts (documented adaptation lag).
        """
        try:
            evaluation = await self.interview.evaluate_answer(
                self.session_id,
                self.user_id,
                question_id=qid,
                answer_text=transcript,
            )
            if not self._disconnected:
                await self._emit(
                    {
                        "type": "evaluation",
                        "answer_id": qid,
                        "question_id": qid,
                        "overall": float(evaluation.overall),
                    }
                )
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 — evaluation must not kill the session
            _logger.warning("background evaluation failed: %s", exc)
            if not self._disconnected:
                await self._emit(
                    {"type": "error", "code": "evaluation_failed", "message": str(exc)}
                )

    async def _persist_answer_audio(self, audio: bytes) -> None:
        """Store candidate audio as WAV + audio_segment row (Phase H).

        Writes only when store_audio is enabled and a storage dir is set.
        The row is best-effort: a storage failure must not break the turn.
        """
        if not self.store_audio or not self.audio_storage_dir or not audio:
            return
        turn = await self.interview.turns.latest_for_session(self.session_id)
        if turn is None:
            return
        try:
            dir_path = Path(self.audio_storage_dir) / str(self.session_id)
            dir_path.mkdir(parents=True, exist_ok=True)
            storage_key = f"{self.session_id}/{turn.id}.wav"
            (dir_path / f"{turn.id}.wav").write_bytes(
                ASRClient.pcm16_to_wav(audio, self.asr_sample_rate)
            )
            retention_until = datetime.now(UTC) + timedelta(days=self.retention_days)
            await self._audios.add(
                AudioSegment(
                    interview_session_id=self.session_id,
                    turn_id=turn.id,
                    kind=TurnDirection.INPUT,
                    storage_key=storage_key,
                    duration_ms=_pcm16_duration_ms(audio, self.asr_sample_rate),
                    retention_until=retention_until,
                )
            )
            await self.interview.session.commit()
        except Exception as exc:  # noqa: BLE001 — storage must not kill the turn
            _logger.warning("audio persistence failed: %s", exc)

    async def _persist_answer_transcript(self, text: str, *, audio_ms: int | None = None) -> None:
        turn = await self.interview.turns.latest_for_session(self.session_id)
        if turn is None:
            return
        seq = await self._transcripts.max_seq_for_turn(turn.id)
        timestamps = self._answer_timestamps(audio_ms)
        await self._transcripts.add(
            TranscriptSegment(
                interview_session_id=self.session_id,
                turn_id=turn.id,
                seq=seq + 1,
                partial=False,
                text=text,
                speaker="candidate",
                timestamps=timestamps,
            )
        )
        await self.interview.session.commit()

    def _answer_timestamps(self, audio_ms: int | None) -> dict[str, object]:
        """Wall-clock + measured timing for the current candidate turn."""
        now = datetime.now(UTC)
        latency_ms: int | None = None
        if self._listen_started_at is not None and self._first_speech_at is not None:
            latency_ms = round((self._first_speech_at - self._listen_started_at) * 1000)
        ts: dict[str, object] = {
            "role": "candidate",
            "started_at": (self._turn_started_wall or now).isoformat(),
            "ended_at": now.isoformat(),
        }
        if audio_ms is not None:
            ts["audio_ms"] = audio_ms
        if latency_ms is not None:
            ts["response_latency_ms"] = latency_ms
        if self._interruptions:
            ts["interruptions"] = self._interruptions
        return ts

    # -- interruption / pause / stop ----------------------------------------

    async def _interrupt(self) -> None:
        """Barge-in: cancel TTS + in-flight answer, clear audio, -> listening."""
        self._interruptions += 1
        from app.observability import record_event

        record_event(
            "voice_interrupt",
            session_id=self.session_id,
            interruption_count=self._interruptions,
            discarded_tts_bytes=self._discarded_tts_bytes,
        )
        await self._cancel_tts()
        await self._cancel_answer()
        await self._cancel_evaluation()
        await self._stop_silence_watchdog()
        self._playback_pending_generation = None
        self._playback_pending_at = None
        self._stop_playback_timeout()
        self._barge_in_since = None
        self._audio_buf.clear()
        self._partial_since = 0
        self._speech_active = False
        self._speech_ended_at = None
        self._turn_started_wall = datetime.now(UTC)
        self._listen_started_at = time.monotonic()
        self._first_speech_at = None
        await self._set_state(VoiceState.INTERRUPTED)
        await self._set_state(VoiceState.LISTENING)
        await self._start_silence_watchdog()

    async def _cancel_tts(self) -> None:
        # Bump generation first: any in-flight chunk stream stops immediately.
        self._generation += 1
        # The speech worker holds the oMLX slot; cancel it so the streaming
        # synthesis closes immediately (interrupt-safe).
        if self._speech_task is not None and not self._speech_task.done():
            self._speech_task.cancel()
            try:
                await self._speech_task
            except asyncio.CancelledError:
                pass  # expected: we cancelled in-flight TTS
            except Exception as exc:  # noqa: BLE001
                _logger.warning("speech worker cancelled with error: %s", exc)
        self._speech_task = None
        if self._tts_task is not None and not self._tts_task.done():
            self._tts_task.cancel()
            try:
                await self._tts_task
            except asyncio.CancelledError:
                pass  # expected: we cancelled the question pipeline
            except Exception as exc:  # noqa: BLE001
                _logger.warning("tts task cancelled with error: %s", exc)
        self._tts_task = None

    async def _cancel_answer(self) -> None:
        if self._answer_task is not None and not self._answer_task.done():
            self._answer_task.cancel()
            try:
                await self._answer_task
            except asyncio.CancelledError:
                pass  # expected
            except Exception as exc:  # noqa: BLE001
                _logger.warning("answer task cancelled with error: %s", exc)
        self._answer_task = None

    async def _cancel_evaluation(self) -> None:
        if self._evaluation_task is not None and not self._evaluation_task.done():
            self._evaluation_task.cancel()
            try:
                await self._evaluation_task
            except asyncio.CancelledError:
                pass  # expected
            except Exception as exc:  # noqa: BLE001
                _logger.warning("evaluation task cancelled with error: %s", exc)
        self._evaluation_task = None

    async def _pause(self) -> None:
        if self.state in (
            VoiceState.LISTENING,
            VoiceState.PROCESSING,
            VoiceState.SPEAKING,
            VoiceState.THINKING,
        ):
            if self.state in (VoiceState.SPEAKING, VoiceState.THINKING):
                # Stop talking / stop the pending question pipeline; resume
                # returns to listening (same question).
                await self._cancel_tts()
                self._playback_pending_generation = None
                self._playback_pending_at = None
                self._stop_playback_timeout()
            await self._stop_silence_watchdog()
            self._resume_state = VoiceState.LISTENING
            await self._set_state(VoiceState.PAUSED)

    async def _resume(self) -> None:
        if self.state is VoiceState.PAUSED:
            target = self._resume_state or VoiceState.LISTENING
            self._resume_state = None
            await self._set_state(target)
            if target is VoiceState.LISTENING:
                self._audio_buf.clear()
                self._partial_since = 0
                self._speech_active = False
                self._speech_ended_at = None
                await self._start_silence_watchdog()

    async def _stop(self) -> None:
        # The session may already be terminal (e.g. cancelled via the HTTP/
        # SSE path before the WS control arrived) — cancellation of TTS must
        # still happen, so tolerate the state-transition error.
        try:
            await self.interview.stop(self.session_id, self.user_id)
        except InterviewStateError:
            pass
        await self._cancel_tts()
        await self._cancel_answer()
        await self._cancel_evaluation()
        await self._stop_silence_watchdog()
        self._playback_pending_generation = None
        self._playback_pending_at = None
        self._stop_playback_timeout()
        await self._set_state(VoiceState.COMPLETED)
        self._running = False

    async def _cancel(self) -> None:
        try:
            await self.interview.cancel(self.session_id, self.user_id)
        except InterviewStateError:
            pass  # already terminal; TTS cancellation below is what matters
        await self._cancel_tts()
        await self._cancel_answer()
        await self._cancel_evaluation()
        await self._stop_silence_watchdog()
        self._playback_pending_generation = None
        self._playback_pending_at = None
        self._stop_playback_timeout()
        await self._set_state(VoiceState.CANCELLED)
        self._running = False
