# Pramya — Model Catalog

> Definitive V1 model inventory. Verified against official sources 2026-08.
> Every model used by Pramya must be recorded here with license, runtime,
> memory, fallback, and rationale. Do not silently change the model stack
> (spec §7/§15; ADR-014). A model may be reconsidered only on verified
> concrete technical incompatibility, documented in an ADR.
> Alternative models are documented at the bottom as research/upgrade
> candidates only.

---

## 0. Model Hierarchy (finalized 2026-08)

Canonical roles — the basis for all routing policy (ADR-004, master plan §10,
`docs/ai/AI_ARCHITECTURE.md`):

1. **Qwen3.5-4B (oMLX alias/profile `pramya-4b`) — primary local workhorse.**
   Default local model. Handles the majority of Pramya workload: routine
   generation, extraction, classification, structured generation, normal
   semantic tasks, interview content generation, ordinary evaluation/support
   workloads. Thinking OFF by default. Local-first.
2. **deepseek-v4-flash — escalation/cloud reasoning model.**
   Used only when the workload materially benefits from stronger reasoning,
   capability, or context. NOT the default. NOT a replacement for the local
   4B workhorse. The InferenceRouter decides when escalation is justified.
   Routine high-volume work is never routed to DeepSeek merely because it is
   stronger.
3. **Qwen3.5-9B — DEFERRED from the V1 production stack.**
   Not a required runtime, not a fallback, not a routing target, not a
   required download/setup dependency. Recorded below as a deferred/experimental
   local candidate only (historical context preserved).

Routing decision flow (deterministic, task-class based — see ADR-004):

```
4B local first
    ↓
application-level task-class decision
    ↓
can 4B handle this workload adequately?
    ├── yes → Qwen3.5-4B (pramya-4b)
    └── no  → deepseek-v4-flash (escalation)
```

Architecture principle: **the strongest model is not the default model.**
Local 4B handles the majority of workload; cloud escalation is reserved for
workloads where additional capability is justified.

---

## 1. Model Inventory Summary

| # | Model | Purpose | Runtime | License | Local/Cloud |
|---|---|---|---|---|---|
| 1 | deepseek-v4-flash | ESCALATION: complex reasoning, deep evaluation, synthesis (never default) | DeepSeek API | DeepSeek terms (proprietary cloud API) | Cloud |
| 2 | Qwen3.5-4B (`pramya-4b`) | PRIMARY local workhorse: routine generation, extraction, classification, structured generation, semantic tasks, ordinary eval | MLX via oMLX | Apache-2.0 | Local |
| 3 | Qwen3.5-9B | DEFERRED from V1 production stack (experimental local candidate; not required) | MLX via oMLX | Apache-2.0 | Local (optional) |
| 4 | BGE-M3 | Embeddings (dense retrieval, multilingual) | MLX via oMLX | MIT | Local |
| 5 | Qwen3-Reranker-0.6B | Reranking candidate evidence | MLX via oMLX | Apache-2.0 | Local |
| 6 | Parakeet-TDT-0.6B-v3 | Live ASR (chunked/pseudo-streaming) | Host-native MLX (parakeet-mlx) | CC-BY-4.0 | Local |
| 7 | Qwen3-ASR-1.7B | Recorded/multilingual ASR + offline/chunked fallback | Host-native MLX (mlx-audio) | Apache-2.0 | Local |
| 8 | Qwen3-TTS-0.6B | Interviewer TTS (streaming) | Host-native MLX (mlx-audio) | Apache-2.0 | Local |

---

## 2. Detailed Entries

### 2.1 deepseek-v4-flash (escalation model — NOT default)

