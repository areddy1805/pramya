"""Provider adapters (httpx-based; no OpenAI SDK)."""

from app.ai.providers.deepseek import DeepSeekProvider
from app.ai.providers.omlx import MLXProvider

__all__ = ["DeepSeekProvider", "MLXProvider"]
