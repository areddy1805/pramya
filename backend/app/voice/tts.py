"""TTS client: oMLX /v1/audio/speech (Qwen3-TTS-12Hz).

V1.1 realtime support (R7):
- ``synthesize_stream`` uses oMLX native TTS streaming (``stream: true``):
  the server yields a 44-byte WAV header followed by PCM16 24 kHz chunks as
  the model generates them, so the FIRST audio arrives long before the full
  utterance is synthesized.
- ``synthesize`` (full-utterance WAV) remains for the V1 fallback path and
  tests.

Voice identity (R2): the caller resolves ONE deterministic
``InterviewerVoiceProfile`` per session; the client maps the profile's
provider-level voice (Qwen3-TTS exposes a single speaker: "default") and
carries ``voice_id`` for diagnostics. There is no random voice selection
here or anywhere in the call path.
"""

from __future__ import annotations

import io
import wave
from collections.abc import AsyncIterator
from typing import Protocol, runtime_checkable

import httpx

from app.core.logging import get_logger

_logger = get_logger("app.voice.tts")

_WAV_HEADER_BYTES = 44  # oMLX streamed TTS uses the standard 44-byte header


@runtime_checkable
class TTSSynthesizer(Protocol):
    """TTS provider seam consumed by the voice engine (duck-typed).

    Implementations: :class:`TTSClient` (Qwen3 via oMLX) and
    :class:`app.voice.pocket.PocketTTSProvider` (Kyutai pocket-tts). The
    engine never branches on the concrete provider; providers advertise
    native per-chunk streaming via ``supports_stream`` and the engine
    relays streamed PCM as generated when available.
    """

    supports_stream: bool

    async def synthesize(self, text: str) -> tuple[bytes, int]: ...

    def synthesize_stream(
        self, text: str, *, streaming_interval: float = 1.0
    ) -> AsyncIterator[bytes]: ...

    async def warmup(self) -> None: ...


class TTSClient:
    """Synthesize speech via the local oMLX runtime (single provider voice)."""

    supports_stream: bool = False  # production path is per-segment full-WAV

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str | None = None,
        model: str = "Qwen3-TTS-12Hz-0.6B-Base-MLX-4bit",
        voice: str = "default",
        voice_id: str | None = None,
        timeout_seconds: float = 120.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.voice = voice  # provider-level voice name (deterministic)
        self.voice_id = voice_id  # identity for diagnostics/telemetry
        self._client = client or httpx.AsyncClient(timeout=timeout_seconds)
        headers: dict[str, str] = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        self._headers = headers

    async def synthesize(self, text: str) -> tuple[bytes, int]:
        """Return (pcm16 frames, sample_rate). Raises on HTTP/parse error."""
        payload = {
            "model": self.model,
            "input": text,
            "voice": self.voice,
            "response_format": "wav",
        }
        resp = await self._client.post(
            f"{self.base_url}/audio/speech",
            headers=self._headers,
            json=payload,
        )
        resp.raise_for_status()
        wav = resp.content
        sample_rate, frames = _parse_wav_pcm(wav)
        _logger.info(
            "tts synthesized: text_chars=%d pcm_bytes=%d sr=%d model=%s",
            len(text),
            len(frames),
            sample_rate,
            self.model,
        )
        return frames, sample_rate

    async def synthesize_stream(
        self,
        text: str,
        *,
        streaming_interval: float = 1.0,
    ) -> AsyncIterator[bytes]:
        """Stream TTS: yields raw PCM16 frames as the model generates them.

        The oMLX streamed response is a 44-byte WAV header followed by PCM
        chunks; the header is stripped here so callers receive raw PCM
        (sample rate 24000). Cancelling the consuming task closes the HTTP
        stream (interrupt-safe).
        """
        payload = {
            "model": self.model,
            "input": text,
            "voice": self.voice,
            "response_format": "wav",
            "stream": True,
            "streaming_interval": streaming_interval,
        }
        total_pcm = 0
        header_buf = bytearray()
        try:
            async with self._client.stream(
                "POST",
                f"{self.base_url}/audio/speech",
                headers=self._headers,
                json=payload,
            ) as resp:
                resp.raise_for_status()
                async for raw in resp.aiter_bytes():
                    if len(header_buf) < _WAV_HEADER_BYTES:
                        need = _WAV_HEADER_BYTES - len(header_buf)
                        header_buf.extend(raw[:need])
                        pcm = raw[need:]
                    else:
                        pcm = raw
                    if pcm:
                        total_pcm += len(pcm)
                        yield pcm
        finally:
            _logger.info(
                "tts streamed: text_chars=%d pcm_bytes=%d sr=24000 model=%s voice=%s",
                len(text),
                total_pcm,
                self.model,
                self.voice,
            )

    async def warmup(self) -> None:
        """Warm the TTS runtime (model resident) with a tiny synthesis.

        Best-effort: a failed warmup is logged and ignored — the next real
        synthesis will load the model on demand.
        """
        try:
            payload = {
                "model": self.model,
                "input": "Okay.",
                "voice": self.voice,
                "response_format": "wav",
            }
            resp = await self._client.post(
                f"{self.base_url}/audio/speech",
                headers=self._headers,
                json=payload,
            )
            if resp.status_code == 200 and resp.content:
                _logger.info("tts warmup ok: %d bytes", len(resp.content))
        except Exception as exc:  # noqa: BLE001 — warmup must never fail the session
            _logger.warning("tts warmup failed: %s", exc)


def _parse_wav_pcm(wav: bytes) -> tuple[int, bytes]:
    """Extract (sample_rate, pcm16 frames) from a WAV blob."""
    with wave.open(io.BytesIO(wav), "rb") as w:
        nch = w.getnchannels()
        sw = w.getsampwidth()
        sr = w.getframerate()
        if nch != 1 or sw != 2:
            raise ValueError(f"unexpected WAV format: channels={nch} width={sw}")
        frames = w.readframes(w.getnframes())
    if len(frames) < 4:
        raise ValueError("TTS produced empty audio")
    return sr, frames


def chunk_pcm16(frames: bytes, chunk_samples: int) -> list[bytes]:
    """Split PCM16 mono frames into fixed-size chunks (byte-aligned)."""
    if chunk_samples < 1:
        raise ValueError("chunk_samples must be >= 1")
    frame_size = 2
    chunk_bytes = chunk_samples * frame_size
    return [frames[i : i + chunk_bytes] for i in range(0, len(frames), chunk_bytes)]


__all__ = ["TTSClient", "chunk_pcm16", "_parse_wav_pcm"]