- **Model:** DeepSeek V4 Flash
- **Version:** model ID `deepseek-v4-flash` (V4-Flash-0731 checkpoint public beta as of Aug 2026; legacy `deepseek-chat`/`deepseek-reasoner` IDs deprecated 2026-07-24 — do NOT use)
- **Role in stack:** escalation/cloud reasoning. Used only when the workload materially benefits from stronger reasoning/capability/context. NOT the default model; NOT a replacement for the local 4B workhorse. The InferenceRouter decides when escalation is justified (ADR-004, §0 above).
- **Purpose:** complex reasoning, adaptive question generation, deep answer evaluation, evidence interpretation, difficult follow-ups, system-design reasoning, final synthesis.
- **Runtime:** DeepSeek cloud API, OpenAI-compatible. Base URL `https://api.deepseek.com`. Anthropic-format endpoint also available.
- **Architecture:** MoE 284B total / 13B active (per official docs).
- **Context window:** 1M tokens; max output up to 384K tokens.
- **Modes:** thinking (default) and non-thinking. Toggle via `extra_body={"thinking": {"type": "enabled"|"disabled"}}` (OpenAI SDK) or `reasoning_effort` (high/max); thinking mode ignores temperature/top_p. Mode is task-policy-driven and observable in telemetry (ADR-004/ADR-013). Verify exact param surface at Phase 4 against current docs.
- **Quantization / memory:** N/A (cloud).
- **Latency expectation:** higher than local; non-thinking for latency-sensitive ops.
- **Streaming:** supported (SSE).
- **Structured output:** JSON output + function calling + Responses API support (current). Tool calls in thinking mode: preserve `reasoning_content`; no `tool_choice`.
- **Pricing (Aug 2026):** ~$0.14/1M input (cache miss), ~$0.0028/1M (cache hit), ~$0.28/1M output; concurrency limit 2500. Verify at api-docs.deepseek.com.
- **License:** proprietary cloud API terms; no redistribution; minimize PII sent.
- **Source:** https://api-docs.deepseek.com/ , https://api-docs.deepseek.com/quick_start/pricing/
- **Fallback (DeepSeek unavailable):** Qwen3.5-4B (local, degraded quality) for non-critical tasks; user-visible degraded state. The 9B is NOT a fallback.
- **Why selected:** spec-mandated escalation/cloud reasoning model (spec §6.1), reconciled to escalation-only role (finalized 2026-08).
- **Alternatives rejected:** legacy IDs (deprecated); deepseek-v4-pro (costlier; not needed in V1).

### 2.2 Qwen3.5-4B (alias `pramya-4b`) — PRIMARY LOCAL WORKHORSE

