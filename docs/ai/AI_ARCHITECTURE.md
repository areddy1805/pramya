# Pramya — AI Architecture

> Companion to master plan §10–§14 and ADR-001/002/003/011.
> Describes how AI components compose: InferenceRouter → providers → models, LangGraph orchestration, prompt management, structured output, injection defenses.

---

## 1. Layering (never model-coupled)

```
InterviewService / KnowledgeService / VoiceEngine / services
        │
        ▼
InferenceRouter        task → policy → provider → model  (observable decision)
        │
        ├── DeepSeekProvider   (OpenAI-compatible, cloud)
        ├── MLXProvider        (oMLX HTTP: chat/embed/rerank/STT/TTS)
        └── FutureProvider     (pluggable)
```

Application asks for capabilities: `generate()`, `embed()`, `rerank()`, `transcribe()`, `synthesize()`. Business logic never knows which runtime answered.

## 2. InferenceRouter

- `RouterRequest(task, prompt_input, schema, mode_flags, latency_budget)` → `RouterDecision(provider, model, reason, thinking)` → execution.
- **Canonical model roles (finalized 2026-08, ADR-023):** deepseek-v4-flash =
  the ONLY production text LLM (all textual/LLM inference; thinking off by
  default, reasoning deliberately requested where justified); BGE-M3 =
  embeddings (local); Qwen3-Reranker-0.6B = reranking (local); audio =
  local oMLX (Parakeet-TDT live ASR, Qwen3-ASR primary/recorded ASR,
  Qwen3-TTS). Local text-generation models (pramya-4b / qwen3.5-4b /
  qwen2.5-coder-7b) are PROHIBITED in the production path; Qwen3.5-9B =
  DEFERRED (not required, not a fallback, not a routing target).
- Task classes (initial policy; ADR-004/ADR-023):

| Task | Model | Thinking |
|---|---|---|
| ALL text tasks (routine generation / extraction / classification / metadata / structured generation / semantic tasks / interview content generation / evaluation / analysis / deep evaluation / complex + adaptive reasoning / system design / final synthesis / difficult follow-ups) | deepseek-v4-flash | off by default; on where deliberately requested (deep eval, adaptive reasoning, system design) |
| embeddings | BGE-M3 (local oMLX) | — |
| rerank | Qwen3-Reranker-0.6B (local oMLX) | — |
| live ASR | Parakeet-TDT-0.6B-v3 (local oMLX) | — |
| recorded/primary ASR | Qwen3-ASR-1.7B (local oMLX) | — |
| TTS | Qwen3-TTS-0.6B (local oMLX) | — |

Routing decision flow: task-class policy — every text task → deepseek-v4-flash
(no fallback chain). TEXT → DeepSeek; AUDIO → local oMLX; RETRIEVAL → local
oMLX. A DeepSeek failure surfaces as a controlled provider error/retry path —
never a silent local text fallback.

- Fallback chains: text → none (controlled provider error); TTS → text;
  ASR → manual transcript; retrieval → degraded mode. (No local text model
  and no 9B is part of any V1 fallback chain.)
- Every decision logged: task, provider, model, reason, latency, tokens, error, fallback, cache hit/miss, cost (cloud).
- Health: provider health checks, capability detection, `/api/v1/models/status`.

## 3. DeepSeekProvider

- httpx (no OpenAI SDK); `base_url="https://api.deepseek.com"`; model
  `deepseek-v4-flash`; legacy IDs (deepseek-chat/reasoner) discontinued
  2026-07-24 — forbidden. Sole production text provider (ADR-023).
- Thinking: emitted as `thinking: {type: enabled|disabled}` in the JSON body
  per task policy; off by default, on where deliberately requested; in
  thinking mode temperature/top_p are inert.
- JSON output via `response_format={"type": "json_object"}` or JSON-schema; tool calls via tools param; streaming supported.
- Usage fields (`prompt_cache_hit_tokens` / `prompt_cache_miss_tokens`) surfaced into cost telemetry; context disk caching automatic.

## 4. MLXProvider (oMLX)

- HTTP OpenAI-compatible: `/v1/chat/completions`, `/v1/embeddings`, `/v1/rerank`, audio endpoints.
- Config: OMLX_BASE_URL, model names per catalog, per-model TTL/pinning for memory (oMLX supports LRU/pinning/TTL).
- Embeddings: BGE-M3 1024-dim (batch where possible).
- Rerank: Qwen3-Reranker-0.6B.
- Voice endpoints verified at Phase 7; fallback to parakeet-mlx / mlx-audio direct paths behind the same provider interface.

## 5. LangGraph Interview Orchestration (see ADR-002)

Typed StateGraph; nodes per §13 of master plan; Postgres checkpointer (thread_id = session id); `interrupt()` at LISTENING; `Command(resume=...)`; per-node timeouts; node error handlers; streaming events → SSE.

State schema (Pydantic, typed): session_id, status, profile, role_model, competency_focus, turn_history, current_question, answer, hints_used, evaluation, evidence_refs, remaining_time, error.

## 6. Prompt Management

```
prompts/
  role_analysis/         # JD → role + competency graph
  candidate_analysis/    # resume → evidence profile
  question_generation/
  answer_evaluation/
  evidence_extraction/
  follow_up/
  report_generation/
  transcript_analysis/
  debrief_analysis/
  story_analysis/
  system_design/
```

- Every prompt versioned; `evaluation_version` table stores version + prompt hash + model policy.
- Prompts live in repo (not scattered in code); loading via prompt service; no magic strings.

## 7. Structured Output

- Pydantic schemas are the contract for every LLM output that touches state.
- Flow: schema → prompt (+ JSON-schema response_format where supported) → validate → on failure, retry with error feedback (bounded) → still failing: return actionable error, never corrupt state.
- Validate business rules too (e.g., evidence status enum, score ranges, no invented experience).

## 8. Prompt-Injection Defenses

- Five regions always delimited: SYSTEM INSTRUCTIONS / USER DATA / DOCUMENT DATA / RETRIEVED EVIDENCE / MODEL OUTPUT.
- Document content is data; extraction prompt says so; claims validated as data.
- LLM output never directly mutates state: proposal → validation → application logic → persistence (ADR-010).
- Adversarial fixtures in test suite (Phase 11).

## 9. Cost Control

- Local-first routing; retrieval instead of full-context; prompt minimization; response caching where safe (never cached where it could corrupt interview state); request dedup; token/cost telemetry; DeepSeek only where policy says.

## 10. Observability (see ADR-008)

- Langfuse OSS `@observe` (self-hosted, MIT) on router + graph nodes; structured logs with the event set; PII-safe (IDs + redacted metadata).
