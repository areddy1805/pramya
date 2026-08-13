"""Voice pipeline (Phase 9): ASR/TTS clients + VoiceEngine state machine.

The voice stack talks to the local oMLX runtime (host-native MLX; Docker
cannot reach Metal) via its OpenAI-compatible /v1/audio/* endpoints. All
speech inference is serialized (single oMLX scheduler slot); the engine
never issues concurrent ASR/TTS calls.
"""
