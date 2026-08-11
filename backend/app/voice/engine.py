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
from typing import Any, cast

from app.core.logging import get_logger
from app.domain.enums import VoiceState
from app.domain.errors import (
    NotFoundError,
    PramyaError,
    ValidationFailedError,
)
from app.interview.service import InterviewService
from app.models.interview import TranscriptSegment
from app.repositories.interview import TranscriptSegmentRepository
from app.voice.asr import ASRClient
from app.voice.tts import TTSClient, chunk_pcm16

_logger = get_logger("app.voice.engine")

# Minimum accumulation (samples @16kHz) between partial ASR calls.
PARTIAL_INTERVAL_SAMPLES = 32000  # 2.0 s


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
    tts: TTSClient
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
        self._turns_completed = 0
        self._running = True
        self._disconnected = False
        self._generation = 0  # increments per TTS stream (H.7 stale protection)
        self._resume_state: VoiceState | None = None
        self._tts_task: asyncio.Task[None] | None = None
        self._answer_task: asyncio.Task[None] | None = None
        self._start_session_task: asyncio.Task[None] | None = None
        self._silence_task: asyncio.Task[None] | None = None
        self._transcripts = self.transcripts or TranscriptSegmentRepository(self.interview.session)

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
            # Begin + first question run as background tasks.
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
            try:
                await ws.close()
            except Exception:  # noqa: BLE001 — client already gone
                _logger.debug("websocket already closed on session end")

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
            await self._ask_next_question()
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
        elif mtype == "interrupt":
            await self._interrupt()
        elif mtype == "pause":
            await self._pause()
        elif mtype == "resume":
            await self._resume()
        elif mtype == "stop":
            await self._stop()
        elif mtype == "cancel":
            await self._cancel()
        else:
            raise ValidationFailedError(f"unknown control message: {mtype}")

    # -- speaking (background task) ------------------------------------------

    async def _ask_next_question(self) -> None:
        """Start the question -> TTS -> stream pipeline as a background task."""
        self._tts_task = asyncio.create_task(self._speak_next_question())

    async def _speak_next_question(self) -> None:
        """Generate question (DeepSeek) -> Qwen3-TTS -> chunk stream."""
        try:
            await self._set_state(VoiceState.SPEAKING)
            self._generation += 1
            generation = self._generation
            question, turn = await self.interview.next_question(self.session_id, self.user_id)
            self._last_question_id = question.id
            self._last_question_turn_id = turn.id
            await self._persist_question_transcript(question.text, turn.id)
            await self._emit(
                {
                    "type": "question",
                    "question_id": question.id,
                    "text": question.text,
                    "difficulty": str(question.difficulty),
                }
            )
            await self._emit({"type": "tts_start", "generation": generation})
            async with self._speech_lock:
                pcm, sr = await self.tts.synthesize(question.text)
            self.tts_sample_rate = sr
            for chunk in chunk_pcm16(pcm, self.chunk_samples):
                # H.7: only send chunks for the CURRENT generation; interrupt
                # bumps the generation so stale audio is never transmitted.
                if self._generation != generation or not self._running:
                    return
                await self._send_bytes(chunk)
                await asyncio.sleep(0)  # yield so interrupt can land
            if self._generation == generation:
                await self._emit({"type": "tts_stop", "generation": generation})
                await self._set_state(VoiceState.LISTENING)
                self._speech_active = False
                self._speech_ended_at = None
                await self._start_silence_watchdog()
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            _logger.warning("tts failed, degrading to text: %s", exc)
            if not self._disconnected:
                await self._emit(
                    {
                        "type": "error",
                        "code": "tts_unavailable",
                        "message": "TTS unavailable; answer in text.",
                    }
                )
                await self._set_state(VoiceState.LISTENING)
                await self._start_silence_watchdog()

    async def _persist_question_transcript(self, text: str, turn_id: int) -> None:
        seq = await self._transcripts.max_seq_for_turn(turn_id)
        await self._transcripts.add(
            TranscriptSegment(
                interview_session_id=self.session_id,
                turn_id=turn_id,
                seq=seq + 1,
                partial=False,
                text=text,
            )
        )
        await self.interview.session.commit()

    async def _start_listening(self) -> None:
        self._audio_buf.clear()
        self._partial_since = 0
        self._speech_active = False
        self._speech_ended_at = None
        await self._set_state(VoiceState.LISTENING)
        await self._start_silence_watchdog()

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
        if self.state is not VoiceState.LISTENING:
            return
        self._audio_buf.extend(chunk)
        self._update_speech_state(chunk)
        # Partial transcripts every ~2s of accumulated audio.
        if len(self._audio_buf) - self._partial_since >= self.partial_interval_samples * 2:
            self._partial_since = len(self._audio_buf)
            await self._emit_partial()

    def _update_speech_state(self, chunk: bytes) -> None:
        energy = _rms(chunk)
        if energy >= self.speech_rms:
            self._speech_active = True
            self._speech_ended_at = None
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
        """Final ASR -> submit_answer (DeepSeek) -> next question (repeat)."""
        try:
            await self._set_state(VoiceState.PROCESSING)
            audio = bytes(self._audio_buf)
            self._audio_buf.clear()
            self._speech_active = False
            self._speech_ended_at = None
            if not audio:
                await self._set_state(VoiceState.LISTENING)
                await self._start_silence_watchdog()
                return
            async with self._speech_lock:
                transcript = await self.asr.transcribe(audio, sample_rate=self.asr_sample_rate)
            if not transcript.strip():
                await self._emit({"type": "final_transcript", "text": ""})
                await self._set_state(VoiceState.LISTENING)
                await self._start_silence_watchdog()
                return
            await self._emit({"type": "final_transcript", "text": transcript})
            if self._last_question_id is None:
                raise ValidationFailedError("no active question")
            answer = await self.interview.submit_answer(
                self.session_id,
                self.user_id,
                question_id=self._last_question_id,
                answer_text=transcript,
                idempotency_key=f"voice-{self.session_id}-{self._last_question_id}",
                mode="voice",
            )
            self._turns_completed += 1
            await self._persist_answer_transcript(transcript)
            await self._emit({"type": "answer_submitted", "answer_id": answer.id})
            evaluation = await self.interview.evaluations.get_by_answer(answer.id)
            await self._emit(
                {
                    "type": "evaluation",
                    "answer_id": answer.id,
                    "question_id": self._last_question_id,
                    "overall": float(evaluation.overall) if evaluation else None,
                }
            )
            # Adaptive loop continues.
            if self._running:
                await self._ask_next_question()
        except asyncio.CancelledError:
            raise
        except PramyaError as exc:
            if not self._disconnected:
                await self._emit({"type": "error", "code": exc.code, "message": exc.message})
                await self._set_state(VoiceState.LISTENING)
                await self._start_silence_watchdog()
        except Exception as exc:  # noqa: BLE001
            _logger.exception("answer processing failed")
            if not self._disconnected:
                await self._emit(
                    {"type": "error", "code": "asr_failed", "message": f"ASR failed: {exc}"}
                )
                await self._set_state(VoiceState.LISTENING)
                await self._start_silence_watchdog()

    async def _persist_answer_transcript(self, text: str) -> None:
        turn = await self.interview.turns.latest_for_session(self.session_id)
        if turn is None:
            return
        seq = await self._transcripts.max_seq_for_turn(turn.id)
        await self._transcripts.add(
            TranscriptSegment(
                interview_session_id=self.session_id,
                turn_id=turn.id,
                seq=seq + 1,
                partial=False,
                text=text,
            )
        )
        await self.interview.session.commit()

    # -- interruption / pause / stop ----------------------------------------

    async def _interrupt(self) -> None:
        """Barge-in: cancel TTS + in-flight answer, clear audio, -> listening."""
        await self._cancel_tts()
        await self._cancel_answer()
        await self._stop_silence_watchdog()
        self._audio_buf.clear()
        self._partial_since = 0
        self._speech_active = False
        self._speech_ended_at = None
        await self._set_state(VoiceState.INTERRUPTED)
        await self._set_state(VoiceState.LISTENING)
        await self._start_silence_watchdog()

    async def _cancel_tts(self) -> None:
        # Bump generation first: any in-flight chunk stream stops immediately.
        self._generation += 1
        if self._tts_task is not None and not self._tts_task.done():
            self._tts_task.cancel()
            try:
                await self._tts_task
            except asyncio.CancelledError:
                pass  # expected: we cancelled in-flight TTS
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

    async def _pause(self) -> None:
        if self.state in (
            VoiceState.LISTENING,
            VoiceState.PROCESSING,
            VoiceState.SPEAKING,
        ):
            if self.state is VoiceState.SPEAKING:
                # Stop talking; resume returns to listening (same question).
                await self._cancel_tts()
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
        await self.interview.stop(self.session_id, self.user_id)
        await self._cancel_tts()
        await self._cancel_answer()
        await self._stop_silence_watchdog()
        await self._set_state(VoiceState.COMPLETED)
        self._running = False

    async def _cancel(self) -> None:
        await self.interview.cancel(self.session_id, self.user_id)
        await self._cancel_tts()
        await self._cancel_answer()
        await self._stop_silence_watchdog()
        await self._set_state(VoiceState.CANCELLED)
        self._running = False
