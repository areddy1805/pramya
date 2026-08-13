# Pramya — Model Catalog

> Definitive V1 model inventory. Verified against official sources 2026-08.
> Every model used by Pramya must be recorded here with license, runtime,
> memory, fallback, and rationale. Do not silently change the model stack
> (spec §7/§15; ADR-014/ADR-023). A model may be reconsidered only on
> verified concrete technical incompatibility, documented in an ADR.
> Alternative models are documented at the bottom as research/upgrade
> candidates only.

---

## 0. Model Hierarchy (finalized 2026-08, ADR-023 — production architecture)

Canonical roles — the basis for all routing policy (ADR-004, ADR-023,
master plan §10, `docs/ai/AI_ARCHITECTURE.md`):

1. **deepseek-v4-flash — the ONLY production text LLM.**
   All textual/LLM inference routes through DeepSeek: routine generation,
   extraction, classification, structured generation, semantic tasks,
   interview content generation, evaluation, analysis, complex reasoning,
   final synthesis. Thinking OFF by default (cheap + fast); reasoning is
   deliberately requested per operation when required.
2. **Local oMLX — AUDIO + RETRIEVAL only.**
   - Voice: Parakeet-TDT-0.6B-v3 (live ASR), Qwen3-ASR-1.7B (recorded /
     fallback ASR), Qwen3-TTS-12Hz-0.6B (interviewer TTS). The voice engine
     talks to the local oMLX HTTP server directly (`/v1/audio/*`).
   - Retrieval: BGE-M3 embeddings + Qwen3-Reranker-0.6B reranking (DeepSeek
     has no equivalent — these stay local).
3. **Local text-generation models — PROHIBITED in the production path.**
   `pramya-4b` (Qwen3.5-4B alias), `qwen3.5-4b`, `qwen2.5-coder-7b`, and any
   other local text-generation model must not be selected by application
   code, and must not appear in any fallback chain. A DeepSeek failure
   produces a controlled provider error/retry path — never a silent local
   text fallback.
4. **Qwen3.5-9B — DEFERRED from the V1 production stack.**
   Not a required runtime, not a fallback, not a routing target, not a
   required download/setup dependency. Recorded below as a deferred/
   experimental local candidate only (historical context preserved).

Routing decision flow (deterministic, task-class based — see ADR-004/ADR-023):

```
application task
    ↓
task-class policy (all text tasks → deepseek-v4-flash; no fallback chain)
    ├── text → deepseek-v4-flash (thinking off unless deliberately requested)
    ├── embedding → BGE-M3 (local oMLX)
    ├── reranking → Qwen3-Reranker-0.6B (local oMLX)
    └── audio → VoiceEngine → local oMLX /v1/audio/* (Parakeet / Qwen3-ASR / Qwen3-TTS)
```

Architecture principle: **TEXT → DeepSeek. AUDIO → local oMLX. Retrieval →
local oMLX.** Provider abstraction (InferenceRouter + provider contracts)
remains intact and provider-agnostic; DeepSeek is simply the current
production text provider.

---

## 1. Model Inventory Summary

| # | Model | Purpose | Runtime | License | Local/Cloud |
|---|---|---|---|---|---|
| 1 | deepseek-v4-flash | ALL text/LLM inference (sole production text provider) | DeepSeek API | DeepSeek terms (proprietary cloud API) | Cloud |
| 2 | BGE-M3 | Embeddings (dense retrieval, multilingual) | MLX via oMLX | MIT | Local |
| 3 | Qwen3-Reranker-0.6B | Reranking candidate evidence | MLX via oMLX | Apache-2.0 | Local |
| 4 | Parakeet-TDT-0.6B-v3 | Live ASR (chunked/pseudo-streaming) | Host-native MLX (parakeet-mlx) | CC-BY-4.0 | Local |
| 5 | Qwen3-ASR-1.7B | Recorded/multilingual ASR + offline/chunked fallback | Host-native MLX (mlx-audio) | Apache-2.0 | Local |
| 6 | Qwen3-TTS-0.6B | Interviewer TTS (streaming) | Host-native MLX (mlx-audio) | Apache-2.0 | Local |
| — | Qwen3.5-4B (`pramya-4b`) | **PROHIBITED** in production text path (ADR-023); retained only as provider-construction compat | MLX via oMLX | Apache-2.0 | Local (disabled) |
| — | Qwen3.5-9B | DEFERRED from V1 production stack (experimental local candidate; not required) | MLX via oMLX | Apache-2.0 | Local (optional) |

---

## 2. Detailed Entries

### 2.1 deepseek-v4-flash (production text LLM — the ONLY text provider)

