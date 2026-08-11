# Pramya — Observability

> Langfuse OSS (self-hosted, MIT-licensed) 4.x tracing. ADR-008
> (docs/architecture/ADR-008-observability.md). Redaction is mandatory.
> Langfuse Cloud and Enterprise-only features are not V1 dependencies.

## What We Trace

```
Interview
 └── LangGraph run
      ├── question generation   (model, tokens, thinking, prompt version)
      ├── retrieval             (counts, rerank, latency, cache)
      ├── evaluation            (dimensions, evaluator version)
      ├── evidence extraction   (provenance classes, strength)
      └── tool calls            (MCP? no — internal tools)
Voice: ASR latency, TTS latency, time_to_first_audio, interruption_count
```

## Telemetry Fields

request_id · session_id · turn_id · graph_node · model · provider · task ·
thinking flag · latency · tokens (in/out) · estimated cost · cache_hit ·
retrieval_count · reranker_count · prompt_version · evaluator_version ·
fallback · error · interruption_count · time_to_first_audio · ASR/TTS
latency.

## Redaction Policy

- **Never** put raw resume contents, answers, or transcript text in traces.
- Use IDs + redacted metadata (e.g., "answer_id=…", "competency=…",
  "evidence_count=…").
- Debug content capture behind explicit env flag, **off by default**.
- Tests assert trace payloads contain no candidate content.

## Wiring (Langfuse OSS SDK 4.x, self-hosted)

- `get_client()` singleton; env `LANGFUSE_BASE_URL` (+ keys).
- LangGraph: `langfuse.langchain.CallbackHandler` in graph config; one trace
  per interview; propagate session_id/thread_id.
- LlamaIndex: `openinference-instrumentation-llama-index` (native callback
  deprecated in v4).
- FastAPI: wrap request handlers with spans via `@observe()` or
  `start_as_current_observation`; join WS/SSE handlers to the same trace.

## Prompt Management

Prompts registered with versions; evaluation records store prompt_version +
evaluator_version. Langfuse prompt management (MIT, OSS) optional; versioned
prompts remain the source of truth in `prompts/` regardless.

## Health / Degradation

- OMLX health, DeepSeek reachability, model status surfaced via
  `/api/v1/model-status`.
- Every degraded-mode decision (fallback used) logged with reason.

## Cost Tracking

Per-call token + estimated cost for DeepSeek; routing reason logged; cache
hit/miss; per-interview cost rollup. Used to validate routing policy.
