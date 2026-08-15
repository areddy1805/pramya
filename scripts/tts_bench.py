#!/usr/bin/env python3
"""Standalone TTS benchmark: Qwen3-TTS (oMLX) vs Kyutai Pocket TTS.

Benchmark hygiene (ADR-025 follow-up): every metric has an exact boundary.

  COLD    process/model-start -> first PCM of the first utterance
  WARM    (model resident) TTS invocation -> first PCM
  STREAM  TTS invocation -> first streamed chunk (native streaming path)
  TOTAL   TTS invocation -> final PCM
  RTF     audio duration / wall time (>= 1.0 = faster than realtime)

Pocket path runs in-process (pocket_tts + torch); Qwen path is the
production boundary (HTTP POST /v1/audio/speech on the running oMLX).

Usage:
  /tmp/pocket-tts-venv/bin/python scripts/tts_bench.py --pocket [--quantize]
  /tmp/pocket-tts-venv/bin/python scripts/tts_bench.py --qwen [--omlx http://127.0.0.1:8000/v1]
  ... --both / --all
"""

from __future__ import annotations

import argparse
import asyncio
import json
import resource
import sys
import time
from typing import Any

TEXTS = {
    "SHORT": "Tell me about yourself.",
    "MEDIUM": (
        "That is a strong example. Now explain how you would design the system "
        "and what trade-offs you would consider."
    ),
    "LONG": (
        "Imagine you are designing a production AI system that must process "
        "thousands of requests per minute. Walk through the architecture, "
        "explain how you would handle failures, and describe how you would "
        "monitor quality and latency."
    ),
}

SEQ_UTTERANCES = [TEXTS["SHORT"], TEXTS["MEDIUM"], TEXTS["LONG"]]


def rss_bytes() -> int:
    ru = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    # macOS returns bytes; Linux returns KiB.
    return ru if sys.platform == "darwin" else ru * 1024


def cpu_seconds() -> float:
    ru = resource.getrusage(resource.RUSAGE_SELF)
    return ru.ru_utime + ru.ru_stime


def pcm16(chunk: Any) -> bytes:
    """float32 torch tensor [samples] -> PCM16 mono bytes."""
    import torch

    arr = torch.clamp(chunk, -1.0, 1.0)
    return (arr * 32767).to(torch.int16).numpy().tobytes()


