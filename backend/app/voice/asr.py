"""ASR client: oMLX /v1/audio/transcriptions (Parakeet-TDT / Qwen3-ASR).

The oMLX endpoint is OpenAI-compatible: multipart file upload with a model
field. We wrap raw PCM16 16 kHz samples into a WAV before upload.
"""

from __future__ import annotations

import io
import wave

import httpx

from app.core.logging import get_logger

_logger = get_logger("app.voice.asr")


class ASRClient:
    """Transcribe PCM16 audio via the local oMLX runtime."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str | None = None,
        model: str = "parakeet-tdt-0.6b-v3-int8",
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

    @staticmethod
    def pcm16_to_wav(pcm: bytes, sample_rate: int = 16000) -> bytes:
        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(sample_rate)
            w.writeframes(pcm)
        return buf.getvalue()

    async def transcribe(self, pcm16: bytes, *, sample_rate: int = 16000) -> str:
        """Transcribe PCM16 mono audio; returns transcript text."""
        wav = self.pcm16_to_wav(pcm16, sample_rate)
        files = {"file": ("speech.wav", wav, "audio/wav")}
        data = {"model": self.model, "response_format": "json"}
        resp = await self._client.post(
            f"{self.base_url}/audio/transcriptions",
            headers=self._headers,
            files=files,
            data=data,
        )
        resp.raise_for_status()
        payload = resp.json()
        text = (payload.get("text") or "").strip()
        _logger.info("asr transcript: chars=%d model=%s", len(text), self.model)
        return text
