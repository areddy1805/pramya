"""V1.1 realtime voice unit tests: text segmentation, question parsing,
voice identity determinism, and router/LangChain streaming.

No real oMLX / DeepSeek / DB — pure logic + fakes.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest

from app.ai.contracts import ChatRequest, ChatResponse, ChatStreamChunk, Usage
from app.ai.langchain.model import RouterChatModel
from app.ai.policy import TaskClass, TaskPolicyTable
from app.ai.router import InferenceRouter
from app.core.config import Settings
from app.domain.errors import ValidationFailedError
from app.interview.generation import parse_question_output
from app.voice.profile import resolve_interviewer_voice
from app.voice.segmenter import TextSegmenter

# ---------------------------------------------------------------------------
# R6 — text segmenter
# ---------------------------------------------------------------------------


def test_segmenter_emits_complete_sentences_only() -> None:
    seg = TextSegmenter(min_chars=10)
    out = seg.feed("That's a reasonable approach. ")
    assert out == ["That's a reasonable approach."]
    out = seg.feed("I would first separate the transactional boundary")
    assert out == []
    out = seg.feed(" from the messaging layer.")
    assert out == ["I would first separate the transactional boundary from the messaging layer."]
    assert seg.flush() == ""


def test_segmenter_never_splits_mid_word() -> None:
    seg = TextSegmenter(min_chars=20, max_chars=30)
    # No punctuation, no spaces: the hard-flush keeps the WHOLE buffer as one
    # segment rather than cutting mid-word (documented behavior).
    out = seg.feed("a" * 60)
    assert out == ["a" * 60]
    # With safe space boundaries present, segments never carry leading or
    # trailing whitespace and the content is preserved.
    seg2 = TextSegmenter(min_chars=20, max_chars=30)
    out2 = seg2.feed("word " * 20)
    assert out2
    assert all(w and not w.startswith(" ") and not w.endswith(" ") for w in out2)
    assert " ".join(out2).replace("  ", " ") == ("word " * 20).strip()


def test_segmenter_flush_returns_remainder() -> None:
    seg = TextSegmenter(min_chars=100)
    seg.feed("Short tail without punctuation")
    assert seg.flush() == "Short tail without punctuation"


def test_segmenter_ignores_whitespace_only() -> None:
    seg = TextSegmenter(min_chars=5)
    assert seg.feed("   \n\t  ") == []
    assert seg.feed("Hello world. ") == ["Hello world."]


# ---------------------------------------------------------------------------
# R5/R6 — streamed question output parsing
# ---------------------------------------------------------------------------


def test_parse_question_output_happy_path() -> None:
    text = (
        "QUESTION: How would you design a retry mechanism for a payments service?\n"
        "TYPE: system_design\n"
        "DIFFICULTY: hard\n"
        "RATIONALE: Probes tradeoff awareness\n"
        "TARGET: System Design\n"
        "HINTS:\n"
        "- Start with failure modes\n"
        "- Consider idempotency\n"
        "- Sketch backoff with jitter"
    )
    q = parse_question_output(text, default_competency="System Design")
    assert q.text == "How would you design a retry mechanism for a payments service?"
    assert q.type == "system_design"
    assert q.difficulty == "hard"
    assert q.rationale == "Probes tradeoff awareness"
    assert len(q.hint_levels) == 3
    assert q.target_competency == "System Design"


def test_parse_question_output_multiline_question_and_defaults() -> None:
    text = (
        "QUESTION: First sentence of the question.\n"
        "Second sentence continues.\n"
        "DIFFICULTY: medium\n"
        "HINTS:\n"
        "- one"
    )
    q = parse_question_output(text, default_competency="Kubernetes")
    assert q.text == "First sentence of the question. Second sentence continues."
    assert q.type == "general"  # missing -> default
    assert q.difficulty == "medium"
    assert q.target_competency == "Kubernetes"  # missing -> default competency


def test_parse_question_output_rejects_empty() -> None:
    with pytest.raises(ValidationFailedError):
        parse_question_output("DIFFICULTY: medium\nHINTS:\n- x", default_competency="g")


# ---------------------------------------------------------------------------
# R2 — deterministic voice identity
# ---------------------------------------------------------------------------


def test_interviewer_voice_is_deterministic() -> None:
    settings = Settings(
        interviewer_voice_id="professional_female_01",
        interviewer_voice_name="Professional Female 01",
        interviewer_voice_style="professional",
    )
    v1 = resolve_interviewer_voice(settings)
    v2 = resolve_interviewer_voice(settings)
    assert v1.voice_id == v2.voice_id == "professional_female_01"
    assert v1.provider == "omlx"
    assert v1.provider_voice == "default"  # Qwen3-TTS single-speaker mapping
    assert v1.language == "en-US"
    assert v1.style == "professional"
    assert v1.enabled is True


def test_voice_profile_defaults_when_unset() -> None:
    settings = Settings()  # defaults
    v = resolve_interviewer_voice(settings)
    assert v.voice_id == "professional_female_01"
    assert v.provider_voice == "default"


def test_tts_client_uses_same_voice_for_every_call() -> None:
    """Regression (R2): multiple TTS generations in a session must all use
    the SAME provider voice — never a random choice."""
    import io
    import struct
    import wave

    from app.voice.tts import TTSClient

    captured: list[dict[str, object]] = []
    wav_buf = io.BytesIO()
    with wave.open(wav_buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(24000)
        w.writeframes(struct.pack("<8h", 0, 100, 200, 100, 0, -100, -200, -100))

    class _FakeResp:
        content = wav_buf.getvalue()

        def raise_for_status(self) -> None:
            return None

    class _FakeClient:
        async def post(
            self,
            url: str,
            *,
            headers: dict[str, str] | None = None,
            json: dict[str, object] | None = None,
        ) -> Any:
            captured.append(json or {})
            return _FakeResp()

        async def stream(self, *args: Any, **kwargs: Any) -> Any:
            raise NotImplementedError

    tts = TTSClient(
        base_url="http://x/v1",
        model="Qwen3-TTS",
        voice="default",
        voice_id="professional_female_01",
        client=_FakeClient(),  # type: ignore[arg-type]
    )
    for _ in range(5):
        import asyncio

        asyncio.run(tts.synthesize("hello"))
    voices = {c.get("voice") for c in captured if c}
    assert voices == {"default"}
    assert len(captured) == 5


# ---------------------------------------------------------------------------
# R5 — router streaming (fallback + real streaming provider)
# ---------------------------------------------------------------------------


class _FakeProvider:
    name = "fake"

    def __init__(self, deltas: list[str] | None = None) -> None:
        self.deltas = deltas

    async def generate(self, request: ChatRequest) -> ChatResponse:
        return ChatResponse(
            content="".join(self.deltas or []),
            model="fake",
            usage=Usage(total_tokens=1),
        )

    async def supports_stream(self) -> bool:
        return self.deltas is not None

    def stream(self, request: ChatRequest) -> AsyncIterator[ChatStreamChunk]:
        async def _gen() -> AsyncIterator[ChatStreamChunk]:
            for d in self.deltas or []:
                yield ChatStreamChunk(delta=d, model="fake")
            yield ChatStreamChunk(delta="", model="fake", finish_reason="stop")

        return _gen()


class _NonStreamingProvider:
    """Legacy provider: generate() only, no stream surface."""

    name = "fake-ns"

    async def generate(self, request: ChatRequest) -> ChatResponse:
        return ChatResponse(content="hello world", model="fake", usage=Usage(total_tokens=1))


@pytest.mark.asyncio
async def test_router_stream_falls_back_for_non_streaming_provider() -> None:
    router = InferenceRouter(policy=TaskPolicyTable(), deepseek=_NonStreamingProvider())  # type: ignore[arg-type]
    chunks: list[tuple[Any, str]] = []
    async for decision, delta in router.stream(TaskClass.INTERVIEW_CONTENT_GENERATION, []):
        chunks.append((decision, delta))
    assert len(chunks) == 1
    assert chunks[0][1] == "hello world"
    assert chunks[0][0] is not None  # decision on the single chunk


@pytest.mark.asyncio
async def test_router_stream_yields_deltas_with_first_decision() -> None:
    provider = _FakeProvider(deltas=["Hello ", "world. ", "Next."])
    router = InferenceRouter(policy=TaskPolicyTable(), deepseek=provider)  # type: ignore[arg-type]
    chunks: list[tuple[Any, str]] = []
    async for decision, delta in router.stream(TaskClass.INTERVIEW_CONTENT_GENERATION, []):
        chunks.append((decision, delta))
    # The provider emits a final empty chunk (finish_reason) — forwarded as-is.
    assert [c[1] for c in chunks] == ["Hello ", "world. ", "Next.", ""]
    assert chunks[0][0] is not None
    assert all(c[0] is None for c in chunks[1:])


@pytest.mark.asyncio
async def test_router_chat_model_astream_yields_message_chunks() -> None:
    provider = _FakeProvider(deltas=["Q: ", "Tell me ", "about x?"])
    router = InferenceRouter(policy=TaskPolicyTable(), deepseek=provider)  # type: ignore[arg-type]
    model = RouterChatModel(router=router, task=TaskClass.INTERVIEW_CONTENT_GENERATION)
    from langchain_core.messages import HumanMessage

    parts: list[str] = []
    async for chunk in model.astream([HumanMessage(content="hi")]):
        parts.append(str(chunk.content))
    assert "".join(parts) == "Q: Tell me about x?"
    assert model.last_decision is not None
    assert model.last_decision.model == "deepseek-v4-flash"


__all__: list[str] = []
