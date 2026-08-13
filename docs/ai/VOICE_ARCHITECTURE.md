# Pramya — Voice Architecture

> Companion to master plan §16 and ADR-012.
> Voice is a first-class feature: explicit state machine, streaming ASR/TTS, correctness-grade interruption.

## 0. Implementation Status (2026-08-13, physical-mic speaker-integrity)

| Item | Status | Notes |
|---|---|---|
| H.1 concurrent engine | ✅ | `VoiceEngine.run()` receive loop never awaits TTS/ASR/DeepSeek/DB; work runs in `_tts_task` / `_answer_task` / `_start_session_task` |
| H.2 turn finalization | ✅ | auto (RMS speech → silence watchdog, `voice_silence_seconds`) + manual (`end_turn` / Done speaking) |
| H.3 answer loop | ✅ | end_turn → final ASR → `submit_answer` (DeepSeek) → evaluation event → next question → TTS |
| H.4 model routing | ✅ | `voice_live_asr_model` (Parakeet), `voice_offline_asr_model` (Qwen3-ASR), `voice_tts_model`; live ASR ≠ offline ASR |
| H.5 concurrency tests | ✅ | hot-loop interrupt mid-TTS, generation bump, no stale chunks, auto+manual end_turn, pause/resume/stop |
| H.6 playback lifecycle | ✅ | AudioContext created synchronously in click; playback gated on `state==='running'` |
| H.7 generation IDs | ✅ | `generation` on tts_start/tts_stop; server skips stale generations; client drops stale chunks |
| H.8 persistence | ✅ | `TranscriptSegment` rows per turn (question + final answer) with explicit `speaker` column |
| H.9 mic permission | ✅ | typed `micErrorMessage`: permission_denied / device_unavailable / mic_unavailable |
| H.10 audio persistence | ✅ | opt-in (`voice_store_audio`): candidate PCM16 → WAV under `audio_storage_dir`, `AudioSegment` row; replay via `GET /interviews/{id}/voice/audio[/{segment_id}]` |
| H.11 reconnect + heartbeat | ✅ | reconnect emits `resume` (authoritative state + last question); `heartbeat` → `heartbeat_ack`; client pings every 15s |
| H.12 communication analysis | ✅ | deterministic `CommunicationAnalyzer` from persisted transcript timestamps; speaker from the `speaker` column |
| H.13 playback-completion gating | ✅ | `tts_stop` no longer opens LISTENING; client sends `playback_complete{generation}` only after the real playback queue drains; server stays SPEAKING until then (see §2). Failure-mode guard `voice_playback_timeout_seconds` (45s) |
| H.14 server-authoritative mic gating | ✅ | only LISTENING accepts mic frames for ASR; SPEAKING frames counted + discarded (never ASR'd); other states counted |
| H.15 speaker integrity | ✅ | `transcript_segment.speaker` (`interviewer`/`candidate`/`unknown`) set at capture time (migration 0002 backfills legacy rows); communication analysis prefers the column |
| H.16 diagnostics | ✅ | `voice_listening` (playback_confirmed), `voice_answer` (accepted/discarded frames+bytes, listening_ms, interruptions), `voice_tts`/`voice_asr`/`voice_interrupt` telemetry |
| H.17 voice barge-in (opt-in) | ✅ | `voice_barge_in_enabled` (default OFF): sustained mic energy ≥ `voice_barge_in_rms` for `voice_barge_in_ms` during SPEAKING cancels TTS. Explicit `interrupt` control remains the guaranteed path |
| Real-model E2E (fake-device mic) | ✅ | passed 2026-08-12 (sessions 39/40/41) + 2026-08-13 with the new gating contract: `tts_stop → playback_complete → state:listening` verified with real Qwen3-TTS + Parakeet |
| Physical-mic E2E (real speakers+mic) | ⏳ NOT_VERIFIED | see §12 — the machine's physical mic delivered digital silence at the OS level (AVAudioRecorder peak 0); every software boundary verified; gating contract proven with real browser playback |

**Observable event contract (acceptance):** `state` (idle→starting→speaking→listening→processing…) → `question` → `tts_start{generation}` → binary chunks → `tts_stop{generation}` → `partial_transcript` → `turn_ended` → `final_transcript` → `answer_submitted` → `evaluation` → next `question` → … Interrupt: `interrupt` control → `state: interrupted` → `state: listening`, generation bumped, zero stale chunks.

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

States: `idle`, `starting`, `speaking` (== TTS playing), `listening`, `processing` (ASR → evaluation), `paused`, `interrupted`, `cancelled`, `completed`, `error`, plus session-level `reconnecting`. Enforced server-side in VoiceEngine; mirrored client-side (single source of truth = server, broadcast as WS `state` events).

**Playback-completion gating (speaker integrity — authoritative transition):**

```
TTS_PLAYING (speaking) ──tts_stop──▶ still SPEAKING (playback tail may sound)
    └─ client: playback queue drains + generation matches ──playback_complete──▶ LISTENING
    └─ client dead/glitched ──playback_timeout_seconds──▶ LISTENING (playback_confirmed=false, diagnostic)
```

`tts_stop` alone NEVER opens LISTENING. The mic window opens only on the
`playback_complete{generation}` handshake (stale generations ignored) or the
timeout guard. This is what makes it impossible for the interviewer's own
audio — still sounding from the browser queue — to become candidate input.

Transitions (examples):

```
speaking ──playback_complete──▶ listening
listening ──user ends turn──▶ processing ──▶ speaking
speaking ──user interrupts──▶ interrupted ──▶ (clear TTS, generation bump) ──▶ listening
speaking ──voice barge-in (opt-in)──▶ interrupted ──▶ listening
any ──pause──▶ paused ──resume──▶ (previous state)
speaking ──pause──▶ paused (TTS cancelled; client flushes playback queue)
listening/speaking ──stop──▶ completed · ──cancel──▶ cancelled
error ──(recoverable)──▶ listening
```

**Mic gating semantics (server-authoritative):**

- `LISTENING`: mic frames → candidate buffer → partial/final ASR. The only
  window that can become a candidate answer.
- `SPEAKING`: mic frames are counted (`discarded_tts_frames/bytes`) and never
  ASR'd. The client keeps the capture worklet live so the server can answer
  "was the mic active while the interviewer was speaking?" and so opt-in
  voice barge-in can detect sustained candidate energy.
- `processing`/`paused`/`interrupted`/`completed`/`cancelled`/`idle`: frames
  counted as discarded-other, never ASR'd.

Rules: no stale TTS after interrupt (tested); interruption during generation
cancels in-flight LLM; state preserved in LangGraph checkpoint + session row.

**Speaker-integrity guarantee:** every persisted `transcript_segment` carries
an explicit `speaker` value (`interviewer` for question rows, `candidate` for
answer rows) written at capture time — never inferred later. Legacy rows are
backfilled from the JSONB role; rows without evidence stay `unknown` (never
guessed).

## 3. Audio Data Model (privacy-first)

- `audio_segment` (kind input/output, storage_key, duration_ms, retention_until) — stored only if user opts in; default: process-and-discard or transient.
- `transcript_segment` (partial/final, timestamps, seq) — persisted (transcript is the durable artifact).
- Retention policy configurable (`VOICE_RETENTION_DAYS`); deletion endpoints for session/audio/transcript.

## 4. ASR: Parakeet-TDT-0.6B-v3 (live)

- `parakeet-mlx` `transcribe_stream(context_size=(256,256))`; feed ~1s PCM chunks; partial text per chunk; finalize with local-agreement commit (N chunks agree) for turn boundaries.
- **VAD-gated pseudo-streaming** (verified constraint, ADR-012): Parakeet v3 is an offline (full-context) model — no cache-aware streaming; sherpa-onnx has no true streaming for it either (k2-fsa/sherpa-onnx#2918). Live path = short decode windows + Silero VAD gating + local-agreement partials (emit partials, finalize on segment boundaries).
- **Fallback live path**: if Parakeet pseudo-streaming latency/quality is insufficient in Phase 8 measurement, chunked/offline Qwen3-ASR transcription (same runtime family) is the documented fallback, not a default change. MLX Qwen3-ASR is NOT native streaming; native streaming requires the vLLM backend and is not part of the MLX deployment.
- **Serialized speech inference**: MLX models cannot run concurrently from multiple threads — one serialized inference worker for speech; VAD on CPU/ANE; speech stack runs host-native (Docker cannot reach Metal).
- Word timestamps → communication analysis (duration, pauses, filler detection).
- Quantization: int8 recommended (~1.3GB), int4 for headroom.
- Upgrade candidate (not V1): Nemotron-3.5 ASR Streaming.

## 5. ASR: Qwen3-ASR-1.7B (recorded/archival)

- Offline reprocessing of uploaded recordings / transcript correction; multilingual; NOT in live loop (spec §12); MLX path is offline/chunked only — not native streaming (native streaming requires vLLM backend).
- Runtime: host-native MLX (mlx-audio 8-bit ~2.35GB / 4-bit ~1.5GB) or official `qwen_asr`; MLX path verified at Phase 7/8 (GGUF/transcribe.cpp fallback).

## 6. TTS: Qwen3-TTS-0.6B

- mlx-audio `generate(stream=True, streaming_interval≈0.32)`; sentence segmentation from LLM token stream; audio chunks (PCM 24kHz) over WS.
- ~250 ms jitter buffer before playback; cooperative cancellation (CancelScope-style) between chunks; stale-TTS flush + cancel target < 150 ms (hard correctness requirement, tested).
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

## 9. Runtime Constraints (M4 16GB + Metal)

- MLX models cannot run concurrently from multiple threads → single serialized inference worker for speech; VAD on CPU/ANE.
- Speech stack is host-native (oMLX/parakeet-mlx/mlx-audio run on host; Docker cannot reach Metal).
- Lifecycle: lazy load/unload, memory cap; one LLM (default = 4B `pramya-4b`; 9B deferred and never co-resident) + speech never over budget; oMLX handles LLM/embed/rerank lifecycle, voice service handles speech model lifecycle. Artifacts may coexist on disk — residency is a runtime decision under the memory policy, not a disk constraint.

## 10. Failure Handling

| Failure | Behavior |
|---|---|
| DeepSeek down | controlled provider error/retry (ADR-023 — no silent local-text fallback) |
| oMLX/ASR down | manual transcript mode |
| TTS down | text interviewer response |
| retrieval down | degraded interview mode (no context, logged) |
| WS dropped | reconnect + transcript re-sync |
| playback_complete never arrives | `voice_playback_timeout_seconds` guard opens LISTENING with `playback_confirmed=false` (diagnostic) |
| ASR/TTS/LLM timeout | per-node TimeoutPolicy; retry policy; actionable error |

Never "Something went wrong" — always actionable degraded state.

## 10. Voice Test Matrix (spec §42)

normal, fast, slow, long, short, silence, background noise, interruption, double interruption, pause, resume, stop, browser refresh, network loss, ASR failure, TTS failure, LLM timeout, LLM cancellation, partial transcript, late transcript, duplicate transcript, stale TTS → each has a test in Phase 9.

## 11. Performance Targets (measured then documented)

- TTFA (time-to-first-audio) and TTF-Transcript low on M4; immediate interruption (<~100ms perceived); no stale playback; bounded memory; no sustained uncontrolled thermal load. Exact thresholds recorded in DEPLOYMENT/TROUBLESHOOTING after measurement.

## 12. Physical-Microphone E2E — evidence (2026-08-13)

**Verdict: NOT_VERIFIED — physical microphone E2E blocked by the machine's
microphone state.** The fix's deterministic + controlled real-model evidence
is below; the acoustic acceptance could not be completed because the Mac's
physical mic delivered digital silence at the OS level.

What WAS verified with real models + a real headed browser (real playback
through speakers, real WebSocket, real backend):

1. `frontend/scripts/voice_e2e_real.mjs` (Playwright fake-device mic): Q1 TTS
   played (120 chunks / 1.15 MB, Qwen3-TTS), then `tts_stop → playback_complete
   → state:listening` — **speaker-integrity gating true**: listening only
   opened after the client's playback-confirmation handshake. Zero stale
   chunks after interrupt.
2. `frontend/scripts/voice_e2e_physical.mjs` (headed Chromium, REAL mic
   auto-granted, speakers): Q1 played aloud (128 chunks), `playback_complete`
   sent, `state:listening` opened, mic stream live (81 968 frames / ~7 MB),
   ASR invoked every ~2 s, candidate speech played through the speakers
   (afplay, loud) — **ASR returned 0 chars because the captured mic stream
   was digital silence**.
3. `frontend/scripts/mic_probe.mjs` (raw capture, AEC/NS/gain OFF): 9 s
   capture during speaker playback → PCM peak **0** — the browser is not
   filtering; the stream itself is silence.
4. OS-level probe (AVAudioRecorder, 3 s): **peak 0** — the physical mic
   delivers silence to any app in this environment (input volume 44, device
   present, TCC not inspectable). Not a Pramya defect.

Interpretation: the software boundaries all held (playback gating, server
mic gating, speaker attribution, barge-in, diagnostics). The remaining
unknown is purely acoustic: with a working physical mic, whether
room-captured speaker audio transcribes at acceptable quality. Re-run
`frontend/scripts/voice_e2e_physical.mjs` after confirming the mic captures
audio in System Settings (e.g. Voice Memos records speech).
