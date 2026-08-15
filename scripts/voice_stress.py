#!/usr/bin/env python3
"""Deterministic voice interview stress harness (Pocket TTS quality).

Exercises the REAL pipeline repeatedly without a human: real DeepSeek
question generation, real Pocket TTS, real Parakeet ASR, real WebSocket
transport. Candidate answers are prerecorded deterministic responses
(synthesized once via Pocket, downsampled to 16 kHz, plus trailing silence
for auto turn finalization).

Measures per interviewer turn (Phase 8):
  final->tts_start    candidate final transcript -> next question TTS start
  tts_start->first    TTS start -> first PCM frame over WS
  tts_start->stop     TTS start -> tts_stop (question speech window)
  audio_s             total PCM relayed (real duration)
  stale               frames received after an interrupt

Usage (from backend/):  uv run python ../scripts/voice_stress.py [turns]
Requires: backend on :8001, oMLX on :8000 (Parakeet), TTS provider default.
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
import wave
from pathlib import Path

import httpx
import numpy as np
import torch
import websockets
from pocket_tts import TTSModel

API = "http://127.0.0.1:8001/api/v1"
WS = "ws://127.0.0.1:8001/api/v1/ws/voice"
USER = 1
DEFAULT_TURNS = 10
INTERRUPT_AFTER_TURN = 5  # turn whose next question gets interrupted

ANSWERS = [
    "I led a small team of four engineers.",
    "We rebuilt the checkout service using event sourcing and a Kafka log as the source of truth, then added automated failover so a database outage no longer took the whole flow down.",
    "Not sure. I guess we would try harder.",
    "I would separate reads from writes and put a cache in front of the read path.",
    "We monitored p95 latency and alert thresholds.",
    "For exactly-once processing I would use an idempotency key on every message and deduplicate at the consumer.",
    "Can you repeat the question?",
    "We used circuit breakers and bulkheads so one failing service could not cascade.",
    "I would start by writing a load test to find the bottleneck.",
    "My main takeaway is that reliability comes from observability first.",
]


def synth_candidate_pcm(text: str, sr_out: int = 16000) -> bytes:
    """Pocket-synthesize a deterministic candidate answer at 16 kHz PCM16."""
    model = TTSModel.load_model()
    vs = model.get_state_for_audio_prompt("alba")
    audio = torch.cat(list(model.generate_audio_stream(vs, text))).numpy()
    n = int(len(audio) * sr_out / model.sample_rate)
    idx = np.linspace(0, len(audio) - 1, n).astype(int)
    pcm = (np.clip(audio[idx], -1, 1) * 32767).astype(np.int16)
    silence = np.zeros(int(sr_out * 2.5), dtype=np.int16)
    # trailing silence AFTER speech so the engine's silence watchdog sees a
    # low-energy window and auto-finalizes the turn (real mic behavior).
    return np.concatenate([silence, pcm, silence]).tobytes()


async def main() -> None:
    turns_n = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_TURNS
    answers = [synth_candidate_pcm(a) for a in ANSWERS]
    print(f"candidate responses synthesized: {[len(a) for a in answers]} bytes")

    async with httpx.AsyncClient(timeout=120) as c:
        r = await c.post(
            f"{API}/interviews", json={"user_id": USER, "kind": "general", "mode": "voice"}
        )
        r.raise_for_status()
        sid = r.json()["id"]
    print(f"session {sid}, turns={turns_n}, interrupt after turn {INTERRUPT_AFTER_TURN}")

    t0 = time.monotonic()
    rows: list[dict[str, float]] = []

    async def q_phase() -> tuple[int, list[float]]:
        """Read the next question's TTS; returns (generation, per-turn ms)."""
        gen = None
        t_start = t_first = t_stop = None
        audio_bytes = 0
        async with asyncio.timeout(90):
            while True:
                msg = await ws.recv()
                if isinstance(msg, bytes):
                    audio_bytes += len(msg)
                    if t_first is None and t_start is not None:
                        t_first = time.monotonic() - t0
                    continue
                d = json.loads(msg)
                e = d.get("type")
                if e == "tts_start":
                    t_start = time.monotonic() - t0
                    gen = d.get("generation")
                elif e == "tts_stop":
                    t_stop = time.monotonic() - t0
                    break
        assert t_start is not None and t_stop is not None
        return gen, [t_start, t_first if t_first is not None else t_stop, t_stop, audio_bytes]

    async def to_listening(gen: int) -> None:
        await ws.send(json.dumps({"type": "playback_complete", "generation": gen}))
        async with asyncio.timeout(5):
            while True:
                msg = await ws.recv()
                if isinstance(msg, bytes):
                    continue
                d = json.loads(msg)
                if d.get("type") == "state" and d.get("state") == "listening":
                    return

    async with websockets.connect(f"{WS}/{sid}?user_id={USER}") as ws:
        gen, q1 = await q_phase()
        rows.append({"q": 0, "final->tts_start": 0.0, "tts_start->first": q1[1] - q1[0], "tts_start->stop": q1[2] - q1[0], "audio_s": q1[3] / 2 / 24000})
        print(f"Q0: first_audio={q1[1]-q1[0]:.2f}s stop={q1[2]-q1[0]:.2f}s audio={q1[3]/2/24000:.1f}s")
        await to_listening(gen)

        total_stale = 0
        for i in range(turns_n):
            pcm = answers[i % len(answers)]
            for j in range(0, len(pcm), 6400):
                await ws.send(pcm[j : j + 6400])
                await asyncio.sleep(0.012)

            # final transcript -> next question audio
            final_at: float | None = None
            gen = None
            t_start = t_first = t_stop = None
            audio_bytes = 0
            interrupted = False
            async with asyncio.timeout(120):
                while True:
                    msg = await ws.recv()
                    if isinstance(msg, bytes):
                        audio_bytes += len(msg)
                        if t_first is None and t_start is not None:
                            t_first = time.monotonic() - t0
                            if i + 1 == INTERRUPT_AFTER_TURN:
                                # interrupt mid-speech (after first audio)
                                await ws.send(json.dumps({"type": "interrupt"}))
                        continue
                    d = json.loads(msg)
                    e = d.get("type")
                    if e == "final_transcript":
                        final_at = time.monotonic() - t0
                    elif e == "tts_start":
                        t_start = time.monotonic() - t0
                        gen = d.get("generation")
                    elif e == "tts_stop":
                        t_stop = time.monotonic() - t0
                        break
                    elif e == "state" and d.get("state") == "interrupted":
                        # interrupted question: no tts_stop; already listening
                        interrupted = True
                        t_stop = t_first or (time.monotonic() - t0)
                        break

            # stale frames after interrupt
            stale = 0
            if i + 1 == INTERRUPT_AFTER_TURN:
                try:
                    async with asyncio.timeout(2):
                        while True:
                            msg = await ws.recv()
                            if isinstance(msg, bytes):
                                stale += 1
                except TimeoutError:
                    pass
                total_stale += stale

            rows.append({
                "q": i + 1,
                "final->tts_start": (t_start - final_at) if (final_at and t_start) else -1,
                "tts_start->first": (t_first - t_start) if (t_first and t_start) else -1,
                "tts_start->stop": (t_stop - t_start) if (t_start and t_stop) else -1,
                "audio_s": audio_bytes / 2 / 24000,
            })
            print(
                f"turn {i+1}: final->tts_start={rows[-1]['final->tts_start']:.2f}s "
                f"tts_start->first={rows[-1]['tts_start->first']:.2f}s "
                f"stop={rows[-1]['tts_start->stop']:.2f}s audio={rows[-1]['audio_s']:.1f}s"
            )
            if gen is not None and not interrupted:
                await to_listening(gen)

        await ws.send(json.dumps({"type": "stop"}))

    print("\nSUMMARY")
    fs = [r["final->tts_start"] for r in rows[1:] if r["final->tts_start"] > 0]
    fa = [r["tts_start->first"] for r in rows[1:] if r["tts_start->first"] > 0]
    print(f"final->tts_start: median {sorted(fs)[len(fs)//2]:.2f}s min {min(fs):.2f}s max {max(fs):.2f}s")
    print(f"tts_start->first: median {sorted(fa)[len(fa)//2]:.2f}s min {min(fa):.2f}s max {max(fa):.2f}s")
    print(f"stale frames after interrupt: {total_stale} (expect 0)")
    print(f"total turns: {len(rows)-1}")


if __name__ == "__main__":
    asyncio.run(main())