- **Model:** DeepSeek V4 Flash
- **Version:** model ID `deepseek-v4-flash` (V4-Flash-0731 checkpoint public beta as of Aug 2026; legacy `deepseek-chat`/`deepseek-reasoner` IDs deprecated 2026-07-24 — do NOT use)
- **Role in stack:** sole production text-generation provider (ADR-023). Every textual/LLM inference in the application routes here via the task policy table. No local text fallback: a DeepSeek failure surfaces as a controlled provider error/retry path.
- **Purpose:** all text tasks — routine generation, extraction, classification, metadata, structured generation, semantic tasks, interview content generation, ordinary + deep evaluation, analysis, complex/adaptive reasoning, system design, final synthesis, difficult follow-ups.
- **Runtime:** DeepSeek cloud API, OpenAI-compatible. Base URL `https://api.deepseek.com`.
- **Architecture:** MoE 284B total / 13B active (per official docs).
- **Context window:** 1M tokens; max output up to 384K tokens.
- **Modes:** thinking (enabled) and non-thinking (disabled). Production default is **non-thinking** (cheap + fast); reasoning is deliberately requested per operation where the workload requires it. Mode is task-policy-driven and observable in telemetry (ADR-004/ADR-013/ADR-023).
- **Streaming:** supported (SSE).
- **Structured output:** JSON output + function calling + Responses API support (current). Tool calls in thinking mode: preserve `reasoning_content`; no `tool_choice`.
- **Pricing (Aug 2026):** ~$0.14/1M input (cache miss), ~$0.0028/1M (cache hit), ~$0.28/1M output; concurrency limit 2500. Verify at api-docs.deepseek.com.
- **License:** proprietary cloud API terms; no redistribution; minimize PII sent.
- **Source:** https://api-docs.deepseek.com/ , https://api-docs.deepseek.com/quick_start/pricing/
- **Fallback:** none. Controlled `ProviderConnectionError` + caller retry (ADR-023 — never a local text model).
- **Why selected:** production architecture decision (2026-08, ADR-023): remove local text LLMs from the production path; single remote text provider simplifies cost/quality predictability while preserving the provider abstraction.
- **Alternatives rejected:** legacy IDs (deprecated); deepseek-v4-pro (costlier; not needed in V1); local text models (prohibited in production).

### 2.2 Qwen3.5-4B (alias `pramya-4b`) — PROHIBITED in production text path (ADR-023)

> Historical note: previously the primary local workhorse. Finalized 2026-08
> (ADR-023): local text-generation models are removed from the production
> inference path. This entry is preserved for historical accuracy and to
> document the prohibition.

- **Status:** PROHIBITED in production text routing. `OMLX_CHAT_MODEL` is retained only for provider-construction compatibility and is unused by routing (the task policy table contains no local text model).
- **Runtime:** MLX via oMLX (`/v1/chat/completions`) — endpoint remains available for operational debugging only; never selected by application code.
- **License:** Apache-2.0.
- **Why removed:** deliberate production architecture decision (ADR-023): TEXT → DeepSeek; local text models add memory churn (16 GB M4) without a production need.

### 2.3 Qwen3.5-9B — DEFERRED (experimental local candidate, NOT V1 production)

> Historical note: initially considered for higher-quality local reasoning.
> Finalized 2026-08: DEFERRED from the V1 production model stack — doubly so
> under ADR-023 (local text models are prohibited in the production path).
> Not a required runtime, not a fallback, not a routing target, not a
> required download/setup dependency. This entry is preserved for historical
> accuracy and as a documented experimental candidate.

- **Model:** Qwen/Qwen3.5-9B (MLX: `mlx-community/Qwen3.5-9B-OptiQ-4bit` ~5.6 GB)
- **Status:** DEFERRED / experimental. Phase 1+ must not depend on it.
- **Runtime:** MLX via oMLX (only if explicitly enabled).
- **License:** Apache-2.0.
- **Fallback:** none in V1 — not part of any fallback chain.

### 2.4 BGE-M3

- **Model:** BAAI/bge-m3 (XLM-RoBERTa 0.6B; 1024-dim; max seq 8192; dense+sparse+multi-vector; 100+ languages)
- **Purpose:** candidate evidence retrieval, resume/JD retrieval, interview-context retrieval, competency retrieval, semantic search, evidence matching, historical-session retrieval.
- **Runtime:** MLX via oMLX `/v1/embeddings` (mlx-community conversions: fp16 ~1.1 GB, 8-bit ~592 MB, 6-bit ~457 MB, 4-bit ~321 MB).
- **License:** MIT (model + MLX conversions).
- **Important licensing note:** third-party `mlx-embeddings` Python library is **GPL-3.0**. Pramya calls embeddings through oMLX's HTTP endpoint (Apache-2.0 server) rather than depending on the GPL library. See ADR-014.
- **Memory expectation:** ~321 MB (4-bit) resident.
- **Fallback:** oMLX down → skip semantic retrieval, use FTS only (degraded).
- **Why selected:** spec-mandated embedding model; DeepSeek has no embedding endpoint (retrieval stays local, ADR-023).

