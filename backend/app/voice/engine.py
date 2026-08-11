"""VoiceEngine — server-authoritative voice interview state machine.

States (mirror app.domain.enums.VoiceState): idle -> listening ->
processing -> speaking -> paused | interrupted | cancelled | completed |
error. The server is the single source of truth and broadcasts every
transition as a JSON `state` event.

Pipeline per turn:
  speaking: question text -> TTS (oMLX) -> PCM 24 kHz audio_chunk frames
  listening: client PCM16 16 kHz binary frames -> periodic partial ASR
  processing: final ASR transcript -> interview graph (submit_answer)
              -> evaluation -> next question -> speaking (repeat)

Interruption is a correctness requirement: an `interrupt` during speaking
cancels the in-flight TTS generation, clears the queued chunk buffer, and
transitions to listening without duplicating the question or evaluation.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any, cast

from app.core.logging import get_logger
from app.domain.enums import VoiceState
from app.domain.errors import (
    NotFoundError,
    PramyaError,
    ProviderUnavailableError,
    ValidationFailedError,
)
from app.interview.service import InterviewService
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
    ws: VoiceWS | None = None

    def __post_init__(self) -> None:
        self.state: VoiceState = VoiceState.IDLE
        self._state_lock = asyncio.Lock()
        self._speech_lock = asyncio.Lock()  # serialized ASR/TTS (single oMLX slot)
        self._audio_buf = bytearray()
        self._partial_since = 0
        self._tts_task: asyncio.Task[None] | None = None
        self._tts_cancelled = False
        self._last_question_id: int | None = None
        self._turns_completed = 0
        self._running = True

    # -- state ---------------------------------------------------------------

    async def _set_state(self, state: VoiceState) -> None:
        async with self._state_lock:
            if self.state != state:
                self.state = state
                await self._emit({"type": "state", "state": state.value})

    async def _emit(self, payload: dict[str, Any]) -> None:
        if self.ws is not None:
            await self.ws.send_json(payload)

    async def _send_bytes(self, payload: bytes) -> None:
        if self.ws is None:
            raise RuntimeError("websocket not connected")
        await self.ws.send_bytes(payload)

    # -- main loop -----------------------------------------------------------

    async def run(self, ws: VoiceWS) -> None:
        """Serve the voice session until stop/cancel/error/disconnect."""
        self.ws = ws
        try:
            await self._set_state(VoiceState.IDLE)
            await self._start_session()
            while self._running:
                try:
                    kind, payload = await ws.receive()
                except Exception:
                    break  # client disconnected
                if kind == "bytes":
                    await self._on_audio(payload)
                else:
                    await self._on_control(payload)
        except PramyaError as exc:
            await self._emit({"type": "error", "code": exc.code, "message": exc.message})
        except Exception as exc:  # noqa: BLE001 — surface actionable error
            _logger.exception("voice engine error")
            await self._emit({"type": "error", "code": "internal_error", "message": str(exc)})
        finally:
            await self._cancel_tts()
            await ws.close()

    async def _start_session(self) -> None:
        """Begin session if needed and ask the first question."""
        session = await self.interview.sessions.get_or_raise(
            self.session_id, name="interview session"
        )
        if session.user_id != self.user_id:
            raise NotFoundError("interview session not found")
        if str(session.status) in ("created", "planning"):
            await self.interview.begin(self.session_id, self.user_id)
        await self._speak_next_question()

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
            await self._end_turn()
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

    # -- speaking ------------------------------------------------------------

    async def _speak_next_question(self) -> None:
        """Generate the next question, synthesize it, and stream audio."""
        if self._tts_cancelled:
            self._tts_cancelled = False
        await self._set_state(VoiceState.SPEAKING)
        question, _turn = await self.interview.next_question(self.session_id, self.user_id)
        self._last_question_id = question.id
        await self._emit(
            {
                "type": "question",
                "question_id": question.id,
                "text": question.text,
                "difficulty": str(question.difficulty),
            }
        )
        await self._emit({"type": "tts_start"})
        try:
            async with self._speech_lock:
                pcm, sr = await self.tts.synthesize(question.text)
            self.tts_sample_rate = sr
            if self._tts_cancelled:
                return
            for chunk in chunk_pcm16(pcm, self.chunk_samples):
                if self._tts_cancelled or not self._running:
                    return
                await self._send_bytes(chunk)
                await asyncio.sleep(0)  # yield so interrupt can land
            await self._emit({"type": "tts_stop"})
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            _logger.warning("tts failed, degrading to text: %s", exc)
            await self._emit(
                {
                    "type": "error",
                    "code": "tts_unavailable",
                    "message": "TTS unavailable; answer in text.",
                }
            )
        finally:
            if not self._tts_cancelled:
                await self._set_state(VoiceState.LISTENING)

    async def _start_listening(self) -> None:
        self._audio_buf.clear()
        self._partial_since = 0
        await self._set_state(VoiceState.LISTENING)

    # -- audio + ASR ---------------------------------------------------------

    async def _on_audio(self, chunk: bytes) -> None:
        if self.state not in (VoiceState.LISTENING, VoiceState.PAUSED):
            return
        if self.state is VoiceState.PAUSED:
            return
        self._audio_buf.extend(chunk)
        if len(self._audio_buf) - self._partial_since >= self.partial_interval_samples * 2:
            self._partial_since = len(self._audio_buf)
            await self._emit_partial()

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

    async def _end_turn(self) -> None:
        """Final ASR -> submit answer -> evaluation -> next question."""
        if self.state is not VoiceState.LISTENING:
            return
        await self._set_state(VoiceState.PROCESSING)
        audio = bytes(self._audio_buf)
        self._audio_buf.clear()
        if not audio:
            await self._set_state(VoiceState.LISTENING)
            return
        try:
            async with self._speech_lock:
                transcript = await self.asr.transcribe(audio, sample_rate=self.asr_sample_rate)
        except Exception as exc:  # noqa: BLE001
            raise ProviderUnavailableError(f"ASR failed: {exc}") from exc
        if not transcript.strip():
            await self._emit({"type": "final_transcript", "text": ""})
            await self._set_state(VoiceState.LISTENING)
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
        evaluation = await self.interview.evaluations.get_by_answer(answer.id)
        await self._emit(
            {
                "type": "evaluation",
                "answer_id": answer.id,
                "question_id": self._last_question_id,
                "overall": float(evaluation.overall) if evaluation else None,
            }
        )
        # Continue the adaptive loop: next question (or end when interviewer
        # decides). V1 keeps asking until the candidate stops.
        await self._speak_next_question()

    # -- interruption / pause / stop ----------------------------------------

    async def _interrupt(self) -> None:
        """Barge-in: cancel TTS, clear queued audio, transition to listening."""
        await self._cancel_tts()
        await self._set_state(VoiceState.INTERRUPTED)
        await self._set_state(VoiceState.LISTENING)
        self._audio_buf.clear()
        self._partial_since = 0

    async def _cancel_tts(self) -> None:
        self._tts_cancelled = True
        if self._tts_task is not None and not self._tts_task.done():
            self._tts_task.cancel()
            try:
                await self._tts_task
            except asyncio.CancelledError:
                pass  # expected: we cancelled in-flight TTS
            except Exception as exc:  # noqa: BLE001
                _logger.warning("tts task cancelled with error: %s", exc)
        self._tts_task = None

    async def _pause(self) -> None:
        if self.state in (VoiceState.LISTENING, VoiceState.PROCESSING):
            await self._set_state(VoiceState.PAUSED)

    async def _resume(self) -> None:
        if self.state is VoiceState.PAUSED:
            await self._set_state(VoiceState.LISTENING)

    async def _stop(self) -> None:
        await self.interview.stop(self.session_id, self.user_id)
        await self._cancel_tts()
        await self._set_state(VoiceState.COMPLETED)
        self._running = False

    async def _cancel(self) -> None:
        await self.interview.cancel(self.session_id, self.user_id)
        await self._cancel_tts()
        await self._set_state(VoiceState.CANCELLED)
        self._running = False
