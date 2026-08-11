"""AI-layer error types.

These are service-layer errors, distinct from HTTP-mapping domain errors
(``app.domain.errors``). The InferenceRouter maps connection-level failures
to fallback providers; application code maps ``StructuredOutputError`` /
``ProviderUnavailableError`` into actionable user-visible errors. Never let
provider internals (e.g. raw HTTP exceptions) leak past this layer.
"""

from __future__ import annotations

from typing import Any


class AIError(Exception):
    """Base error for the AI layer."""

    code: str = "ai_error"

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details: dict[str, Any] = details or {}


class ProviderConnectionError(AIError):
    """Provider unreachable / timed out / server-side failure.

    Router treats this as fallback-eligible.
    """

    code = "provider_unavailable"


class ProviderAuthError(AIError):
    """Provider rejected credentials (401/403). Not fallback-eligible by default."""

    code = "provider_auth"


class ProviderRequestError(AIError):
    """Provider rejected the request (4xx) or returned an unparseable response."""

    code = "provider_request"


class ProviderConfigurationError(AIError):
    """Provider not configured (e.g. DeepSeek provider requested but no API key)."""

    code = "provider_not_configured"


class StructuredOutputError(AIError):
    """Model output failed schema validation after bounded retries.

    Raised instead of corrupting state: callers surface the error without
    applying partial/invalid output.
    """

    code = "structured_output"
