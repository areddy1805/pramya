"""Interviewer voice identity (V1.1, R2).

The interviewer has ONE deterministic professional voice per configuration —
never a random choice per TTS generation. Qwen3-TTS-12Hz-0.6B is a
single-speaker model, so the provider-level voice name maps to its only
voice ("default"); the voice_id/name/style live in configuration so a future
multi-voice provider (e.g. Pocket TTS) plugs in without changing callers.

Resolution is deterministic: the profile is resolved once per session by the
engine (voice engine owns it), and every TTS generation in that session uses
the same voice. There is intentionally no random.choice anywhere in this
module or the TTS call path.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.config import Settings


@dataclass(frozen=True)
class InterviewerVoiceProfile:
    """Resolved interviewer voice for one session (immutable)."""

    voice_id: str
    provider: str
    provider_voice: str
    name: str
    language: str
    style: str
    enabled: bool = True

    def as_dict(self) -> dict[str, object]:
        """Diagnostics payload (voice visible in observability, never random)."""
        return {
            "voice_id": self.voice_id,
            "provider": self.provider,
            "provider_voice": self.provider_voice,
            "name": self.name,
            "language": self.language,
            "style": self.style,
            "enabled": self.enabled,
        }


def resolve_interviewer_voice(settings: Settings) -> InterviewerVoiceProfile:
    """Resolve the configured interviewer voice (deterministic, per-session).

    Maps the configured voice_id to the active provider's concrete voice:
    oMLX/Qwen3-TTS exposes a single speaker ("default"). Unknown voice_ids
    fall back to that single voice with the configured identity metadata —
    the identity (voice_id/name/style) is preserved for diagnostics even
    when the provider has one voice.
    """
    voice_id = (settings.interviewer_voice_id or "professional_female_01").strip()
    provider_voice = "default"  # Qwen3-TTS single-speaker mapping
    return InterviewerVoiceProfile(
        voice_id=voice_id,
        provider="omlx",
        provider_voice=provider_voice,
        name=settings.interviewer_voice_name or "Professional Female 01",
        language="en-US",
        style=settings.interviewer_voice_style or "professional",
    )


__all__ = ["InterviewerVoiceProfile", "resolve_interviewer_voice"]