### 2.5 Qwen3-Reranker-0.6B

- **Model:** Qwen/Qwen3-Reranker-0.6B (MLX: `mlx-community/Qwen3-Reranker-0.6B-4bit` ~331 MB)
- **Purpose:** candidate evidence reranking, resume-evidence retrieval, JD-to-evidence matching, interview-context retrieval, high-value semantic ranking.
- **Runtime:** MLX via oMLX `/v1/rerank` (query, documents, top_n).
- **License:** Apache-2.0.
- **Memory expectation:** ~331 MB (4-bit).
- **Fallback:** skip reranking (top-K direct) if unavailable.
- **Why selected:** spec-mandated; DeepSeek has no rerank endpoint (retrieval stays local, ADR-023).

### 2.6 Parakeet-TDT-0.6B-v3 (live ASR)

- **Model:** nvidia/parakeet-tdt-0.6b-v3 (FastConformer + TDT transducer; 25 European languages; INT8 ~755 MB / INT4 ~489 MB MLX conversions; `parakeet-mlx` package)
- **Purpose:** live-interview ASR: real-time transcription, partial transcripts, live turn detection support, word timestamps, interview transcript generation. Optional ASR (secondary) per ADR-023 config (`OMLX_ASR_OPTIONAL_MODEL`).
- **Runtime:** host-native MLX (`parakeet-mlx`), 16 kHz mono.
- **License:** CC-BY-4.0 (attribution required; commercial OK).
- **Streaming constraint (verified):** upstream model is offline/non-chunked; MLX path supports chunked streaming with finalized/draft token phases. Pramya V1: chunked/pseudo-streaming with VAD-gated short windows + partial transcript agreement pattern (see ADR-012, VOICE_ARCHITECTURE).
- **Fallback live path:** Parakeet chunked streaming → Qwen3-ASR (recorded/offline) → manual text input.
- **Memory expectation:** ~0.5–0.8 GB (INT8/INT4).
- **Source:** https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3 , https://github.com/senstella/parakeet-mlx
- **Why selected:** spec-mandated live ASR; small, fast, good accuracy, Apple-Silicon-suitable.

### 2.7 Qwen3-ASR-1.7B (recorded / primary ASR)

- **Model:** Qwen/Qwen3-ASR-1.7B (30 languages + 22 Chinese dialects; offline AND streaming inference supported via official vLLM backend; MLX: `mlx-community/Qwen3-ASR-1.7B-8bit` ~2.35 GB, `-4bit` ~1.5 GB via mlx-audio)
- **Purpose:** primary ASR model per ADR-023 config (`OMLX_ASR_MODEL`): live + recorded transcription. Parakeet remains the optional ASR for the live path.
- **Runtime:** host-native MLX (`mlx-audio` STT).
- **License:** Apache-2.0.
- **Memory expectation:** ~0.9–2.4 GB (4-bit/8-bit).
- **Streaming:** MLX path is offline/chunked (single-pass per chunk) — NOT native streaming. Native streaming requires the official vLLM backend, which is not part of the MLX deployment.
- **Source:** https://huggingface.co/Qwen/Qwen3-ASR-1.7B , https://huggingface.co/mlx-community/Qwen3-ASR-1.7B-8bit
- **Why selected:** spec-mandated ASR; high quality, multilingual.

### 2.8 Qwen3-TTS-0.6B (TTS)

- **Model:** Qwen/Qwen3-TTS-12Hz-0.6B-Base (official name; + CustomVoice variant; 10 languages; discrete multi-codebook LM, 12 Hz tokenizer). MLX: `Qwen3-TTS-12Hz-0.6B-Base-MLX-4bit` ~981 MB; used via mlx-audio TTS through oMLX `/v1/audio/speech`.
- **Purpose:** default interviewer voice; streaming output, low perceived latency, controllable voice, cancellation, interruption handling, chunk streaming, browser playback.
- **Runtime:** host-native MLX (mlx-audio), served by oMLX.
- **License:** Apache-2.0.
- **Memory expectation:** ~1 GB (4-bit).
- **Cancellation:** cooperative between chunks — required for stale-TTS prevention (ADR-012, Phase 9).
- **Source:** https://huggingface.co/Qwen/Qwen3-TTS-12Hz-0.6B-Base
- **Fallback:** text interviewer response when TTS unavailable.
- **Why selected:** spec-mandated V1 TTS (Apache-2.0, MLX-supported).

---