# ---------------------------------------------------------------------------
# Pocket
# ---------------------------------------------------------------------------
def bench_pocket(quantize: bool) -> None:
    import torch  # noqa: F401  (import cost measured below is torch+pocket)

    from pocket_tts import TTSModel

    out: dict[str, Any] = {"provider": "pocket", "quantize": quantize}
    t0 = time.monotonic()
    model = TTSModel.load_model(quantize=quantize)
    load_s = round(time.monotonic() - t0, 3)
    out["load_model_s"] = load_s
    out["sample_rate"] = model.sample_rate
    out["rss_after_load_mb"] = round(rss_bytes() / 1e6, 1)

    t0 = time.monotonic()
    voice_state = model.get_state_for_audio_prompt("alba")
    out["voice_state_s"] = round(time.monotonic() - t0, 3)
    out["rss_after_voice_mb"] = round(rss_bytes() / 1e6, 1)

    # Warm: one short utterance, discarded.
    list(model.generate_audio_stream(voice_state, TEXTS["SHORT"]))
    out["warm_s"] = round(cpu_seconds(), 3)

    def run_one(text: str, label: str) -> dict[str, float]:
        chunks: list[bytes] = []
        t_first: float | None = None
        t_first_nonempty: float | None = None
        t0 = time.monotonic()
        for chunk in model.generate_audio_stream(voice_state, text):
            if t_first is None:
                t_first = time.monotonic()
            b = pcm16(chunk)
            if t_first_nonempty is None and len(b) >= 128:
                t_first_nonempty = time.monotonic()
            chunks.append(b)
        total = time.monotonic() - t0
        audio_s = sum(len(c) for c in chunks) / 2 / model.sample_rate
        assert t_first is not None
        return {
            f"{label}_first_pcm_ms": round((t_first - t0) * 1000, 1),
            f"{label}_first_nonempty_ms": round((t_first_nonempty - t0) * 1000, 1),
            f"{label}_total_ms": round(total * 1000, 1),
            f"{label}_audio_s": round(audio_s, 2),
            f"{label}_rtf": round(audio_s / total, 2),
            f"{label}_bytes": sum(len(c) for c in chunks),
        }

    # Cold: first measured utterance after warmup is still "warm model";
    # true cold = load included. Report load separately and cold first-PCM
    # as load + warm first utterance on a fresh process (see COLD section).
    for label, text in TEXTS.items():
        out.update(run_one(text, label))

    # Sequences.
    for n in (1, 5, 10, 20):
        seq: list[dict[str, float]] = []
        cpu0 = cpu_seconds()
        rss0 = rss_bytes()
        for i in range(n):
            seq.append(run_one(SEQ_UTTERANCES[i % 3], f"s{i}"))
        out[f"seq{n}_cpu_s"] = round(cpu_seconds() - cpu0, 3)
        out[f"seq{n}_rss_mb"] = round((rss_bytes() - rss0) / 1e6, 1)
        out[f"seq{n}_first_pcm_median_ms"] = round(
            sorted(s[f"s{i}_first_pcm_ms"] for i, s in enumerate(seq))[n // 2], 1
        )
        out[f"seq{n}_total_median_ms"] = round(
            sorted(s[f"s{i}_total_ms"] for i, s in enumerate(seq))[n // 2], 1
        )

    print(json.dumps(out, indent=2, sort_keys=True))


# ---------------------------------------------------------------------------
# Qwen3 via oMLX (production boundary)
# ---------------------------------------------------------------------------
async def bench_qwen(omlx_base: str) -> None:
    import psutil

    import httpx

    async with httpx.AsyncClient(timeout=300.0) as client:
        base = omlx_base.rstrip("/")
        model = "Qwen3-TTS-12Hz-0.6B-Base-MLX-4bit"
        out: dict[str, Any] = {"provider": "qwen3-omlx", "base": base, "model": model}

        async def synth(text: str) -> tuple[bytes, float]:
            t0 = time.monotonic()
            r = await client.post(
                f"{base}/audio/speech",
                json={"model": model, "input": text, "voice": "default", "response_format": "wav"},
            )
            r.raise_for_status()
            return r.content, time.monotonic() - t0

        # Warm the model (resident) before measurements; log cold load wall.
        t0 = time.monotonic()
        await synth("Okay.")
        out["warmup_s"] = round(time.monotonic() - t0, 3)

        # Identify oMLX process RSS.
        omlx_rss = None
        for p in psutil.process_iter(["name", "cmdline"]):
            try:
                cmd = " ".join(p.info["cmdline"] or [])
            except Exception:
                continue
            if "omlx" in (p.info["name"] or "").lower() or "omlx" in cmd:
                omlx_rss = p.memory_info().rss
                break
        out["omlx_rss_mb"] = round((omlx_rss or 0) / 1e6, 1)

        def wav_duration_ms(wav: bytes) -> int:
            import struct

            if len(wav) < 44 or wav[:4] != b"RIFF":
                return 0
            sr = struct.unpack("<I", wav[24:28])[0]
            nch = struct.unpack("<H", wav[22:24])[0]
            bits = struct.unpack("<H", wav[34:36])[0]
            data = len(wav) - 44
            return int(data / (sr * nch * (bits // 8)) * 1000)

        # Warm measured runs (full-WAV production boundary: first PCM == total).
        for label, text in TEXTS.items():
            wav, dt = await synth(text)
            out[f"{label}_first_pcm_ms"] = round(dt * 1000, 1)
            out[f"{label}_total_ms"] = round(dt * 1000, 1)
            out[f"{label}_audio_s"] = round(wav_duration_ms(wav) / 1000, 2)
            out[f"{label}_rtf"] = round((wav_duration_ms(wav) / 1000) / dt, 2)
            out[f"{label}_bytes"] = len(wav)

        # Native streaming TTFA (informational: replaced by per-segment
        # full-WAV in production; stream artifacts were the reason).
        for label, text in TEXTS.items():
            t0 = time.monotonic()
            first: float | None = None
            total = 0
            async with client.stream(
                "POST",
                f"{base}/audio/speech",
                json={
                    "model": model,
                    "input": text,
                    "voice": "default",
                    "response_format": "wav",
                    "stream": True,
                    "streaming_interval": 1.0,
                },
            ) as r:
                r.raise_for_status()
                async for raw in r.aiter_bytes():
                    if first is None and len(raw) > 44:
                        first = time.monotonic() - t0
                    total += len(raw)
            out[f"{label}_stream_first_chunk_ms"] = round((first or 0) * 1000, 1)
            out[f"{label}_stream_total_ms"] = round((time.monotonic() - t0) * 1000, 1)

        # Sequences (warm full-WAV).
        for n in (1, 5, 10, 20):
            times: list[float] = []
            for i in range(n):
                _, dt = await synth(SEQ_UTTERANCES[i % 3])
                times.append(dt)
            out[f"seq{n}_total_median_ms"] = round(sorted(times)[n // 2] * 1000, 1)

        print(json.dumps(out, indent=2, sort_keys=True))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pocket", action="store_true")
    ap.add_argument("--quantize", action="store_true")
    ap.add_argument("--qwen", action="store_true")
    ap.add_argument("--omlx", default="http://127.0.0.1:8000/v1")
    ap.add_argument("--all", action="store_true")
    args = ap.parse_args()

    if args.all:
        args.pocket = args.qwen = True
    if args.pocket:
        bench_pocket(args.quantize)
    if args.qwen:
        asyncio.run(bench_qwen(args.omlx))


if __name__ == "__main__":
    main()
