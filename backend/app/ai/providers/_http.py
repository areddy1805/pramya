"""Shared HTTP plumbing + response parsing for httpx-based providers.

No OpenAI SDK: providers call the verified OpenAI-compatible HTTP endpoints
directly through httpx. All httpx/HTTP failures are normalized into
app.ai.errors so provider internals never leak into application code.
"""

from __future__ import annotations

import json
from typing import Any, cast

import httpx

from app.ai.contracts import ChatResponse, Usage
from app.ai.errors import ProviderAuthError, ProviderConnectionError, ProviderRequestError

_DEFAULT_HEADERS = {"Accept": "application/json"}


def build_headers(api_key: str | None, *, bearer: bool = False) -> dict[str, str]:
    headers = dict(_DEFAULT_HEADERS)
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}" if bearer else api_key
    return headers


def _raise_for_provider_status(response: httpx.Response) -> None:
    status = response.status_code
    if status in (401, 403):
        raise ProviderAuthError(
            f"provider rejected credentials (HTTP {status})", details={"status": status}
        )
    if status in (408, 409, 429) or status >= 500:
        # Fallback-eligible: transient or server-side failure.
        raise ProviderConnectionError(
            f"provider unavailable (HTTP {status})", details={"status": status}
        )
    if status >= 400:
        raise ProviderRequestError(
            f"provider rejected request (HTTP {status})", details={"status": status}
        )


async def request_json(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Perform one JSON request; raise normalized app.ai.errors on failure."""
    try:
        response = await client.request(method, url, headers=headers, json=body)
    except httpx.TimeoutException as exc:
        raise ProviderConnectionError(f"provider request timed out: {url}") from exc
    except httpx.HTTPError as exc:
        raise ProviderConnectionError(f"provider request failed: {url}: {exc}") from exc
    _raise_for_provider_status(response)
    try:
        result = response.json()
    except json.JSONDecodeError as exc:
        raise ProviderRequestError(f"provider returned non-JSON response: {url}") from exc
    if not isinstance(result, dict):
        raise ProviderRequestError(f"provider returned non-object JSON: {url}")
    return cast(dict[str, Any], result)


# --------------------------------------------------------------------------
# Response normalization into provider contracts
# --------------------------------------------------------------------------


def _get(container: dict[str, Any] | None, key: str) -> Any:
    return container.get(key) if container is not None else None


def _int_or(value: Any) -> int:
    return value if isinstance(value, int) else 0


def parse_chat_response(
    payload: dict[str, Any], *, fallback_model: str, provider: str
) -> ChatResponse:
    """Normalize an OpenAI-compatible chat completion into ChatResponse."""
    choices_raw = payload.get("choices")
    if not isinstance(choices_raw, list) or not choices_raw:
        raise ProviderRequestError(
            "malformed chat response: empty choices", details={"provider": provider}
        )
    choice = cast(dict[str, Any], choices_raw[0])
    message_raw = choice.get("message")
    if not isinstance(message_raw, dict):
        raise ProviderRequestError(
            "malformed chat response: missing message", details={"provider": provider}
        )
    message = cast(dict[str, Any], message_raw)

    usage_raw = _get(payload, "usage")
    usage = Usage(
        prompt_tokens=_int_or(_get(usage_raw, "prompt_tokens")),
        completion_tokens=_int_or(_get(usage_raw, "completion_tokens")),
        total_tokens=_int_or(_get(usage_raw, "total_tokens")),
        prompt_cache_hit_tokens=_int_or(_get(usage_raw, "prompt_cache_hit_tokens")),
        prompt_cache_miss_tokens=_int_or(_get(usage_raw, "prompt_cache_miss_tokens")),
    )
    content = message.get("content")
    return ChatResponse(
        content=content if isinstance(content, str) else "",
        model=str(payload.get("model") or fallback_model),
        usage=usage,
        finish_reason=choice.get("finish_reason"),
        thinking_content=message.get("reasoning_content"),
    )
