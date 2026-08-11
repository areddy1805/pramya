"""Domain error types.

Errors are typed so services can map them to HTTP responses with actionable
messages instead of leaking raw exceptions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class PramyaError(Exception):
    """Base domain error."""

    code: str = "pramya_error"
    status_code: int = 500

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details: dict[str, Any] = details or {}


@dataclass
class ErrorEnvelope:
    """Standard error response body."""

    code: str
    message: str
    request_id: str = ""
    details: dict[str, Any] = field(default_factory=dict[str, Any])


class NotFoundError(PramyaError):
    code = "not_found"
    status_code = 404


class ValidationFailedError(PramyaError):
    code = "validation_failed"
    status_code = 422


class DuplicateSubmissionError(PramyaError):
    """Idempotency violation: same idempotency key already processed."""

    code = "duplicate_submission"
    status_code = 409


class InterviewStateError(PramyaError):
    """Illegal state transition for an interview session."""

    code = "interview_state"
    status_code = 409


class ProviderUnavailableError(PramyaError):
    """AI provider unreachable; caller should attempt fallback."""

    code = "provider_unavailable"
    status_code = 503
