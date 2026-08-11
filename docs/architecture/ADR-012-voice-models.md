# ADR-012 — Voice Model Stack (ASR/TTS)

**Status:** Accepted
**Date:** 2026-08

## Context

Voice is first-class: live streaming ASR with partial transcripts and turn
detection, plus streamed TTS with interruption/cancellation. Spec mandates
Parakeet-TDT-0.6B-v3 for live ASR, Qwen3-ASR-1.7B for recorded/multilingual,
Qwen3-TTS-0.6B for TTS. All verified compatible (2026-08): MLX conversions
exist; licenses CC-BY-4.0 / Apache 2.0; memory fits 16 GB.

## Problem

How to implement live ASR + recorded ASR + TTS with correct streaming,
interruption, and resource bounds?

## Decision

- **Live ASR**: Parakeet-TDT-0.6B-v3 (INT8 ~755 MB) via `parakeet-mlx`
  `transcribe_stream(context_size=(256,256))` — true streaming with
  finalized/draft token phases; feed 1 s audio chunks; partial transcripts
  from draft tokens; turn detection on finalization; 16 kHz mono input from
  browser AudioWorklet capture.
- **Recorded ASR**: Qwen3-ASR-1.7B (8-bit ~2.4 GB) via `mlx-audio` STT for
  uploaded recordings, archival audio, multilingual (52 langs), offline
  reprocessing, transcript correction. Never the default live path.
- **TTS**: Qwen3-TTS-12Hz-0.6B-Base (4-bit ~981 MB, ~120 ms first audio
  chunk) streaming MLX; pipeline LLM token stream → sentence/chunk
  segmentation → TTS → audio chunk → browser playback.
- Voice state machine explicit: listening, processing, speaking, paused,
  interrupted, cancelled, completed, error. Cancellation at every boundary;
  stale TTS after interruption is a correctness bug.
- Lifecycle: Parakeet + TTS + one LLM is the peak live envelope (~10 GB);
  ASR-1.7B loads only for reprocessing tasks.

## Alternatives

- Whisper live — rejected: windowed, not streaming.
- Qwen3-ASR as default live — rejected (spec: routing demo; latency/memory).
- Cloud ASR/TTS — rejected: cost + privacy; local-first.

## Tradeoffs

- Two ASR models to maintain; deliberate routing complexity.
- parakeet-mlx is community-maintained (senstella) — pin + health-check.

## Consequences

- `packages/voice/`: audio capture protocol, ASR adapters, TTS adapter,
  state machine, cancellation tokens, retention policy.
- Voice test matrix (interruption, silence, refresh, ASR/TTS failure…).
