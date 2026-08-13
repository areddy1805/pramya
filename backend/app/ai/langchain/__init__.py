"""LangChain integration (ADR-001 boundary, Phase B realignment).

LangChain is the AI composition layer: prompt templates, runnable
pipelines, output parsing, and structured output. Every model invocation
still routes through the InferenceRouter (ADR-004/ADR-023) — DeepSeek stays
the sole production text LLM; oMLX stays audio+retrieval only.

The deterministic helpers under ``app.ai.structured`` remain the
reference/fallback implementation; production paths execute these LangChain
pipelines.
"""
