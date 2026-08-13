"""Deterministic task-class model policy (ADR-004, ADR-020, ADR-023).

Canonical model roles (finalized 2026-08, ADR-023 — production architecture):
- deepseek-v4-flash = the ONLY production text LLM (all textual/LLM
  inference; never routed to a local text model).
- Local oMLX = audio only (Parakeet-TDT ASR, Qwen3-ASR, Qwen3-TTS) plus
  retrieval capabilities that DeepSeek does not provide (BGE-M3 embeddings,
  Qwen3-Reranker-0.6B reranking).
- Local text-generation models (pramya-4b / qwen3.5-4b / qwen2.5-coder-7b)
  are PROHIBITED in the production inference path.
- Qwen3.5-9B is DEFERRED: absent from this module by design.

Fallback semantics: text tasks have NO fallback chain. A DeepSeek failure
produces a controlled ProviderConnectionError (retry at the caller) — it is
never silently degraded to a local text model. Retrieval capabilities keep
no fallback either (caller degrades: FTS-only / skip rerank).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ProviderKind(StrEnum):
    OMLX = "omlx"
    DEEPSEEK = "deepseek"


class TaskClass(StrEnum):
    """Task classes that application code routes on (initial policy)."""

    # Text generation (deepseek-v4-flash)
    ROUTINE_GENERATION = "routine_generation"
    EXTRACTION = "extraction"
    CLASSIFICATION = "classification"
    METADATA = "metadata"
    STRUCTURED_GENERATION = "structured_generation"
    SEMANTIC_TASK = "semantic_task"
    INTERVIEW_CONTENT_GENERATION = "interview_content_generation"
    ORDINARY_EVALUATION = "ordinary_evaluation"
    ANALYSIS = "analysis"  # transcript/debrief analysis (Phase 10)
    DEEP_EVALUATION = "deep_evaluation"
    COMPLEX_REASONING = "complex_reasoning"
    ADAPTIVE_REASONING = "adaptive_reasoning"
    SYSTEM_DESIGN = "system_design"
    FINAL_SYNTHESIS = "final_synthesis"
    DIFFICULT_FOLLOWUP = "difficult_followup"
    # Retrieval capabilities (local oMLX — no DeepSeek equivalent)
    EMBEDDING = "embedding"
    RERANKING = "reranking"


class ModelId(StrEnum):
    """Canonical model IDs (docs/MODEL_CATALOG.md). No local text models.

    Only production models are registered: deepseek-v4-flash for text,
    BGE-M3 embeddings + Qwen3-Reranker reranking locally, and the audio
    models (registered under oMLX audio; referenced by the voice engine).
    """

    DEEPSEEK_V4_FLASH = "deepseek-v4-flash"
    BGE_M3 = "bge-m3-mlx-4bit"  # embeddings via oMLX
    QWEN3_RERANKER_0_6B = "Qwen3-Reranker-0.6B-4bit"  # reranking via oMLX


# Audio model IDs (not routed through the InferenceRouter; the voice engine
# calls the local oMLX /v1/audio/* endpoints directly — see app/voice/).
AUDIO_MODEL_IDS: tuple[str, ...] = (
    "Qwen3-ASR-1.7B-4bit",
    "parakeet-tdt-0.6b-v3-int8",
    "Qwen3-TTS-12Hz-0.6B-Base-MLX-4bit",
)


@dataclass(frozen=True)
class ModelSpec:
    """A model's canonical role."""

    id: str
    provider: ProviderKind
    # Explicit thinking policy. Production default is thinking OFF (cheap +
    # fast); callers may deliberately request thinking per request.
    thinking: bool
    capability: str  # "generate" | "embed" | "rerank"


# Canonical model registry. The sole source of model facts for routing.
MODEL_REGISTRY: dict[ModelId, ModelSpec] = {
    ModelId.DEEPSEEK_V4_FLASH: ModelSpec(
        id=ModelId.DEEPSEEK_V4_FLASH,
        provider=ProviderKind.DEEPSEEK,
        thinking=False,  # cheap + fast by default; reasoning only on request
        capability="generate",
    ),
    ModelId.BGE_M3: ModelSpec(
        id=ModelId.BGE_M3,
        provider=ProviderKind.OMLX,
        thinking=False,
        capability="embed",
    ),
    ModelId.QWEN3_RERANKER_0_6B: ModelSpec(
        id=ModelId.QWEN3_RERANKER_0_6B,
        provider=ProviderKind.OMLX,
        thinking=False,
        capability="rerank",
    ),
}


