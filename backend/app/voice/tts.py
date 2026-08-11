"""TTS client: oMLX /v1/audio/speech (Qwen3-TTS-12Hz).

oMLX returns a complete WAV (PCM16 mono 24 kHz). We parse the WAV and
expose the raw PCM frames for chunked streaming to the browser, plus the
sample rate so the client can configure its playback context.
"""

from __future__ import annotations

import io
import wave

import httpx

from app.core.logging import get_logger

_logger = get_logger("app.voice.tts")


class TTSClient:
    """Synthesize speech via the local oMLX runtime."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str | None = None,
        model: str = "Qwen3-TTS-12Hz-0.6B-Base-MLX-4bit",
        timeout_seconds: float = 120.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
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
            "voice": "default",
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
