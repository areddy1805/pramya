"""Provider/router wiring from Settings (dependency construction only).

No global singletons: the router is built explicitly from Settings so tests
can inject mocked httpx clients. Application code should depend on the
router (or the provider contracts) — never on oMLX/DeepSeek specifics.
"""

from __future__ import annotations

import httpx

from app.ai.policy import TaskPolicyTable
from app.ai.providers.deepseek import DeepSeekProvider
from app.ai.providers.omlx import MLXProvider
from app.ai.router import InferenceRouter
from app.core.config import Settings, get_settings


def build_inference_router(
    settings: Settings | None = None,
    *,
    client: httpx.AsyncClient | None = None,
) -> InferenceRouter:
    """Construct the InferenceRouter with providers wired from Settings.

    - oMLX provider is built when LOCAL_AI_ENABLED (default true).
    - DeepSeek provider is built only when DEEPSEEK_API_KEY is set; the
      escalation path reports not-configured otherwise.
    - ``client`` allows tests to inject a mocked httpx transport.
    """
    settings = settings or get_settings()
    policy = TaskPolicyTable()

    omlx: MLXProvider | None = None
    if settings.local_ai_enabled:
        omlx = MLXProvider(
            base_url=settings.omlx_base_url,
            api_key=settings.omlx_api_key,
            chat_model=settings.omlx_chat_model,
            embedding_model=settings.omlx_embedding_model,
            rerank_model=settings.omlx_rerank_model,
            thinking_enabled=settings.omlx_pramya_thinking_enabled,
            timeout_seconds=settings.omlx_timeout_seconds,
            client=client,
        )

    deepseek: DeepSeekProvider | None = None
    if settings.deepseek_api_key:
        deepseek = DeepSeekProvider(
            base_url=settings.deepseek_base_url,
            api_key=settings.deepseek_api_key,
            model=settings.deepseek_model,
            timeout_seconds=settings.deepseek_timeout_seconds,
            client=client,
        )

    return InferenceRouter(policy=policy, omlx=omlx, deepseek=deepseek)
