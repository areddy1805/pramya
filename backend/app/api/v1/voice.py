"""Voice interview WebSocket endpoint (Phase 9).

WS /ws/voice/{interview_id}?user_id=N

Client -> server: JSON control (start_turn, end_turn, interrupt, pause,
resume, stop, cancel) and binary PCM16 16 kHz mono audio frames.
Server -> client: JSON events (state, question, tts_start/stop,
partial_transcript, final_transcript, evaluation, error) and binary
PCM16 24 kHz playback chunks.

The server is the authoritative state machine (VoiceEngine); the client
mirrors states and never invents transitions.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.factory import build_inference_router
from app.core.config import get_settings
from app.core.db import get_session
from app.core.logging import get_logger
from app.interview.service import InterviewService
from app.knowledge.retrieval import RetrievalService
from app.voice.asr import ASRClient
from app.voice.engine import VoiceEngine, VoiceWS
from app.voice.tts import TTSClient

_logger = get_logger("app.api.v1.voice")

router = APIRouter()

SessionDep = Annotated[AsyncSession, Depends(get_session)]


class _WSAdapter(VoiceWS):
    """Adapts FastAPI WebSocket to the engine's minimal interface."""

    def __init__(self, ws: WebSocket) -> None:
        self._ws = ws

    async def receive(self) -> tuple[str, object]:
        msg = await self._ws.receive()
        if msg.get("type") == "websocket.disconnect":
            raise WebSocketDisconnect()
        if "bytes" in msg and msg["bytes"] is not None:
            return ("bytes", msg["bytes"])
        if "text" in msg and msg["text"] is not None:
            return ("json", msg["text"])
        raise WebSocketDisconnect()

    async def send_json(self, payload: dict[str, object]) -> None:
        await self._ws.send_json(payload)

    async def send_bytes(self, payload: bytes) -> None:
        await self._ws.send_bytes(payload)

    async def close(self, code: int = 1000) -> None:
        await self._ws.close(code=code)


def _engine(
    session: AsyncSession,
    session_id: int,
    user_id: int,
) -> VoiceEngine:
    settings = get_settings()
    router = build_inference_router(settings)
    retrieval = RetrievalService(session, router)
    interview = InterviewService(session, router, retrieval=retrieval)
    asr = ASRClient(
        base_url=settings.omlx_base_url,
        api_key=settings.omlx_api_key,
        model=settings.voice_live_asr_model,  # Parakeet-TDT: live ASR (H.4)
        timeout_seconds=settings.omlx_timeout_seconds,
    )
    tts = TTSClient(
        base_url=settings.omlx_base_url,
        api_key=settings.omlx_api_key,
        model=settings.voice_tts_model,  # Qwen3-TTS (H.4)
        timeout_seconds=settings.omlx_timeout_seconds,
    )
    return VoiceEngine(
        interview=interview,
        asr=asr,
        tts=tts,
        session_id=session_id,
        user_id=user_id,
        chunk_samples=settings.voice_chunk_samples,
        silence_seconds=settings.voice_silence_seconds,
        speech_rms=settings.voice_speech_rms,
        audio_storage_dir=str(settings.audio_storage_path),
        store_audio=settings.voice_store_audio,
        retention_days=settings.voice_retention_days,
    )


@router.websocket("/ws/voice/{interview_id}")
async def voice_ws(
    websocket: WebSocket,
    interview_id: int,
    user_id: int = Query(...),
    session: SessionDep = None,  # type: ignore[assignment]
) -> None:
    await websocket.accept()
    _logger.info("voice ws connect: session=%d user=%d", interview_id, user_id)
    engine = _engine(session, interview_id, user_id)
    adapter = _WSAdapter(websocket)
    await engine.run(adapter)
