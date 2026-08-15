"""Pocket TTS provider: Kyutai pocket-tts (CPU, in-process).

Provider behind the voice engine's TTS seam (duck-typed ``synthesize`` /
``synthesize_stream`` / ``warmup``, plus ``supports_stream``), selected via
``TTS_PROVIDER=pocket``. Model + one fixed voice are loaded once and reused
across utterances (no per-utterance reload, no voice-selection complexity).

Threading model:
- All CPU work (torch) runs in short-lived worker threads via the event
  loop's default executor; the event loop is never blocked.
- A single ``asyncio.Lock`` serializes generations (the upstream streaming
  API is documented as not thread-safe; Pramya needs one generation at a
  time anyway).
- Cancellation is bounded: closing the async generator stops consumption;
  the worker finishes only the sentence chunk already in flight (upstream
  decodes per sentence via a daemon thread) then exits. No audio is
  delivered after cancellation because the consumer stops pulling.

Errors surface as provider-level exceptions (ValueError for bad input,
RuntimeError for model/generation failures) which the engine degrades
gracefully (skip segment / tts_unavailable).

Model/voice licensing: pocket-tts package is MIT; the weights
(kyutai/pocket-tts-without-voice-cloning) are CC-BY-4.0; the built-in
reference voice ("alba", kyutai/tts-voices) carries its own attribution.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

from app.core.logging import get_logger

_logger = get_logger("app.voice.pocket")


class _Sentinel:
    """Queue marker type (error) — distinct from bytes and None end-of-stream."""


_ERR = _Sentinel()  # queue item carrying a worker exception


def _pcm16(chunk: Any) -> bytes:
    """float32 torch tensor [samples] -> PCM16 mono bytes (worker thread)."""
    import torch

    arr = torch.clamp(chunk, -1.0, 1.0)
    return (arr * 32767).to(torch.int16).numpy().tobytes()


class PocketTTSProvider:
    """Kyutai Pocket TTS: CPU in-process synthesis, single fixed voice."""

    supports_stream = True  # engine relays per-chunk PCM as generated

    def __init__(
        self,
        *,
        voice: str = "alba",
        quantize: bool = False,
        chunk_samples: int = 4800,
    ) -> None:
        self._voice = voice
        self._quantize = quantize
        self._chunk_samples = chunk_samples
        self._model: Any = None
        self._voice_state: Any = None
        self._sample_rate = 24000
        self._lock = asyncio.Lock()

    # -- lifecycle ----------------------------------------------------------

    async def _ensure_loaded(self) -> None:
        if self._model is not None:
            return
        async with self._lock:
            if self._model is not None:
                return

            def load() -> tuple[Any, Any]:
                # Lazy import: the backend runs without pocket-tts until
                # TTS_PROVIDER=pocket is configured.
                from pocket_tts import TTSModel  # pyright: ignore[reportMissingTypeStubs]

                model: Any = TTSModel.load_model(quantize=self._quantize)
                state: Any = model.get_state_for_audio_prompt(self._voice)
                return model, state

            loop = asyncio.get_running_loop()
            model, state = await loop.run_in_executor(None, load)
            self._model = model
            self._voice_state = state
            self._sample_rate = int(model.sample_rate)
            _logger.info(
                "pocket tts loaded: voice=%s quantize=%s sr=%d",
                self._voice,
                self._quantize,
                self._sample_rate,
            )

    async def warmup(self) -> None:
        """Load the model and run one tiny utterance (engine awaits this
        before the first question so cold-load never stalls first audio)."""
        await self._ensure_loaded()
        await self.synthesize("Okay.")

    # -- generation ----------------------------------------------------------

    def _run_worker(
        self, text: str, loop: asyncio.AbstractEventLoop
    ) -> tuple[asyncio.Queue[bytes | _Sentinel | None], asyncio.Future[None]]:
        """Start the sync generator in a worker thread; returns (queue, task).

        The worker converts each streamed chunk to PCM16 and pushes it onto
        the queue via the loop; a sentinel marks normal end, an error marker
        carries the worker exception. The worker only finishes the sentence
        chunk already in flight after the consumer stops pulling.
        """
        q: asyncio.Queue[bytes | _Sentinel | None] = asyncio.Queue()
        model, voice_state = self._model, self._voice_state

        def worker() -> None:
            try:
                for chunk in model.generate_audio_stream(voice_state, text):
                    try:
                        loop.call_soon_threadsafe(q.put_nowait, _pcm16(chunk))
                    except RuntimeError:  # loop closed
                        return
            except Exception as exc:  # noqa: BLE001 — surfaced via sentinel
                _logger.warning("pocket tts generation failed: %s", exc)
                try:
                    loop.call_soon_threadsafe(q.put_nowait, _ERR)
                except RuntimeError:
                    pass
            finally:
                try:
                    loop.call_soon_threadsafe(q.put_nowait, None)
                except RuntimeError:
                    pass

        fut = loop.run_in_executor(None, worker)
        return q, fut

    async def synthesize(self, text: str) -> tuple[bytes, int]:
        """Return (pcm16 frames, sample_rate) for the full utterance."""
        if not text or not text.strip():
            raise ValueError("empty TTS text")
        await self._ensure_loaded()
        loop = asyncio.get_running_loop()
        async with self._lock:
            q, fut = self._run_worker(text, loop)
            out: list[bytes] = []
            while True:
                item = await q.get()
                if isinstance(item, _Sentinel):
                    raise RuntimeError("Pocket TTS generation failed")
                if item is None:
                    break
                out.append(item)
            await fut  # propagate worker exceptions / join
        pcm = b"".join(out)
        if len(pcm) < 4:
            raise RuntimeError("Pocket TTS produced empty audio")
        _logger.info(
            "pocket tts synthesized: text_chars=%d pcm_bytes=%d sr=%d voice=%s",
            len(text),
            len(pcm),
            self._sample_rate,
            self._voice,
        )
        return pcm, self._sample_rate

    async def synthesize_stream(
        self, text: str, *, streaming_interval: float = 1.0
    ) -> AsyncIterator[bytes]:
        """Yield PCM16 mono chunks (80 ms each) as the model generates them.

        The first chunk flows ~30-100 ms after synthesis starts — long before
        the full utterance exists. Cancelling the consuming task stops
        delivery immediately; the worker's in-flight sentence tail is bounded
        and its output is discarded.
        """
        if not text or not text.strip():
            raise ValueError("empty TTS text")
        await self._ensure_loaded()
        loop = asyncio.get_running_loop()
        async with self._lock:
            q, fut = self._run_worker(text, loop)
            try:
                while True:
                    item = await q.get()
                    if isinstance(item, _Sentinel):
                        raise RuntimeError("Pocket TTS generation failed")
                    if item is None:
                        break
                    yield item
                await fut  # normal end: join the worker
            finally:
                # Cancellation: stop pulling. The worker's daemon decode
                # thread finishes the in-flight sentence only.
                if not fut.done():
                    fut.cancel()


__all__ = ["PocketTTSProvider"]
