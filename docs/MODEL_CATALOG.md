# Pramya — Model Catalog

> Defines every model used by Pramya V1, with license, runtime, memory, and compatibility evidence.
> Verified against current official repositories/docs — August 2026.
> Evidence and reasoning for the verification recorded in `docs/architecture/012-model-stack-verification.md`.

---

## 1. Model Inventory Summary

| # | Model | Purpose | Runtime | License | Local/Cloud |
|---|---|---|---|---|---|
| 1 | deepseek-v4-flash | Cloud reasoning, deep evaluation, synthesis | DeepSeek API | DeepSeek terms (proprietary cloud API) | Cloud |
| 2 | Qwen3.5-4B | Cheap local classification/extraction/transformations | MLX via oMLX | Apache-2.0 | Local |
| 3 | Qwen3.5-9B | Higher-quality local reasoning, local question gen/eval | MLX via oMLX | Apache-2.0 | Local |
| 4 | BGE-M3 | Embeddings (dense retrieval, multilingual) | MLX via oMLX | MIT | Local |
| 5 | Qwen3-Reranker-0.6B | Reranking candidate evidence | MLX via oMLX | Apache-2.0 | Local |
| 6 | Parakeet-TDT-0.6B-v3 | Live ASR (pseudo-streaming + VAD) | Host-native MLX (parakeet-mlx) | CC-BY-4.0 | Local |
| 7 | Qwen3-ASR-1.7B | Recorded/multilingual ASR, reprocessing | Host-native MLX (mlx-audio) | Apache-2.0 | Local |
| 8 | Qwen3-TTS-0.6B | Interviewer TTS (streaming) | Host-native MLX (mlx-audio) | Apache-2.0 | Local |

---

## 2. Detailed Entries

### 2.1 deepseek-v4-flash

- **Model:** DeepSeek V4 Flash
- **Version:** deepseek-v4-flash (model ID; V4-Flash-0731 checkpoint public beta as of Aug 2026; legacy `deepseek-chat`/`deepseek-reasoner` IDs deprecated 2026-07-24)
- **Purpose:** complex reasoning, adaptive question generation, deep answer evaluation, evidence interpretation, difficult follow-ups, system-design reasoning, final synthesis.
- **Runtime:** DeepSeek cloud API, OpenAI-compatible. Base URL `https://api.deepseek.com`. Also supports Anthropic-format endpoint.
- **Architecture:** 284B total / 13B active (MoE).
- **Context window:** 1,000,000 tokens; max output up to 384K tokens.
- **Modes:** thinking (default) and non-thinking; `reasoning_effort` parameter (high/max). Mode must be task-policy-driven and observable in telemetry (ADR-004).
- **Quantization:** N/A (cloud).
- **Memory expectation:** N/A (cloud).
- **Latency expectation:** higher than local; use non-thinking mode for latency-sensitive ops.
- **Streaming:** supported (SSE).
- **Structured output:** JSON output + function calling + Responses API support (current).
- **Pricing (Aug 2026):** ~$0.14/1M input (cache miss), ~$0.0028/1M (cache hit), ~$0.28/1M output. Verify at api-docs.deepseek.com.
- **License:** proprietary cloud API terms. No model redistribution. Do not send PII beyond necessity.
- **Source:** https://api-docs.deepseek.com/ , https://api-docs.deepseek.com/quick_start/pricing/
- **Fallback:** Qwen3.5-9B (local) for degraded mode.
- **Why selected:** spec-mandated primary cloud reasoning model (spec §6.1).
- **Why alternatives rejected:** legacy IDs deprecated; spec forbids replacing without concrete incompatibility — none found.

### 2.2 Qwen3.5-4B

