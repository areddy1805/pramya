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


_META_PREFIXES = (
    "TYPE:",
    "DIFFICULTY:",
    "RATIONALE:",
    "RATIONAL:",
    "TARGET:",
    "HINTS:",
    # Productization metadata emitted after the QUESTION section — must never
    # reach TTS. Keep in sync with generation.QUESTION_META_PREFIXES.
    "CATEGORY:",
    "SOURCE:",
    "SOURCE_REF:",
)


class QuestionStreamExtractor:
    """Presentation boundary (V1.1 P0): extracts ONLY the user-facing
    interviewer question text from the streamed model output.

    The model streams the plain-text format::

        QUESTION: <spoken question, 1-3 sentences>
        CATEGORY: <taxonomy category>
        SOURCE: resume | jd | followup | ...
        SOURCE_REF: <grounded entity>
        TYPE: ...
        DIFFICULTY: ...
        RATIONALE: ...
        TARGET: ...
        HINTS:
        - ...

    The QUESTION: section is the TTS script; everything after the first
    metadata key line is WORKFLOW DATA (state/UI/persistence) and must
    never reach TTS. This extractor streams question-text tokens only —
    header stripped, metadata cut — so the segmenter/TTS never speak
    "TYPE: technical", "CATEGORY: system_scaling", or a JSON
    serialization of the question.
    """

    def __init__(self) -> None:
        self._buf = ""
        self._in_question = False
        self._done = False

    def feed(self, token: str) -> list[str]:
        """Return question-text tokens (header stripped, metadata cut)."""
        if self._done or not token:
            return []
        self._buf += token
        out: list[str] = []
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
            out.extend(self._process_line(line))
            if self._done:
                break
        return out

    def flush(self) -> list[str]:
        """Process the remaining partial line at end-of-stream."""
        if self._done or not self._buf:
            return []
        line = self._buf
        self._buf = ""
        return self._process_line(line)

    def _process_line(self, line: str) -> list[str]:
        stripped = line.strip()
        upper = stripped.upper()
        if upper.startswith(_META_PREFIXES):
            # Metadata section reached: the question is complete. Cut here.
            self._done = True
            return []
        if upper.startswith("QUESTION:"):
            self._in_question = True
            rest = line[len("QUESTION:") :]
            return [rest] if rest.strip() else []
        if not self._in_question:
            # Model deviated (no QUESTION: header): emit up to the first
            # metadata line anyway (resilient, still never metadata).
            return [line]
        # Continuation line of a multi-line question.
        return [line]
