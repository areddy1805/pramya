"""Streaming text segmenter (V1.1, R6).

Splits a stream of LLM text tokens into safe-to-speak sentence segments:
- emits only complete sentences (natural punctuation boundaries: . ! ? …),
- holds back a minimum phrase length so we never speak a fragment,
- hard-flushes at a maximum length at the last safe word boundary
  (never splits mid-word, never synthesizes punctuation fragments),
- ignores whitespace-only runs.

The segmenter is deterministic and pure — unit-testable without any
model/network dependency. It is the ONLY gate between the DeepSeek stream
and TTS: tokens are never synthesized individually.
"""

from __future__ import annotations

_BOUNDARIES = ".!?…。！？"
_SPACE_CHARS = " \t\n\r\f\v"


def _is_space(ch: str) -> bool:
    return ch in _SPACE_CHARS


class TextSegmenter:
    """Accumulate streamed tokens; yield complete speakable segments."""

    def __init__(
        self,
        *,
        min_chars: int = 60,
        max_chars: int = 200,
    ) -> None:
        self.min_chars = min_chars
        self.max_chars = max_chars
        self._buf = ""
        self._last_space = -1  # index of last safe word boundary in _buf

    def feed(self, chunk: str) -> list[str]:
        """Ingest a token chunk; return any complete segments now speakable."""
        if not chunk:
            return []
        self._buf += chunk
        segments: list[str] = []

        # Track the latest safe boundary.
        for i, ch in enumerate(self._buf):
            if _is_space(ch):
                self._last_space = i

        while True:
            if len(self._buf) < self.min_chars:
                break
            boundary = -1
            for i in range(len(self._buf) - 1, -1, -1):
                if self._buf[i] in _BOUNDARIES:
                    boundary = i
                    break
            if boundary >= 0 and len(self._buf[: boundary + 1]) >= self.min_chars:
                seg = self._buf[: boundary + 1].strip()
                self._buf = self._buf[boundary + 1 :]
                self._reset_boundaries()
                if seg:
                    segments.append(seg)
                continue
            # No sentence boundary yet: hard-flush at max length (word-safe).
            if len(self._buf) >= self.max_chars:
                cut = self._last_space if self._last_space > self.min_chars // 2 else -1
                if cut < 0:
                    # No usable space: flush whole buffer (better than stalling).
                    cut = len(self._buf)
                seg = self._buf[:cut].strip()
                self._buf = self._buf[cut:].lstrip()
                self._reset_boundaries()
                if seg:
                    segments.append(seg)
                continue
            break
        return segments

    def flush(self) -> str:
        """Return the remaining buffered text (called when the stream ends)."""
        out = self._buf.strip()
        self._buf = ""
        self._reset_boundaries()
        return out

    def _reset_boundaries(self) -> None:
        self._last_space = -1
        for i, ch in enumerate(self._buf):
            if _is_space(ch):
                self._last_space = i


__all__ = ["TextSegmenter"]
