"""AI layer: InferenceRouter + httpx-based providers (Phase 2.0).

Application code depends on the router and the provider contracts only —
never on oMLX or DeepSeek specifics (ADR-004, ADR-011, ADR-013).
"""

from app.ai.contracts import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    EmbeddingProvider,
    EmbedRequest,
    EmbedResponse,
    InferenceProvider,
    RerankingProvider,
    RerankItem,
    RerankRequest,
    RerankResponse,
    TextGenerationProvider,
    Usage,
)
from app.ai.errors import (
    AIError,
    ProviderAuthError,
    ProviderConfigurationError,
    ProviderConnectionError,
    ProviderRequestError,
    StructuredOutputError,
)
from app.ai.factory import build_inference_router
from app.ai.policy import (
    MODEL_REGISTRY,
    TASK_POLICIES,
    ModelId,
    ModelSpec,
    ProviderKind,
    TaskClass,
    TaskPolicy,
    TaskPolicyTable,
)
from app.ai.providers import DeepSeekProvider, MLXProvider
from app.ai.router import InferenceRouter, RouterDecision, RouterResult
from app.ai.structured import generate_structured

__all__ = [
    "AIError",
    "ChatMessage",
    "ChatRequest",
    "ChatResponse",
    "DeepSeekProvider",
    "EmbedRequest",
    "EmbedResponse",
    "EmbeddingProvider",
    "InferenceProvider",
    "InferenceRouter",
    "MLXProvider",
    "MODEL_REGISTRY",
    "ModelId",
    "ModelSpec",
    "ProviderAuthError",
    "ProviderConfigurationError",
    "ProviderConnectionError",
    "ProviderKind",
    "ProviderRequestError",
    "RerankItem",
    "RerankRequest",
    "RerankResponse",
    "RerankingProvider",
    "RouterDecision",
    "RouterResult",
    "StructuredOutputError",
    "TASK_POLICIES",
    "TaskClass",
    "TaskPolicy",
    "TaskPolicyTable",
    "TextGenerationProvider",
    "Usage",
    "build_inference_router",
    "generate_structured",
]
