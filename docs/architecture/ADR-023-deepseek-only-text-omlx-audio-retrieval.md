# ADR-023 — Production Text Inference: DeepSeek Only; Local oMLX Retained for Audio + Retrieval

- **Status:** Accepted
- **Date:** 2026-08-12
- **Supersedes:** the local-text-LLM-first interpretation of ADR-004/ADR-011/ADR-013/ADR-020 (documented in prior catalog revisions). Provider abstraction, routing, and contracts remain unchanged.

## Context

The production architecture previously made a local 4B text model (`pramya-4b`,
Qwen3.5-4B alias) the default text provider with DeepSeek as escalation. On a
16 GB M4 with oMLX holding multiple local models, model load/unload churn
caused severe system memory pressure and user-visible lag during voice
sessions. Production economics and reliability favor a single remote text
provider: deterministic cost, predictable latency, zero local memory for text.

## Decision

- **TEXT → DeepSeek.** All textual/LLM inference routes through
  `deepseek-v4-flash` (base URL `https://api.deepseek.com`, key via
  `DEEPSEEK_API_KEY`). The task policy table (ADR-004) now maps every text
  task class to `ModelId.DEEPSEEK_V4_FLASH`.
- **No fallback chain for text.** A DeepSeek failure surfaces as a controlled
  `ProviderConnectionError` (caller retry path). There is NO silent fallback
  to a local text model — silent degradation would violate this decision.
- **AUDIO → local oMLX (retained).** The voice engine continues to call the
  local oMLX HTTP server directly for Parakeet-TDT-0.6B-v3 (live ASR),
  Qwen3-ASR-1.7B (primary/recorded ASR), and Qwen3-TTS-12Hz-0.6B (TTS).
- **RETRIEVAL → local oMLX (retained).** BGE-M3 embeddings and
  Qwen3-Reranker-0.6B reranking stay local because DeepSeek has no embedding
  or reranking endpoint. These are capabilities, not text LLMs.
- **Local text-generation models are prohibited in the production path.**
  `pramya-4b`, `qwen3.5-4b`, `qwen2.5-coder-7b` must not be selected by
  application code and must not appear in any fallback chain.
  `OMLX_CHAT_MODEL` remains a config field only for provider-construction
  compatibility; routing never uses it.
- **Thinking default off.** DeepSeek thinking is disabled by default
  (cheap + fast). Reasoning is deliberately requested per operation where
  the workload requires it (e.g. deep evaluation / complex reasoning).
- **Config topology is explicit:** `LLM_PROVIDER=deepseek`,
  `VOICE_PROVIDER=omlx`; `OMLX_ASR_MODEL` (primary, Qwen3-ASR-1.7B-4bit) and
  `OMLX_ASR_OPTIONAL_MODEL` (parakeet-tdt-0.6b-v3).

## Consequences

- Positive: no local text model memory footprint; no text-model load/unload
  churn; simpler cost accounting (single provider); provider abstraction and
  observability intact.
- Negative: every text operation depends on the DeepSeek API (network,
  rate limits, cost). Mitigated by the existing router retry/error path and
  structured-output validation; no cache layer exists yet (see Risks).
- The provider abstraction (InferenceRouter → provider contracts →
  DeepSeekProvider/MLXProvider) is unchanged; a future text provider can
  implement the same interface.

## Verification

- Unit: task policy table (all text tasks → deepseek, no fallback),
  router no-fallback behavior, structured output, providers (mocked httpx).
- Contract: `/models/status` surface (providers now carry `role`; oMLX lists
  audio + retrieval models; DeepSeek lists the text model).
- Integration: extraction/role-analysis/interview suites with fake router.
- Smoke: one minimal real DeepSeek call via the router returned
  `provider=deepseek model=deepseek-v4-flash thinking=False degraded=False`
  with real usage tokens.

## Risks

- No L1/L2 inference cache exists yet in the codebase; cache keys must
  include provider/model when one is added so old local-model entries can
  never masquerade as DeepSeek results.
- Langfuse tracing is config-only (no SDK wiring yet); when added, LLM
  traces must identify `provider=deepseek model=deepseek-v4-flash`.
