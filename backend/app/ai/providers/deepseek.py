"""DeepSeekProvider — deepseek-v4-flash via OpenAI-compatible HTTP (ADR-013).

Escalation model only (never default). Thinking mode is task-policy driven:
the router passes the thinking flag per request; it is emitted directly in
the JSON body (``thinking: {type: enabled|disabled}``). Legacy model IDs
(deepseek-chat / deepseek-reasoner) are forbidden.

Implemented over httpx (no OpenAI SDK): the DeepSeek API is plain
OpenAI-compatible JSON over HTTP.
"""

from __future__ import annotations

from typing import Any

import httpx

from app.ai.contracts import ChatRequest, ChatResponse
from app.ai.providers._http import build_headers, parse_chat_response, request_json


class DeepSeekProvider:
    """Text-generation provider backed by the DeepSeek cloud API."""

    name = "deepseek"

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        timeout_seconds: float = 60.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self._client = client or httpx.AsyncClient(timeout=timeout_seconds)

    async def generate(self, request: ChatRequest) -> ChatResponse:
        body: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content} for m in request.messages],
        }
        if request.temperature is not None:
            body["temperature"] = request.temperature
        if request.max_tokens is not None:
            body["max_tokens"] = request.max_tokens
        if request.json_mode:
            body["response_format"] = {"type": "json_object"}
        if request.thinking is not None:
            body["thinking"] = {"type": "enabled" if request.thinking else "disabled"}

        payload = await request_json(
            self._client,
            "POST",
            f"{self.base_url}/chat/completions",
            headers=build_headers(self.api_key, bearer=True),
            body=body,
        )
        return parse_chat_response(payload, fallback_model=self.model, provider=self.name)