## 3. Model / Runtime Compatibility Matrix (M4 16 GB)

| Model | Runs on M4 16GB | MLX | oMLX | Streaming | Batch | Cancel | Est. resident |
|---|---|---|---|---|---|---|---|
| deepseek-v4-flash | N/A (cloud) | — | — | yes | yes | client-side | 0 |
| Qwen3.5-4B 4-bit (`pramya-4b`) | yes | yes | yes | yes | yes | client-side | ~3 GB (prohibited in prod) |
| Qwen3.5-9B 4-bit | yes* | yes | yes | yes | yes | client-side | ~5.6 GB (deferred) |
| BGE-M3 4-bit | yes | yes | yes | yes | yes | n/a | ~0.3 GB |
| Qwen3-Reranker-0.6B 4-bit | yes | yes | yes | n/a | yes | n/a | ~0.3 GB |
| Parakeet-TDT v3 INT8/4 | yes | yes | no (host-native) | chunked/pseudo | yes | mid-window | ~0.5–0.8 GB |
| Qwen3-ASR-1.7B 8-bit | yes | yes | audio via mlx-audio | yes (native) | yes | yes | ~0.9–2.4 GB |
| Qwen3-TTS-0.6B 4-bit | yes | yes | audio via mlx-audio | yes | n/a | cooperative | ~1 GB |

*\*9B is DEFERRED from V1 production: it runs on the hardware but is not part of the
required stack, not a fallback, not a routing target, and not a required download.*

**16 GB budget rule (V1 default, ADR-023):** text inference is remote
(DeepSeek — 0 GB resident). Local resident set = voice (ASR + TTS,
~1.5–3 GB) + retrieval (BGE-M3 + reranker, ~0.6 GB). No local text LLM is
resident in production; model lifecycle (oMLX memory guard, lazy load,
unload) manages the audio/retrieval set under the memory cap. Speech runs on
a single serialized MLX worker (MLX Metal workloads should not run
concurrently from multiple threads).

All installed model artifacts may coexist on disk; oMLX dynamically
loads/manages models under its memory policy — residency is determined by
demand, cache state, TTL/pinning, and the configured memory guard, not by
what is installed.

---

## 4. License Audit Notes

- Apache-2.0: Qwen3-Reranker-0.6B, Qwen3-ASR-1.7B, Qwen3-TTS-0.6B, oMLX.
- MIT: BGE-M3 weights/conversions.
- CC-BY-4.0: Parakeet-TDT v3 (attribution required — record in NOTICE).
- Proprietary cloud terms: DeepSeek API.
- Avoid: `mlx-embeddings` (GPL-3.0) — use oMLX HTTP instead;
  jina-reranker-v3-mlx (CC-BY-NC) — rejected.
- Full inventory + attribution: `NOTICE.md` to be created at Phase 12.

---

## 5. Alternative / Research Models (documented, NOT V1)

| Model | Class | Note |
|---|---|---|
| NVIDIA Nemotron-3.5-ASR-Streaming-Multilingual-0.6b | ASR | true streaming upgrade candidate; permission-gated |
| Voxtral TTS | TTS | research candidate |
| Soprano | TTS | very small footprint, streaming claims |
| Kokoro | TTS | research candidate |
| IndexTTS | TTS | research candidate |
| Zonos | TTS | research candidate |
| VibeVoice | TTS | research candidate |
| Higgs Audio | TTS | research candidate |
| Magpie TTS | TTS | research candidate |
| DeepSeek V4 Pro | cloud | not needed in V1 (flash sufficient) |
| Qwen3.5-35B/122B (MoE) | local | exceeds 16 GB comfortable envelope in V1 |
| **Qwen3.5-4B (`pramya-4b`)** | **local LLM** | **PROHIBITED in production text path (ADR-023). Provider-construction compat only.** |
| **Qwen3.5-9B** | **local LLM** | **DEFERRED from V1 production (historical consideration; experimental candidate only — §2.3). Not required, not a fallback, not a routing target.** |

---

## 6. Local Runtime Verification Baseline (required at Phase 4)

Before any voice/retrieval work depends on local inference, the oMLX audio +
retrieval baseline must be verified (no local text LLM dependency):

- [ ] oMLX serves audio models (Parakeet / Qwen3-ASR / Qwen3-TTS) under `/v1/audio/*`
- [ ] BGE-M3 embeddings + Qwen3-Reranker work through the router (retrieval)
- [ ] DeepSeek text generation + structured JSON works through the router
- [ ] no local text-generation model appears in the task policy table
- [ ] a DeepSeek failure surfaces as a controlled provider error (no local text fallback)
- [ ] no 9B dependency exists anywhere in config/setup/tests

No performance or quality claims beyond verified facts may be recorded.