- **Model:** Qwen3.5-4B (official: `Qwen/Qwen3.5-4B`; MLX: `mlx-community/Qwen3.5-4B-4bit` ~3.06 GB, `mlx-community/Qwen3.5-4B-OptiQ-4bit` ~3.0 GB)
- **Purpose:** fast classification, lightweight extraction, metadata analysis, simple transformations, structured extraction, cheap conversational ops, background processing.
- **Runtime:** MLX via oMLX (`/v1/chat/completions`, streaming, JSON-schema structured output, tool calling).
- **License:** Apache-2.0.
- **Quantization:** 4-bit standard; OptiQ mixed-precision variants exist.
- **Memory expectation:** ~2.9–3.1 GB (4-bit).
- **Latency expectation:** ~26–168 tok/s on Apple Silicon (community benchmarks; M3/M4-class).
- **Streaming:** yes.
- **Batching:** oMLX continuous batching.
- **Compatibility note:** initial mlx-lm lag for `qwen3_5` architecture (ml-explore/mlx-lm issue #1136) — must use recent mlx-lm/mlx-vlm. Verify at Phase 4.
- **Source:** https://huggingface.co/Qwen/Qwen3.5-4B , https://huggingface.co/mlx-community/Qwen3.5-4B-4bit
- **Fallback:** none (local); if unavailable, route task to Qwen3.5-9B or DeepSeek per policy.
- **Why selected:** spec-mandated cheap local model.
- **Why alternatives rejected:** spec forbids reselection absent concrete incompatibility; none found (fits 16GB alongside lifecycle management).

### 2.3 Qwen3.5-9B

- **Model:** Qwen3.5-9B (official: `Qwen/Qwen3.5-9B`; MLX: `mlx-community/Qwen3.5-9B-MLX-4bit` ~5.6 GB, OptiQ 4-bit ~5.6 GB)
- **Purpose:** higher-quality local reasoning, candidate analysis, local question generation, local evaluation, synthesis where cloud unnecessary.
- **Runtime:** MLX via oMLX.
- **License:** Apache-2.0.
- **Quantization:** 4-bit standard; 8-bit/bf16/OptiQ/mxfp8 variants exist.
- **Memory expectation:** ~5.6 GB (4-bit).
- **Latency expectation:** ~51 tok/s M3 Max-class (community); slower on base M4 — measure.
- **Streaming:** yes.
- **Compatibility note:** same mlx-lm `qwen3_5` arch support caveat as 4B.
- **Source:** https://huggingface.co/Qwen/Qwen3.5-9B , https://huggingface.co/mlx-community/Qwen3.5-9B-MLX-4bit
- **Fallback:** DeepSeek for complex reasoning; Qwen3.5-4B for cheap ops.
- **Why selected:** spec-mandated local reasoning model.
- **Memory budget note:** 4B + 9B must not be loaded simultaneously with speech models on 16GB; use model lifecycle (lazy load, unload, oMLX memory cap).

### 2.4 BGE-M3

- **Model:** BAAI/bge-m3 (XLM-RoBERTa 0.6B; 1024-dim; max seq 8192; dense+sparse+multi-vector; 100+ languages)
- **Purpose:** candidate evidence retrieval, resume/JD retrieval, interview-context retrieval, competency retrieval, semantic search, evidence matching, historical-session retrieval.
- **Runtime:** MLX via oMLX `/v1/embeddings` (mlx-community conversions: fp16 ~1.1 GB, 8-bit ~592 MB, 6-bit ~457 MB, 4-bit ~321 MB).
- **License:** MIT (model weights + MLX conversions).
- **Important licensing note:** the third-party `mlx-embeddings` Python library is reported GPL-3.0. **Pramya must call embeddings through oMLX's HTTP endpoint (Apache-2.0 server) rather than depending on the GPL library**, to keep the project permissively licensed. See ADR-012.
- **Memory expectation:** ~321 MB (4-bit) resident.
- **Batching:** supported (oMLX).
- **Source:** https://huggingface.co/BAAI/bge-m3 , https://huggingface.co/mlx-community/bge-m3-mlx-4bit
- **Fallback:** none needed (small); degraded mode if oMLX down → skip semantic retrieval, use FTS only.
- **Why selected:** spec-mandated embedding model; multilingual, strong retrieval.
- **Why alternatives rejected:** spec forbids reselection; MIT + MLX support confirmed.

### 2.5 Qwen3-Reranker-0.6B

- **Model:** Qwen/Qwen3-Reranker-0.6B (MLX: `mlx-community/Qwen3-Reranker-0.6B-4bit` ~331 MB)
- **Purpose:** candidate evidence reranking, resume-evidence retrieval, JD-to-evidence matching, interview-context retrieval, high-value semantic ranking.
- **Runtime:** MLX via oMLX `/v1/rerank` (Cohere/Jina-compatible: query, documents, top_n).
- **License:** Apache-2.0.
- **Memory expectation:** ~331 MB (4-bit).
- **Source:** https://huggingface.co/Qwen/Qwen3-Reranker-0.6B , https://huggingface.co/mlx-community/Qwen3-Reranker-0.6B-4bit
- **Fallback:** skip reranking (top-K direct) if unavailable.
- **Why selected:** spec-mandated; Apache-2.0 (vs jina-reranker-v3-mlx which is CC-BY-NC — non-commercial, rejected).

### 2.6 Parakeet-TDT-0.6B-v3 (live ASR)

- **Model:** nvidia/parakeet-tdt-0.6b-v3 (FastConformer+TDT transducer, offline model, 25 European languages; INT8 ~755 MB, INT4 ~489 MB MLX conversions; parakeet-mlx package)
- **Purpose:** PRIMARY live-interview ASR: real-time transcription, partial transcripts, live turn detection support, word timestamps, interview transcript generation.
- **Runtime:** host-native MLX (parakeet-mlx), 16 kHz mono.
- **License:** CC-BY-4.0 (attribution required; commercial OK). sherpa-onnx exports inherit it (some community pages mislabel Apache-2.0 — upstream is CC-BY-4.0).
- **Streaming constraint (verified, ADR-011):** the model is **offline/non-chunked**. sherpa-onnx has NO true streaming for it (issue #2918) — only simulated/pseudo-streaming (re-decode growing buffer). MLX path (parakeet-mlx) supports chunking; NVIDIA supports real streaming via NeMo chunked inference. Pramya V1: pseudo-streaming with VAD-gated short windows + partial local-agreement pattern. Fallback live path: Qwen3-ASR-1.7B (native streaming). Future candidate: nvidia/NVIDIA-Nemotron-3.5-ASR-Streaming-Multilingual-0.6b (permission-gated; document only).
- **Memory expectation:** ~0.5–0.8 GB (INT8/INT4).
- **Latency expectation:** ~0.82% LibriSpeech WER at ~95× RTFx M3 Max (INT8).
- **Source:** https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3 , https://github.com/senstella/parakeet-mlx , https://github.com/k2-fsa/sherpa-onnx/issues/2918
- **Fallback:** Qwen3-ASR-1.7B (streaming) → manual text input.
- **Why selected:** spec-mandated live ASR; small, fast, good accuracy, Apple-Silicon-suitable.
- **Why alternatives rejected:** Nemotron-3.5-ASR-Streaming is permission-gated (not V1); Whisper-family not spec'd.

### 2.7 Qwen3-ASR-1.7B (recorded / high-quality ASR)

- **Model:** Qwen/Qwen3-ASR-1.7B (released Jan 2026; 30 languages + 22 Chinese dialects; offline AND streaming inference supported; `pip install qwen-asr`; MLX: `mlx-community/Qwen3-ASR-1.7B-8bit` ~1.7 GB, `-4bit` ~0.9 GB via mlx-audio)
- **Purpose:** uploaded recordings, archival audio, high-quality transcription, multilingual transcription, offline reprocessing, transcript correction, non-live audio analysis. NOT default live path.
- **Runtime:** host-native MLX (mlx-audio STT).
- **License:** Apache-2.0.
- **Memory expectation:** ~0.9–1.7 GB (4-bit/8-bit).
- **Streaming:** supported natively — usable as live fallback if Parakeet pseudo-streaming insufficient (ADR-011).
- **Source:** https://huggingface.co/Qwen/Qwen3-ASR-1.7B , https://huggingface.co/mlx-community/Qwen3-ASR-1.7B-8bit
- **Fallback:** none required.
- **Why selected:** spec-mandated secondary ASR; distinct responsibility (recorded/high-quality vs live).

### 2.8 Qwen3-TTS-0.6B (TTS)

- **Model:** Qwen/Qwen3-TTS-12Hz-0.6B-Base (official name; + CustomVoice variant; 10 languages; discrete multi-codebook LM, 12 Hz tokenizer). MLX: `aitytech/Qwen3-TTS-12Hz-0.6B-Base-MLX-4bit` ~981 MB; used via mlx-audio `tts.generate` / mlx-audio server.
- **Purpose:** default interviewer voice; streaming output, low perceived latency, controllable voice, cancellation, interruption handling, chunk streaming, browser playback.
- **Runtime:** host-native MLX (mlx-audio).
- **License:** Apache-2.0.
- **Memory expectation:** ~1 GB (4-bit); ~1.7–2.5 GB class for 8-bit/1.7B variants.
- **Streaming:** generator-based; sentence-level splitting + jitter buffer (~250 ms) for first-byte latency.
- **Cancellation:** cooperative (CancelScope-style) between chunks; required for stale-TTS prevention (ADR-011, Phase 9).
- **Source:** https://huggingface.co/Qwen/Qwen3-TTS-12Hz-0.6B-Base , https://huggingface.co/aitytech/Qwen3-TTS-12Hz-0.6B-Base-MLX-4bit
- **Fallback:** text interviewer response when TTS unavailable.
- **Why selected:** spec-mandated V1 TTS (Apache-2.0, MLX-supported).
- **Why alternatives rejected (documented, not V1):** Voxtral TTS, Soprano, Kokoro, IndexTTS, Zonos, VibeVoice, Higgs Audio, Magpie TTS — spec says do not make mandatory in V1; keep as future candidates.

---

## 3. Model / Runtime Compatibility Matrix (M4 16 GB)

| Model | Runs on M4 16GB | MLX | oMLX | Streaming | Batch | Cancel | Est. resident |
|---|---|---|---|---|---|---|---|
| deepseek-v4-flash | N/A (cloud) | — | — | yes | yes | client-side | 0 |
| Qwen3.5-4B 4-bit | yes | yes | yes | yes | yes | client-side | ~3 GB |
| Qwen3.5-9B 4-bit | yes | yes | yes | yes | yes | client-side | ~5.6 GB |
| BGE-M3 4-bit | yes | yes | yes | yes | yes | n/a | ~0.3 GB |
| Qwen3-Reranker-0.6B 4-bit | yes | yes | yes | n/a | yes | n/a | ~0.3 GB |
| Parakeet-TDT v3 INT8/4 | yes | yes | no (host-native) | pseudo-only | yes | mid-window | ~0.5–0.8 GB |
| Qwen3-ASR-1.7B 8-bit | yes | yes | audio via mlx-audio | yes (native) | yes | yes | ~0.9–1.7 GB |
| Qwen3-TTS-0.6B 4-bit | yes | yes | audio via mlx-audio | yes | n/a | cooperative | ~1 GB |

**16 GB budget rule:** never load 4B + 9B + ASR + TTS simultaneously. Typical concurrent set: one LLM (4B or 9B) + BGE-M3 + reranker (~4–6.5 GB) OR speech stack (ASR + TTS, ~1.5–2.5 GB) + small LLM. Model lifecycle service enforces memory cap (oMLX default cap = RAM − 8 GB), lazy load, unload, and single-serialized MLX worker for speech (MLX cannot run concurrent Metal workloads reliably; ADR-011).

## 4. License Audit Notes

- Apache-2.0: Qwen3.5-4B/9B, Qwen3-Reranker-0.6B, Qwen3-ASR-1.7B, Qwen3-TTS-0.6B, oMLX, mlx-audio (check current), FastMCP, DeepEval.
- MIT: BGE-M3 weights/conversions.
- CC-BY-4.0: Parakeet-TDT v3 (attribution required — record in NOTICE).
- Proprietary cloud terms: DeepSeek API.
- Avoid: `mlx-embeddings` (GPL-3.0) — use oMLX HTTP instead; jina-reranker-v3-mlx (CC-BY-NC) — rejected.
- Full inventory + attribution requirements: `NOTICE.md` (to be created at Phase 12; ADR-012).
