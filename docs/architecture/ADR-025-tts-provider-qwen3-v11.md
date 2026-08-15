# ADR-025 — TTS Provider: Qwen3-TTS (oMLX) for V1.1 Realtime Voice

- Status: **Accepted**
- Date: 2026-08-14
- Replaces: none (extends ADR-012 Voice Models / ADR-023 audio routing)
- Related: ADR-008 (observability), ADR-011 (oMLX runtime), ADR-012 (voice models)

## Context

V1.1 realtime voice requires the lowest achievable
TURN_TO_FIRST_AUDIO (candidate finishes speaking → first interviewer audio)
on the target hardware (Apple Silicon, 16 GB unified memory). The TTS
provider is the dominant contributor to first-audio latency in the V1
pipeline (full-utterance synthesis was measured at 10.5–40 s).

Two candidates were benchmarked (R13):

| Metric | Qwen3-TTS-12Hz-0.6B (oMLX/MLX) | Kyutai Pocket TTS (CPU PyTorch) |
|---|---|---|
| Native streaming | Yes (oMLX `stream`+`streaming_interval`) | Yes (`generate_audio_stream`) |
| Warm first PCM chunk | **5.16 s** (measured, benchmark utterance) | **~0.2–0.4 s** (estimated, published claims) |
| Warm total, ~120-char utterance | **10.35 s** (measured) | **2.2 s** (measured wall, incl. process startup) |
| Throughput | ~10 s for 120 chars | 8.7× real-time (measured) |
| Voice identity | Single deterministic speaker, provider voice mapping | Voice cloning from ~5 s sample |
| Language | Multi-language (auto) | **English-only** at launch |
| Model footprint | 1.71 GB resident (oMLX) | ~1 GB CPU |
| Runtime | oMLX (already integrated, Metal/MLX) | New dependency (PyTorch CPU) |
| Acquisition | Installed, weights verified | HF gated repo (ungated mirrors), additional install |
| Memory on 16 GB Mac | Co-resident with ASR in pinned oMLX | Additional process |
| Integration cost | None (in production path) | New provider behind TTS boundary |

Measurement basis: warm = model resident (pinned); Qwen3 measured via
direct oMLX `/v1/audio/speech` streaming probe; Pocket TTS measured via
`python -m pocket_tts generate` (CLI) on the same M4 machine. Pocket TTS
streaming first-audio is **estimated** from published claims (dev.to M4
review: ~214 ms; OmniVoice M3 Pro: ~33 ms first streamed chunk) — not
independently measured in a streaming harness this session.

## Decision

**Keep Qwen3-TTS (oMLX) as the V1.1 production TTS provider.**

Pocket TTS is classified **BENCHMARKED / CANDIDATE** — not integrated.

Rationale:

1. **Latency is not the only acceptance criterion.** Pocket TTS wins on
   first-audio latency, but V1.1 correctness invariants (deterministic
   professional voice per session, multi-language readiness, integration
   inside the existing oMLX audio runtime) matter as much as raw TTFA.
2. **Already-integrated stack, zero risk.** Qwen3-TTS is in the production
   path today: TTSClient, warmup, streaming relay, voice identity, pinned
   residency, interruption/barge-in all verified. Replacing it adds a
   provider boundary, a gated model acquisition, English-only constraint,
   and a second inference runtime on a 16 GB machine.
3. **Memory discipline.** V1.1 explicitly targets the 16 GB Mac. Adding a
   ~1 GB CPU PyTorch runtime alongside pinned oMLX models raises the
   memory ceiling risk demonstrated by the failed e2e10c run.
4. **Measured Qwen3 streaming works.** Warm first PCM 5.16 s in an
   isolated probe; in-run first-chunk ~10–16 s under full system load
   (memory pressure), improving to ~5 s when warm and unloaded. The
   streaming pipeline itself is proven.
5. **No silent replacement.** Adopting Pocket TTS without a full
   product-quality integration + acceptance test would be trading a known
   working system for an unverified one to claim a lower number.

## Consequences

- Qwen3-TTS-12Hz-0.6B-Base-MLX-4bit remains the sole production TTS
  provider (voice_id deterministic per session, provider voice `default`).
- Pocket TTS stays on the candidate list: revisit only with (a) a real
  streaming integration behind the TTSClient boundary, (b) an acceptance
  test proving first-audio + intelligibility + voice identity on the 16 GB
  Mac, (c) memory measurements showing no degradation. Until then it is
  BENCHMARKED / CANDIDATE only.
- The TTS benchmark numbers above are recorded in the V1.1 report; they
  are measurements, not predictions, and are separated into
  measured/estimated where applicable.
- oMLX audio models (ASR, TTS, reranker) are pinned in the oMLX
  model_settings.json to prevent mid-interview eviction reloads (the root
  cause of the earlier 79–128 s turn gaps). Pinning is an operational
  setting, not a code path change.
