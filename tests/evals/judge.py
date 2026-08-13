"""Router-bound DeepEval judge (Phase F).

DeepEval semantic metrics need an LLM judge. This judge is a thin
DeepEvalBaseLLM adapter over Pramya's InferenceRouter — every judge call
goes through the router (deepseek-v4-flash, temperature 0), never a raw
provider, never a local text LLM. The architectural rule that application
and test code must not bypass the router is preserved.

When DEEPSEEK_API_KEY is absent the semantic suite skips (see conftest);
deterministic evals always run.
"""

from __future__ import annotations

from typing import Any

from deepeval.models import DeepEvalBaseLLM

from app.ai.contracts import ChatMessage
from app.ai.policy import TaskClass
from app.ai.router import InferenceRouter


class RouterJudgeLLM(DeepEvalBaseLLM):
    """DeepEval judge delegating every call to InferenceRouter.

    DeepEval 4.x calls ``a_generate(prompt)`` / ``a_generate_with_schema``;
    both are routed. No local text models are ever loaded.
    """

    def __init__(self, router: InferenceRouter) -> None:
        super().__init__(model="deepseek-v4-flash")
        self._router = router
        self.name = "deepseek-v4-flash"

    def load_model(self) -> RouterJudgeLLM:
        return self

    def get_model_name(self) -> str:
        return self.name

    async def a_generate(self, prompt: str, **_: Any) -> str:
        result = await self._run(prompt, json_mode=False)
        return result.response.content

    def generate(self, prompt: str, **_: Any) -> str:
        import asyncio

        return asyncio.run(self.a_generate(prompt))

    async def a_generate_with_schema(self, prompt: str, schema: Any = None, **_: Any) -> str:
        """Return JSON text; DeepEval parses it against the schema."""
        result = await self._run(prompt, json_mode=True)
        return result.response.content

    def generate_with_schema(self, prompt: str, schema: Any = None, **_: Any) -> str:
        import asyncio

        return asyncio.run(self.a_generate_with_schema(prompt, schema=schema))

    async def _run(self, prompt: str, *, json_mode: bool) -> Any:
        messages = [
            ChatMessage(
                role="system",
                content=(
                    "You are the Pramya evaluation judge. Score strictly and "
                    "consistently. Return only the requested JSON or answer."
                ),
            ),
            ChatMessage(role="user", content=prompt),
        ]
        return await self._router.generate(
            TaskClass.COMPLEX_REASONING,
            messages,
            json_mode=json_mode,
            temperature=0,
        )


class StubJudge(DeepEvalBaseLLM):
    """Deterministic judge for offline golden evals (no router/network).

    Returns a fixed verdict string; used only by deterministic metric
    scaffolding tests, never in real semantic evals.
    """

    def __init__(self, text: str = '{"score": 1.0}') -> None:
        super().__init__(model="stub-judge")
        self.name = "stub-judge"
        self._text = text

    def load_model(self) -> StubJudge:
        return self

    def get_model_name(self) -> str:
        return self.name

    async def a_generate(self, prompt: str, **_: Any) -> str:
        return self._text

    def generate(self, prompt: str, **_: Any) -> str:
        return self._text

    async def a_generate_with_schema(self, prompt: str, schema: Any = None, **_: Any) -> str:
        return self._text