- **Model:** Qwen/Qwen3.5-4B (MLX: `mlx-community/Qwen3.5-4B-OptiQ-4bit` ~2.8–3.0 GB)
- **oMLX alias/profile:** `pramya-4b` (canonical alias configured in oMLX pointing at the 4B model; used by all routing/config code instead of raw HF names).
- **Role in stack:** primary local workhorse. Default local model; handles the majority of Pramya workload. Thinking is EXPLICITLY DISABLED on load/request for the default workhorse configuration (`enable_thinking: false` in the oMLX profile/settings, mirrored in the task policy) — never rely on the model's default thinking behavior. Local-first.
- **Purpose:** routine generation, extraction, classification, metadata analysis, structured generation, normal semantic tasks, interview content generation, ordinary evaluation/support workloads, background processing, simple transformations.
- **Runtime:** MLX via oMLX (`/v1/chat/completions`, streaming, JSON-schema structured output, tool calling).
- **License:** Apache-2.0.
- **Quantization:** 4-bit standard; OptiQ mixed-precision variants exist.
- **Memory expectation:** ~2.8–3.1 GB (4-bit).
- **Latency expectation:** ~26–168 tok/s on Apple Silicon (community benchmarks, M3/M4-class).
- **Streaming:** yes. **Batching:** oMLX continuous batching.
- **Compatibility note:** initial mlx-lm lag for `qwen3_5` architecture (ml-explore/mlx-lm issue #1136) — must use recent mlx-lm. Verify at Phase 4.
- **Source:** https://huggingface.co/Qwen/Qwen3.5-4B , https://huggingface.co/mlx-community/Qwen3.5-4B-OptiQ-4bit
- **Fallback (4B unavailable):** escalate to deepseek-v4-flash per task policy (not another local model); graceful degraded mode.
- **Why selected:** spec-mandated cheap local model; finalized 2026-08 as the primary local workhorse; fits 16 GB envelope.

### 2.3 Qwen3.5-9B — DEFERRED (experimental local candidate, NOT V1 production)

> Historical note: initially considered for higher-quality local reasoning,
> candidate analysis, local question generation/evaluation, and as a local
> fallback for cloud. Finalized 2026-08: DEFERRED from the V1 production
> model stack. Not a required runtime, not a fallback, not a routing target,
> not a required download/setup dependency. This entry is preserved for
> historical accuracy and as a documented experimental candidate.

- **Model:** Qwen/Qwen3.5-9B (MLX: `mlx-community/Qwen3.5-9B-OptiQ-4bit` ~5.6 GB)
- **Status:** DEFERRED / experimental. Phase 1+ must not depend on it.
- **Purpose (if enabled experimentally):** higher-quality local reasoning beyond 4B capability.
- **Runtime:** MLX via oMLX (only if explicitly enabled).
- **License:** Apache-2.0.
- **Quantization:** 4-bit standard; 8-bit/bf16/mxfp8 variants exist.
- **Memory expectation:** ~5.6 GB (4-bit); peak ~6–7 GB at 4K ctx.
- **Latency expectation:** ~19–35 tok/s on M4 16 GB (community, unmeasured on Pramya) — measure only if enabled.
- **Streaming:** yes.
- **Compatibility note:** same mlx-lm `qwen3_5` arch support caveat as 4B.
- **Source:** https://huggingface.co/Qwen/Qwen3.5-9B , https://huggingface.co/mlx-community/Qwen3.5-9B-OptiQ-4bit
- **Fallback:** none in V1 — not part of any fallback chain.
- **Memory budget note (if ever enabled):** 4B + 9B must not be loaded simultaneously with speech models on 16 GB; model lifecycle (lazy load, unload, oMLX memory cap) enforces. Default V1 concurrent set never includes 9B.

### 2.4 BGE-M3

- **Model:** BAAI/bge-m3 (XLM-RoBERTa 0.6B; 1024-dim; max seq 8192; dense+sparse+multi-vector; 100+ languages)
- **Purpose:** candidate evidence retrieval, resume/JD retrieval, interview-context retrieval, competency retrieval, semantic search, evidence matching, historical-session retrieval.
- **Runtime:** MLX via oMLX `/v1/embeddings` (mlx-community conversions: fp16 ~1.1 GB, 8-bit ~592 MB, 6-bit ~457 MB, 4-bit ~321 MB).
- **License:** MIT (model + MLX conversions).
- **Important licensing note:** third-party `mlx-embeddings` Python library is **GPL-3.0**. Pramya calls embeddings through oMLX's HTTP endpoint (Apache-2.0 server) rather than depending on the GPL library. See ADR-014.
- **Memory expectation:** ~321 MB (4-bit) resident.
- **Batching:** supported (oMLX).
- **Source:** https://huggingface.co/BAAI/bge-m3 , https://huggingface.co/mlx-community/bge-m3-mlx-4bit
- **Fallback:** oMLX down → skip semantic retrieval, use FTS only (degraded).
- **Why selected:** spec-mandated embedding model; multilingual, strong retrieval.

### 2.5 Qwen3-Reranker-0.6B

- **Model:** Qwen/Qwen3-Reranker-0.6B (MLX: `mlx-community/Qwen3-Reranker-0.6B-4bit` ~331 MB)
- **Purpose:** candidate evidence reranking, resume-evidence retrieval, JD-to-evidence matching, interview-context retrieval, high-value semantic ranking.
- **Runtime:** MLX via oMLX `/v1/rerank` (query, documents, top_n).
- **License:** Apache-2.0.
- **Memory expectation:** ~331 MB (4-bit).
- **Source:** https://huggingface.co/Qwen/Qwen3-Reranker-0.6B , https://huggingface.co/mlx-community/Qwen3-Reranker-0.6B-4bit
- **Fallback:** skip reranking (top-K direct) if unavailable.
- **Why selected:** spec-mandated; Apache-2.0 (jina-reranker-v3-mlx is CC-BY-NC — non-commercial, rejected).

### 2.6 Parakeet-TDT-0.6B-v3 (live ASR)

- **Model:** nvidia/parakeet-tdt-0.6b-v3 (FastConformer + TDT transducer; 25 European languages; INT8 ~755 MB / INT4 ~489 MB MLX conversions; `parakeet-mlx` package)
- **Purpose:** PRIMARY live-interview ASR: real-time transcription, partial transcripts, live turn detection support, word timestamps, interview transcript generation.
- **Runtime:** host-native MLX (`parakeet-mlx`), 16 kHz mono.
- **License:** CC-BY-4.0 (attribution required; commercial OK). sherpa-onnx exports inherit it (some community pages mislabel Apache-2.0 — upstream is CC-BY-4.0).
- **Streaming constraint (verified):** upstream model is offline/non-chunked; sherpa-onnx has no true streaming for it (issue #2918) — only simulated/pseudo-streaming (re-decode growing buffer). MLX path (`parakeet-mlx`) supports chunked streaming with finalized/draft token phases; NVIDIA supports real streaming via NeMo chunked inference. Pramya V1: chunked/pseudo-streaming with VAD-gated short windows + partial transcript agreement pattern (see ADR-012, VOICE_ARCHITECTURE).
- **Fallback live path:** Parakeet chunked streaming → manual text input. (Qwen3-ASR on MLX is offline/chunked only — NOT a native-streaming live fallback; native streaming requires vLLM backend.)
- **Memory expectation:** ~0.5–0.8 GB (INT8/INT4).
- **Latency expectation:** ~100× realtime on M-series (community); measure at Phase 7.
- **Source:** https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3 , https://github.com/senstella/parakeet-mlx , https://github.com/k2-fsa/sherpa-onnx/issues/2918
- **Why selected:** spec-mandated live ASR; small, fast, good accuracy, Apple-Silicon-suitable.
- **Alternatives rejected:** Nemotron-3.5-ASR-Streaming is permission-gated (not V1, document only); Whisper-family not spec'd.

### 2.7 Qwen3-ASR-1.7B (recorded / high-quality ASR)

- **Model:** Qwen/Qwen3-ASR-1.7B (30 languages + 22 Chinese dialects; offline AND streaming inference supported via official vLLM backend; `pip install qwen-asr`; MLX: `mlx-community/Qwen3-ASR-1.7B-8bit` ~2.35 GB, `-4bit` ~1.5 GB via mlx-audio)
- **Purpose:** uploaded recordings, archival audio, high-quality transcription, multilingual transcription, offline reprocessing, transcript correction, non-live audio analysis. NOT the default live path (spec §11/§12).
- **Runtime:** host-native MLX (`mlx-audio` STT).
- **License:** Apache-2.0.
- **Memory expectation:** ~0.9–2.4 GB (4-bit/8-bit).
- **Streaming:** MLX path is offline/chunked (single-pass per chunk) — NOT native streaming. Native streaming requires the official vLLM backend (`qwen-asr[vllm]`), which is not part of the MLX deployment. MLX Qwen3-ASR serves as offline/chunked fallback only (documented decision, ADR-012).
- **Source:** https://huggingface.co/Qwen/Qwen3-ASR-1.7B , https://huggingface.co/mlx-community/Qwen3-ASR-1.7B-8bit
- **Why selected:** spec-mandated secondary ASR; distinct responsibility (recorded/high-quality vs live).

### 2.8 Qwen3-TTS-0.6B (TTS)

- **Model:** Qwen/Qwen3-TTS-12Hz-0.6B-Base (official name; + CustomVoice variant; 10 languages; discrete multi-codebook LM, 12 Hz tokenizer). MLX: `aitytech/Qwen3-TTS-12Hz-0.6B-Base-MLX-4bit` ~981 MB; used via mlx-audio TTS.
- **Purpose:** default interviewer voice; streaming output, low perceived latency, controllable voice, cancellation, interruption handling, chunk streaming, browser playback.
- **Runtime:** host-native MLX (mlx-audio).
- **License:** Apache-2.0.
- **Memory expectation:** ~1 GB (4-bit).
- **Streaming:** generator-based; sentence-level splitting + jitter buffer (~120–250 ms first chunk) for low latency.
- **Cancellation:** cooperative (CancelScope-style) between chunks — required for stale-TTS prevention (ADR-012, Phase 9).
- **Source:** https://huggingface.co/Qwen/Qwen3-TTS-12Hz-0.6B-Base , https://huggingface.co/aitytech/Qwen3-TTS-12Hz-0.6B-Base-MLX-4bit
- **Fallback:** text interviewer response when TTS unavailable.
- **Why selected:** spec-mandated V1 TTS (Apache-2.0, MLX-supported).
- **Alternatives rejected (documented, not V1):** Voxtral TTS, Soprano, Kokoro, IndexTTS, Zonos, VibeVoice, Higgs Audio, Magpie TTS — spec says do not make mandatory in V1; keep as future candidates.

---

## 3. Model / Runtime Compatibility Matrix (M4 16 GB)

| Model | Runs on M4 16GB | MLX | oMLX | Streaming | Batch | Cancel | Est. resident |
|---|---|---|---|---|---|---|---|
| deepseek-v4-flash | N/A (cloud) | — | — | yes | yes | client-side | 0 |
| Qwen3.5-4B 4-bit (`pramya-4b`) | yes | yes | yes | yes | yes | client-side | ~3 GB |
| Qwen3.5-9B 4-bit | yes* | yes | yes | yes | yes | client-side | ~5.6 GB |
| BGE-M3 4-bit | yes | yes | yes | yes | yes | n/a | ~0.3 GB |
| Qwen3-Reranker-0.6B 4-bit | yes | yes | yes | n/a | yes | n/a | ~0.3 GB |
| Parakeet-TDT v3 INT8/4 | yes | yes | no (host-native) | chunked/pseudo | yes | mid-window | ~0.5–0.8 GB |
| Qwen3-ASR-1.7B 8-bit | yes | yes | audio via mlx-audio | yes (native) | yes | yes | ~0.9–2.4 GB |
| Qwen3-TTS-0.6B 4-bit | yes | yes | audio via mlx-audio | yes | n/a | cooperative | ~1 GB |

*\*9B is DEFERRED from V1 production: it runs on the hardware but is not part of the
required stack, not a fallback, not a routing target, and not a required download.*

**16 GB budget rule (V1 default):** one LLM — the 4B workhorse — + BGE-M3 +
reranker (~4–6.5 GB total) OR speech stack (ASR + TTS, ~1.5–3 GB) + small LLM.
9B is not in the default concurrent set. If 9B is ever enabled experimentally,
never load 4B + 9B + ASR + TTS simultaneously; model lifecycle service enforces
memory cap, lazy load, unload; speech runs on a single serialized MLX worker
(MLX Metal workloads should not run concurrently from multiple threads).

---

## 4. License Audit Notes

- Apache-2.0: Qwen3.5-4B (production), Qwen3.5-9B (deferred/experimental),
  Qwen3-Reranker-0.6B, Qwen3-ASR-1.7B, Qwen3-TTS-0.6B, oMLX, FastMCP, DeepEval.
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
| **Qwen3.5-9B** | **local LLM** | **DEFERRED from V1 production (historical consideration; experimental candidate only — §2.3). Not required, not a fallback, not a routing target.** |

---

## 6. Local Runtime Verification Baseline (required at Phase 4)

Before any Phase 1+ work depends on local inference, the oMLX + `pramya-4b`
baseline must be verified (no 9B dependency):

- [ ] `pramya-4b` is discoverable through oMLX (model alias/profile exists)
- [ ] `pramya-4b` loads successfully on M4 16 GB
- [ ] thinking is disabled by default — explicitly on load/request (`enable_thinking: false` in oMLX profile + task policy), not reliant on model default
- [ ] normal generation works (`/v1/chat/completions`)
- [ ] structured JSON generation works (JSON-schema response_format)
- [ ] model alias/profile (`pramya-4b`) works through the router config
- [ ] no 9B dependency exists anywhere in config/setup/tests

No performance or quality claims beyond verified facts may be recorded
(measure at Phase 4; see §2.2 latency note).