@dataclass(frozen=True)
class TaskPolicy:
    """Routing decision for one task class."""

    task: TaskClass
    model: ModelId
    # Fallback chain (primary first, then fallbacks in order). Empty for
    # text tasks (DeepSeek failure is explicit, never silently local) and
    # for capabilities without a degradation path (embeddings/rerank).
    fallback_models: tuple[ModelId, ...] = ()
    # Fallback is degraded (quality/user-visible state) — logged on decision.
    fallback_degraded: bool = False


def _policy(task: TaskClass, model: ModelId, *fallback: ModelId) -> TaskPolicy:
    return TaskPolicy(
        task=task,
        model=model,
        fallback_models=tuple(fallback),
        fallback_degraded=bool(fallback),
    )


# Task policy table (AI_ARCHITECTURE §2). Every text task routes to
# deepseek-v4-flash with NO fallback (controlled error path). Embedding and
# reranking stay local (no DeepSeek equivalent; caller degrades).
TASK_POLICIES: dict[TaskClass, TaskPolicy] = {
    # --- Text generation (deepseek-v4-flash; no fallback) ---
    TaskClass.ROUTINE_GENERATION: _policy(TaskClass.ROUTINE_GENERATION, ModelId.DEEPSEEK_V4_FLASH),
    TaskClass.EXTRACTION: _policy(TaskClass.EXTRACTION, ModelId.DEEPSEEK_V4_FLASH),
    TaskClass.CLASSIFICATION: _policy(TaskClass.CLASSIFICATION, ModelId.DEEPSEEK_V4_FLASH),
    TaskClass.METADATA: _policy(TaskClass.METADATA, ModelId.DEEPSEEK_V4_FLASH),
    TaskClass.STRUCTURED_GENERATION: _policy(
        TaskClass.STRUCTURED_GENERATION, ModelId.DEEPSEEK_V4_FLASH
    ),
    TaskClass.SEMANTIC_TASK: _policy(TaskClass.SEMANTIC_TASK, ModelId.DEEPSEEK_V4_FLASH),
    TaskClass.INTERVIEW_CONTENT_GENERATION: _policy(
        TaskClass.INTERVIEW_CONTENT_GENERATION, ModelId.DEEPSEEK_V4_FLASH
    ),
    TaskClass.ORDINARY_EVALUATION: _policy(
        TaskClass.ORDINARY_EVALUATION, ModelId.DEEPSEEK_V4_FLASH
    ),
    TaskClass.ANALYSIS: _policy(TaskClass.ANALYSIS, ModelId.DEEPSEEK_V4_FLASH),
    TaskClass.DEEP_EVALUATION: _policy(TaskClass.DEEP_EVALUATION, ModelId.DEEPSEEK_V4_FLASH),
    TaskClass.COMPLEX_REASONING: _policy(TaskClass.COMPLEX_REASONING, ModelId.DEEPSEEK_V4_FLASH),
    TaskClass.ADAPTIVE_REASONING: _policy(TaskClass.ADAPTIVE_REASONING, ModelId.DEEPSEEK_V4_FLASH),
    TaskClass.SYSTEM_DESIGN: _policy(TaskClass.SYSTEM_DESIGN, ModelId.DEEPSEEK_V4_FLASH),
    TaskClass.FINAL_SYNTHESIS: _policy(TaskClass.FINAL_SYNTHESIS, ModelId.DEEPSEEK_V4_FLASH),
    TaskClass.DIFFICULT_FOLLOWUP: _policy(TaskClass.DIFFICULT_FOLLOWUP, ModelId.DEEPSEEK_V4_FLASH),
    # --- Retrieval capabilities (local oMLX; no fallback) ---
    TaskClass.EMBEDDING: _policy(TaskClass.EMBEDDING, ModelId.BGE_M3),
    TaskClass.RERANKING: _policy(TaskClass.RERANKING, ModelId.QWEN3_RERANKER_0_6B),
}


class TaskPolicyTable:
    """Read-only view over TASK_POLICIES; single source for routing."""

    def __init__(self, policies: dict[TaskClass, TaskPolicy] | None = None) -> None:
        self._policies: dict[TaskClass, TaskPolicy] = dict(policies or TASK_POLICIES)

    def for_task(self, task: TaskClass) -> TaskPolicy:
        try:
            return self._policies[task]
        except KeyError as exc:
            raise ValueError(f"no task policy for {task!r}") from exc

    def model_spec(self, model: ModelId) -> ModelSpec:
        try:
            return MODEL_REGISTRY[model]
        except KeyError as exc:
            raise ValueError(f"model {model!r} not in registry") from exc

    def as_dict(self) -> dict[str, dict[str, object]]:
        return {
            p.task.value: {
                "model": p.model.value,
                "fallbacks": [m.value for m in p.fallback_models],
            }
            for p in self._policies.values()
        }
