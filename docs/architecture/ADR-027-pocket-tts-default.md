# ADR-027 — TTS Provider: Kyutai Pocket TTS becomes default (Qwen3 kept as fallback)

- Status: **Accepted**
- Date: 2026-08-15
- Replaces: supersedes the ADR-025 default choice (Qwen3-TTS via oMLX stays
  available as `TTS_PROVIDER=qwen3` but is no longer the default)
- Related: ADR-012 (voice models), ADR-023 (text→DeepSeek, audio→local),
  ADR-025 (previous TTS provider decision)

## Context

Pramya V1.1 realtime voice has one primary product metric:
TURN_TO_FIRST_AUDIO (candidate turn ends → first audible interviewer audio).
The previous benchmark (ADR-025) chose Qwen3-TTS (oMLX) over Pocket TTS
because Pocket was then English-only, behind a gated HF repo, a new CPU
dependency, and its streaming first-audio was only estimated from upstream
claims. The directive for this evaluation: re-measure BOTH providers on the
actual machine and inside the actual Pramya voice path, and only switch if
Pocket proves materially faster with no regression in streaming,
cancellation, quality, memory, or stability.

## Benchmark method (boundaries)

- Same machine (Apple Silicon M4, 16 GB), same texts (SHORT / MEDIUM / LONG
  interview responses), same warm state, sequential runs, 1/5/10/20
  utterances per sequence.
- COLD = process/model start → first PCM; WARM = TTS invocation → first PCM;
  STREAM = invocation → first streamed chunk; TOTAL = invocation → final PCM;
  RTF = audio duration / wall time.
- Qwen boundary = production path (HTTP POST /v1/audio/speech, per-segment
  full-WAV). Pocket boundary = `generate_audio_stream` per-chunk yield.
- Harness: `scripts/tts_bench.py` (committed).
- Versions: pocket-tts 2.1.0 (torch 2.13.0), Qwen3-TTS-12Hz-0.6B-Base-MLX-4bit
  via oMLX on the same host.

## Measured results (warm, same machine)

| Metric | Qwen3 (oMLX) | Pocket (CPU) | Delta | Winner |
|---|---|---|---|---|
| warm first PCM (SHORT) | 634 ms | 30 ms | 21× | Pocket |
| warm first PCM (MEDIUM) | 2 152 ms | 31 ms | 69× | Pocket |
| warm first PCM (LONG) | 4 333 ms | 31 ms | 140× | Pocket |
| native stream first chunk | 320-416 ms | 30 ms | ~11× | Pocket |
| total (LONG, ~12 s audio) | 4 333 ms | 1 281 ms | 3.4× | Pocket |
| RTF (real-time factor) | 2.9-3.0× | 8.3-9.0× | ~3× | Pocket |
| model RSS (resident) | 1.71 GB (oMLX) | 0.84-0.96 GB | −44% | Pocket |
| cold model load (cached) | — | 0.8 s | | Pocket |
| sustained 20-utterance median | 2 700 ms | 678 ms | 4× | Pocket |

Cold Qwen model load was not re-measured this session (model was resident);
the historical cold load under memory pressure was ~160 s (oMLX load) vs
Pocket 0.8 s.

## End-to-end in the real Pramya voice path (WS, fake-mic, real DeepSeek + Parakeet)

| Metric | Qwen3 | Pocket | Winner |
|---|---|---|---|
| Q1 tts_start → first PCM frame | 7.35 s | 1.62 s | Pocket (4.5×) |
| Q2 final_transcript → first PCM frame | 9.13 s | 5.67 s | Pocket (1.6×) |
| 10-turn sustained: first-audio median | — | 3.34 s (3.06-3.81, no drift) | Pocket |
| stale frames after interrupt | 0 | 0 | tie |

The Q1 gap is dominated by per-segment synthesis: Qwen full-WAV synthesis of
the first sentence (~5-7 s) vs Pocket per-chunk streaming (~30-100 ms first
chunk + LLM TTFT).

## Quality

Objective ASR round-trip (Parakeet) on both providers' output for all three
texts: word-perfect transcripts for both. No intelligibility regression for
English interview speech. Pocket speaks slightly faster (LONG: 11.8 s vs
13.2 s audio).

## Cancellation / barge-in

Pocket's streaming API is a sync generator; each sentence is decoded by a
daemon thread. Cancellation stops delivery immediately (generation guard,
0 stale WS frames measured); the in-flight sentence tail burns bounded CPU
(≤ ~1 s) and then exits; thread count returns to baseline; the provider
remains usable after cancel. Serialization: one generation at a time via
provider lock + the engine's existing `_speech_lock` (upstream API is not
thread-safe).

## Licensing

- Package `pocket-tts` 2.1.0: MIT.
- Weights `kyutai/pocket-tts-without-voice-cloning`: CC-BY-4.0 (attribution
  required; commercial use permitted).
- Reference voice "alba" (kyutai/tts-voices): per-voice attribution on the
  voices repo; document before public release.

## Decision

1. `TTS_PROVIDER=pocket` becomes the default; Pocket is the V1.1 production
   TTS for English single-voice interview speech.
2. Qwen3-TTS (oMLX) is retained as the fallback/benchmark provider
   (`TTS_PROVIDER=qwen3`) — the oMLX integration, warmup, and voice profile
   are untouched.
3. Provider boundary: the voice engine consumes a duck-typed
   `TTSSynthesizer` seam (`synthesize` / `synthesize_stream` / `warmup` +
   `supports_stream`); no Pocket-specific logic in the engine; selection is
   configuration-driven (`backend/app/api/v1/voice.py::_build_tts`).
4. Pocket runs in the backend process (torch CPU); model + one fixed voice
   load lazily once and are reused; the engine awaits warmup before the first
   question so cold load never stalls first audio.

## Known limitations

- +~1.1 GB RSS in the backend process once loaded (torch + model), vs Qwen3
  which keeps ~1.7 GB resident inside oMLX when warm — net memory is lower,
  but the cost moves into the API process and adds a torch install
  (~2 GB on disk; the backend container image grows accordingly).
- English-focused single voice "alba" (fits the requirement: English only,
  one voice acceptable). No multilingual switching.
- Cancellation is prompt but not instantaneous: the in-flight sentence's
  decode tail finishes (~≤1 s CPU) before the worker exits.
- In-pipeline sustained evidence: 10-turn loop stable (first-audio 3.06-3.81 s,
  no drift) + standalone 20-utterance sequences stable (no RSS growth);
  20-30-turn in-pipeline runs remain NOT_VERIFIED.

## Fallback behavior

Provider-agnostic: if TTS fails (either provider), the engine skips the
segment, emits `tts_unavailable`, and degrades to a text interviewer
response — unchanged behavior, no benchmark-specific switching.
