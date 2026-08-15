"""Pocket TTS provider + configuration-driven provider selection tests.

Uses a fake pocket_tts module (monkeypatched into sys.modules) and a fake
chunk converter — no torch, no model download, no oMLX. Covers: lazy load,
single fixed voice, full-utterance synthesize, streaming yields, bounded
cancellation, serialization, error propagation, and the _build_tts factory.
"""

from __future__ import annotations

import asyncio
import sys
import types

import pytest

from app.voice import pocket as pocket_mod
from app.voice.pocket import PocketTTSProvider


class FakeGenerator:
    """Yields a fixed number of fake chunks; each is 'converted' by _pcm16."""

    def __init__(self, chunks: int, *, delay: float = 0.0) -> None:
        self._chunks = chunks
        self._delay = delay
        self._calls = 0

    def __iter__(self):
        return self

    def __next__(self):
        if self._calls >= self._chunks:
            raise StopIteration
        self._calls += 1
        if self._delay:
            import time

            time.sleep(self._delay)
        return self._calls  # fake "tensor"


class FakeModel:
    def __init__(self, chunks: int = 3, *, delay: float = 0.0) -> None:
        self.chunks = chunks
        self.delay = delay
        self.loaded_with: dict[str, object] = {}
        self.sample_rate = 24000
        self.state_from: list[str] = []
        self.generated: list[str] = []

    def get_state_for_audio_prompt(self, voice: str) -> dict[str, object]:
        self.state_from.append(voice)
        return {"voice": voice}

    def generate_audio_stream(self, state: dict[str, object], text: str):
        self.generated.append(text)
        return FakeGenerator(self.chunks, delay=self.delay)


@pytest.fixture
def fake_pocket(monkeypatch: pytest.MonkeyPatch) -> FakeModel:
    model = FakeModel(chunks=4)

    class _TTSModel:
        @staticmethod
        def load_model(*, quantize: bool = False) -> FakeModel:
            model.loaded_with["quantize"] = quantize
            return model

    monkeypatch.setitem(sys.modules, "pocket_tts", types.SimpleNamespace(TTSModel=_TTSModel))
    monkeypatch.setattr(pocket_mod, "_pcm16", lambda c: b"\x10\x00" * (c * 100))
    return model


async def _load(provider: PocketTTSProvider) -> None:
    await provider._ensure_loaded()  # noqa: SLF001


@pytest.mark.asyncio
async def test_pocket_provider_lazy_loads_once_with_fixed_voice(fake_pocket: FakeModel) -> None:
    p = PocketTTSProvider(voice="alba", quantize=True)
    assert p._model is None  # noqa: SLF001 — lazy: nothing loaded at construction
    await _load(p)
    assert fake_pocket.loaded_with == {"quantize": True}
    assert fake_pocket.state_from == ["alba"], "one fixed voice loaded once"
    await _load(p)  # second load is a no-op
    assert fake_pocket.state_from == ["alba"]


@pytest.mark.asyncio
async def test_pocket_provider_synthesize_returns_pcm16_24k(fake_pocket: FakeModel) -> None:
    p = PocketTTSProvider()
    pcm, sr = await p.synthesize("Tell me about yourself.")
    assert sr == 24000
    assert len(pcm) > 4
    assert pcm == b"".join(b"\x10\x00" * (c * 100) for c in range(1, 5))


@pytest.mark.asyncio
async def test_pocket_provider_stream_yields_chunks(fake_pocket: FakeModel) -> None:
    p = PocketTTSProvider()
    got: list[bytes] = []
    async for chunk in p.synthesize_stream("Hello there."):
        got.append(chunk)
    assert len(got) == 4
    assert got[0] == b"\x10\x00" * 100
    assert fake_pocket.generated == ["Hello there."]


@pytest.mark.asyncio
async def test_pocket_provider_stream_cancel_stops_consumption(fake_pocket: FakeModel) -> None:
    fake_pocket.chunks = 1000  # long stream
    p = PocketTTSProvider()

    async def consume() -> list[bytes]:
        got: list[bytes] = []
        async for chunk in p.synthesize_stream("Long text."):
            got.append(chunk)
            if len(got) == 2:
                raise asyncio.CancelledError
        return got

    with pytest.raises(asyncio.CancelledError):
        await consume()
    # Cancellation is bounded and does not hang; the provider remains usable.
    pcm, _ = await p.synthesize("Still works.")
    assert len(pcm) > 4


@pytest.mark.asyncio
async def test_pocket_provider_serializes_generations(fake_pocket: FakeModel) -> None:
    fake_pocket.chunks = 20
    fake_pocket.delay = 0.01
    p = PocketTTSProvider()
    results = await asyncio.gather(
        p.synthesize("one"),
        p.synthesize("two"),
        p.synthesize("three"),
    )
    assert len(results) == 3
    assert all(len(pcm) > 4 for pcm, _sr in results)


@pytest.mark.asyncio
async def test_pocket_provider_empty_text_raises(fake_pocket: FakeModel) -> None:
    p = PocketTTSProvider()
    with pytest.raises(ValueError, match="empty TTS text"):
        await p.synthesize("   ")
    with pytest.raises(ValueError, match="empty TTS text"):
        async for _ in p.synthesize_stream(""):
            pass  # pragma: no cover


class _FakeSettings:
    def __init__(self, provider: str) -> None:
        self.tts_provider = provider
        self.pocket_tts_voice = "alba"
        self.pocket_tts_quantize = False
        self.voice_chunk_samples = 4800
        self.omlx_base_url = "http://x"
        self.omlx_api_key = None
        self.voice_tts_model = "m"
        self.omlx_timeout_seconds = 120.0


def test_build_tts_selects_pocket_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.api.v1 import voice as voice_mod

    monkeypatch.setitem(sys.modules, "pocket_tts", types.SimpleNamespace(TTSModel=object))
    voice = types.SimpleNamespace(provider_voice="default", voice_id="vid")
    provider = voice_mod._build_tts(_FakeSettings("pocket"), voice)  # noqa: SLF001
    assert isinstance(provider, PocketTTSProvider)


def test_build_tts_defaults_to_qwen3(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.api.v1 import voice as voice_mod

    voice = types.SimpleNamespace(provider_voice="default", voice_id="vid")
    provider = voice_mod._build_tts(_FakeSettings("qwen3"), voice)  # noqa: SLF001
    assert type(provider).__name__ == "TTSClient"
