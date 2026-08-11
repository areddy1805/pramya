# Pramya — Voice Architecture

> Companion to master plan §16 and ADR-005/016.
> Voice is a first-class feature: explicit state machine, streaming ASR/TTS, correctness-grade interruption.

---

## 1. Pipeline

```
Microphone → AudioWorklet capture (PCM16 16kHz)
  → WebSocket /ws/voice/{interview_id}
  → VoiceEngine (server state machine)
  → Parakeet-TDT-0.6B-v3 streaming chunks (partial transcripts)
  → turn detection (client energy + server finalization, local-agreement commit)
  → final transcript
  → InterviewGraph (LangGraph state machine: evidence retrieval → reasoning → next action)
  → interviewer response text stream
  → sentence/chunk segmentation
  → Qwen3-TTS-0.6B streaming
  → WebSocket audio chunks (PCM 24kHz)
  → AudioWorklet playback
```

Cancellation supported at every boundary: LLM task cancel, TTS queue clear, client buffer clear.

## 2. Explicit State Machine

States: `listening`, `processing`, `speaking`, `paused`, `interrupted`, `cancelled`, `completed`, `error`, plus session-level `reconnecting`. Enforced server-side in VoiceEngine; mirrored client-side (single source of truth = server, broadcast as WS `state` events).

Transitions (examples):

```
listening ──user ends turn──▶ processing ──▶ speaking
speaking ──user interrupts──▶ interrupted ──▶ (clear TTS) ──▶ listening
any ──pause──▶ paused ──resume──▶ (previous state)
listening/speaking ──stop──▶ cancelled
error ──(recoverable)──▶ error_recovery ──▶ listening
```

Rules: no stale TTS after interrupt (tested); interruption during generation cancels in-flight LLM; state preserved in LangGraph checkpoint + session row.

## 3. Audio Data Model (privacy-first)

- `audio_segment` (kind input/output, storage_key, duration_ms, retention_until) — stored only if user opts in; default: process-and-discard or transient.
- `transcript_segment` (partial/final, timestamps, seq) — persisted (transcript is the durable artifact).
- Retention policy configurable (`VOICE_RETENTION_DAYS`); deletion endpoints for session/audio/transcript.

## 4. ASR: Parakeet-TDT-0.6B-v3 (live)

- `parakeet-mlx` `transcribe_stream(context_size=(256,256))`; feed ~1s PCM chunks; partial text per chunk; finalize with local-agreement commit (N chunks agree) for turn boundaries.
- Word timestamps → communication analysis (duration, pauses, filler detection).
- Verified limitation: chunked pseudo-streaming (not cache-aware) — acceptable; Nemotron-3.5 ASR Streaming = upgrade candidate.
- Quantization: int8 recommended (~1.3GB), int4 for headroom.

## 5. ASR: Qwen3-ASR-1.7B (recorded/archival)

- Offline reprocessing of uploaded recordings / transcript correction; multilingual; NOT in live loop (spec §12).
- Runtime: official `qwen_asr`; MLX path verified at Phase 7/8 (GGUF/transcribe.cpp fallback).

## 6. TTS: Qwen3-TTS-0.6B

- mlx-audio `generate(stream=True, streaming_interval≈0.32)`; sentence segmentation from LLM token stream; audio chunks (PCM 24kHz) over WS.
- Interrupt: discard queued chunks + cancel generation task; client clears AudioWorklet buffer.
- CustomVoice preset for consistent interviewer voice; TTFA measured and logged.

## 7. WebSocket Protocol (v1)

Client → server (JSON control + binary audio):
- `start_turn`, `end_turn`, `interrupt`, `pause`, `resume`, `stop`, `replay`, binary PCM audio chunks.

Server → client:
- `state` (machine transitions), `partial_transcript`, `final_transcript`, `question`, `evaluation`, `follow_up`, `audio_chunk` (PCM + seq), `tts_start`, `tts_stop`, `error` (actionable), `reconnect`.

- Heartbeat every ~30s; exponential-backoff reconnect; resume re-syncs transcript from DB checkpoint.
- Auth per deployment: token query param (WS cannot set headers).

## 8. Browser Client

- `AudioContext` + AudioWorklet for capture and playback (`latencyHint: "interactive"`).
- Turn detection: energy/VAD heuristics client-side + server finalization; no pseudo-scientific claims.
- Interrupt button and barge-in (audio level) both clear playback buffer.
- Full cleanup on unmount: close context, stop tracks, close WS, cancel rAF.

## 9. Failure Handling

| Failure | Behavior |
|---|---|
| DeepSeek down | local model (degraded quality) |
| oMLX/ASR down | manual transcript mode |
| TTS down | text interviewer response |
| retrieval down | degraded interview mode |
| WS dropped | reconnect + transcript re-sync |
| ASR/TTS/LLM timeout | per-node TimeoutPolicy; retry policy; actionable error |

Never "Something went wrong" — always actionable degraded state.

## 10. Voice Test Matrix (spec §42)

normal, fast, slow, long, short, silence, background noise, interruption, double interruption, pause, resume, stop, browser refresh, network loss, ASR failure, TTS failure, LLM timeout, LLM cancellation, partial transcript, late transcript, duplicate transcript, stale TTS → each has a test in Phase 9.

## 11. Performance Targets (measured then documented)

- TTFA (time-to-first-audio) and TTF-Transcript low on M4; immediate interruption (<~100ms perceived); no stale playback; bounded memory; no sustained uncontrolled thermal load. Exact thresholds recorded in DEPLOYMENT/TROUBLESHOOTING after measurement.
