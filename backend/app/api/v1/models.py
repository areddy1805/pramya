"""Model / runtime status endpoint (Phase 4.5).

Exposes the routing table, canonical model registry, and provider health so
the UI can show model/runtime status. Health probes are advisory — routing
decisions remain in the InferenceRouter policy.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.policy import MODEL_REGISTRY, TASK_POLICIES
from app.ai.providers.omlx import MLXProvider
from app.core.config import get_settings
from app.core.db import get_session

SessionDep = Annotated[AsyncSession, Depends(get_session)]

router = APIRouter()


class ProviderStatusOut(BaseModel):
    name: str
    configured: bool
    healthy: bool | None = None
    base_url: str | None = None
    models: list[str] = []
    role: str | None = None  # "text LLM" | "audio + retrieval" (ADR-023)


class ModelStatusOut(BaseModel):
    id: str
    provider: str
    capability: str
    thinking: bool


class TaskPolicyOut(BaseModel):
    task: str
    model: str
    fallbacks: list[str]


class ModelsStatusResponse(BaseModel):
    providers: list[ProviderStatusOut]
    models: list[ModelStatusOut]
    policies: list[TaskPolicyOut]
    local_ai_enabled: bool


@router.get("/models/status", response_model=ModelsStatusResponse)
async def models_status() -> ModelsStatusResponse:
    settings = get_settings()

    providers: list[ProviderStatusOut] = []
    omlx_healthy: bool | None = None
    if settings.local_ai_enabled:
        omlx = MLXProvider(
            base_url=settings.omlx_base_url,
            api_key=settings.omlx_api_key,
            chat_model=settings.omlx_chat_model,
            embedding_model=settings.omlx_embedding_model,
            rerank_model=settings.omlx_rerank_model,
            thinking_enabled=settings.omlx_pramya_thinking_enabled,
        )
        omlx_healthy = await _health(omlx)
        providers.append(
            ProviderStatusOut(
                name="omlx",
                role="audio + retrieval",
                configured=True,
                healthy=omlx_healthy,
                base_url=settings.omlx_base_url,
                models=[
                    settings.voice_live_asr_model,
                    settings.voice_offline_asr_model,
                    settings.voice_tts_model,
                    settings.omlx_embedding_model,
                    settings.omlx_rerank_model,
                ],
            )
        )
    providers.append(
        ProviderStatusOut(
            name="deepseek",
            role="text LLM",
            configured=bool(settings.deepseek_api_key),
            healthy=bool(settings.deepseek_api_key),
            base_url=settings.deepseek_base_url if settings.deepseek_api_key else None,
            models=[settings.deepseek_model] if settings.deepseek_api_key else [],
        )
    )

    return ModelsStatusResponse(
        providers=providers,
        models=[
            ModelStatusOut(
                id=s.id, provider=s.provider.value, capability=s.capability, thinking=s.thinking
            )
            for s in MODEL_REGISTRY.values()
        ],
        policies=[
            TaskPolicyOut(
                task=p.task.value,
                model=p.model.value,
                fallbacks=[m.value for m in p.fallback_models],
            )
            for p in TASK_POLICIES.values()
        ],
        local_ai_enabled=settings.local_ai_enabled,
    )


async def _health(provider: MLXProvider) -> bool:
    try:
        await provider.health()
        return True
    except Exception:
        return False
