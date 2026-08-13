"""RouterChatModel — LangChain chat model bound to the InferenceRouter.

LangChain composes (prompt templates, runnables, output parsers); the
router still decides provider/model per the task policy (DeepSeek for all
text — ADR-023). No bypass of the router, no silent local text fallback.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

from langchain_core.callbacks import AsyncCallbackManagerForLLMRun, CallbackManagerForLLMRun
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    AIMessageChunk,
    BaseMessage,
    HumanMessage,
    SystemMessage,
)
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult
from pydantic import PrivateAttr

from app.ai.contracts import ChatMessage as RouterChatMessage
from app.ai.policy import TaskClass
from app.ai.router import InferenceRouter, RouterDecision, RouterResult


class RouterChatModel(BaseChatModel):
    """A LangChain chat model that routes every call through InferenceRouter.

    Constructor takes the router + the task class so the policy table decides
    the concrete provider/model per call (never the caller). Supports
    ``json_mode`` / ``thinking`` / ``temperature`` / ``max_tokens`` via
    pydantic fields, so LangChain ``bind(**kwargs)`` and
    ``with_structured_output`` compose normally.
    """

    # pydantic fields (LangChain BaseChatModel is a pydantic model).
    task: TaskClass
    json_mode: bool = False
    thinking: bool | None = None
    temperature: float | None = None
    max_tokens: int | None = None

    # Non-serializable dependencies (kept private, not part of the model).
    _router: InferenceRouter = PrivateAttr(default=None)  # type: ignore[assignment]
    _last_decision: RouterDecision | None = PrivateAttr(default=None)
    _last_result: RouterResult | None = PrivateAttr(default=None)

    def __init__(self, *, router: InferenceRouter, task: TaskClass, **kwargs: Any) -> None:
        super().__init__(task=task, **kwargs)  # type: ignore[call-arg]
        self._router = router
        self._last_decision = None

    @property
    def _llm_type(self) -> str:
        return "pramya-router"

    @property
    def last_decision(self) -> RouterDecision | None:
        """Most recent routing decision (observability; never None after a call)."""
        return self._last_decision

    @property
    def last_result(self) -> RouterResult | None:
        """Full RouterResult of the most recent call (telemetry payload)."""
        return self._last_result

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        """Sync path: run the async core on a fresh loop when no loop is active."""
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self._agenerate(messages, stop=stop, **kwargs))
        raise RuntimeError(
            "RouterChatModel._generate is sync-only; use ainvoke/agenerate in async code"
        )

    async def _agenerate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: AsyncCallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        chat_messages = [self._to_router_message(m) for m in messages]
        result = await self._router.generate(
            self.task,
            chat_messages,
            json_mode=self.json_mode,
            thinking=self.thinking,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )
        self._last_decision = result.decision
        self._last_result = result
        return ChatResult(
            generations=[ChatGeneration(message=AIMessage(content=result.response.content))],
            llm_output={
                "model": result.decision.model,
                "provider": result.decision.provider,
                "degraded": result.decision.degraded,
            },
        )

    async def _astream(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: AsyncCallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> AsyncIterator[ChatGenerationChunk]:
        """Stream tokens through the router (V1.1 realtime path).

        Yields one ChatGenerationChunk per router stream delta; emits
        on_llm_new_token so LangGraph ``stream_mode="messages"`` can surface
        them. The router falls back to a single chunk for non-streaming
        providers.
        """
        chat_messages = [self._to_router_message(m) for m in messages]
        first = True
        async for decision, delta in self._router.stream(
            self.task,
            chat_messages,
            json_mode=self.json_mode,
            thinking=self.thinking,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        ):
            if first and decision is not None:
                self._last_decision = decision
                first = False
            if not delta:
                continue
            if run_manager is not None:
                await run_manager.on_llm_new_token(delta)
            yield ChatGenerationChunk(
                message=AIMessageChunk(content=delta),
                generation_info=None,
            )

    @staticmethod
    def _to_router_message(message: BaseMessage) -> RouterChatMessage:
        if isinstance(message, SystemMessage):
            return RouterChatMessage(role="system", content=str(message.content))
        if isinstance(message, HumanMessage):
            return RouterChatMessage(role="user", content=str(message.content))
        return RouterChatMessage(role="assistant", content=str(message.content))
