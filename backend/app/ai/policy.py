"""Deterministic task-class model policy (ADR-004, ADR-020, AI_ARCHITECTURE §2).

Canonical model roles (finalized 2026-08):
- Qwen3.5-4B (oMLX alias `pramya-4b`) = primary local workhorse (default,
  thinking off, majority of workload).
- deepseek-v4-flash = escalation only (never default; reserved for workloads
  that materially benefit from stronger reasoning/capability/context).
- BGE-M3 = embeddings; Qwen3-Reranker-0.6B = reranking.
- Qwen3.5-9B is DEFERRED: absent from this module by design.

Routing decision flow: 4B local first -> task-class decision -> can 4B handle
this adequately? yes -> 4B; no -> deepseek-v4-flash. No "complexity = cloud"
heuristic beyond this table. Strongest model is never the default.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ProviderKind(StrEnum):
    OMLX = "omlx"
    DEEPSEEK = "deepseek"


class TaskClass(StrEnum):
    """Task classes that application code routes on (initial policy)."""

    # Local workhorse (pramya-4b, thinking off)
    ROUTINE_GENERATION = "routine_generation"
    EXTRACTION = "extraction"
    CLASSIFICATION = "classification"
    METADATA = "metadata"
    STRUCTURED_GENERATION = "structured_generation"
    SEMANTIC_TASK = "semantic_task"
    INTERVIEW_CONTENT_GENERATION = "interview_content_generation"
    ORDINARY_EVALUATION = "ordinary_evaluation"
    ANALYSIS = "analysis"  # transcript/debrief analysis (Phase 10)
    # Escalation (deepseek-v4-flash)
    DEEP_EVALUATION = "deep_evaluation"
    COMPLEX_REASONING = "complex_reasoning"
    ADAPTIVE_REASONING = "adaptive_reasoning"
    SYSTEM_DESIGN = "system_design"
    FINAL_SYNTHESIS = "final_synthesis"
    DIFFICULT_FOLLOWUP = "difficult_followup"
    # Retrieval capabilities
    EMBEDDING = "embedding"
    RERANKING = "reranking"


class ModelId(StrEnum):
    """Canonical model IDs (docs/MODEL_CATALOG.md). No 9B entry — deferred."""

    PRAMYA_4B = "pramya-4b"  # Qwen3.5-4B via oMLX
    DEEPSEEK_V4_FLASH = "deepseek-v4-flash"
    BGE_M3 = "bge-m3-mlx-4bit"  # embeddings via oMLX
    QWEN3_RERANKER_0_6B = "Qwen3-Reranker-0.6B-4bit"  # reranking via oMLX


@dataclass(frozen=True)
class ModelSpec:
    """A model's canonical role."""

    id: str
    provider: ProviderKind
    # Explicit thinking policy. For pramya-4b this MUST stay off — never rely
    # on the model's default thinking behavior (catalog §2.2, ADR-020).
    thinking: bool
    capability: str  # "generate" | "embed" | "rerank"


# Canonical model registry. The sole source of model facts for routing.
MODEL_REGISTRY: dict[ModelId, ModelSpec] = {
    ModelId.PRAMYA_4B: ModelSpec(
        id=ModelId.PRAMYA_4B,
        provider=ProviderKind.OMLX,
        thinking=False,
        capability="generate",
    ),
    ModelId.DEEPSEEK_V4_FLASH: ModelSpec(
        id=ModelId.DEEPSEEK_V4_FLASH,
        provider=ProviderKind.DEEPSEEK,
        thinking=True,
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
    # capabilities without a degradation path (embeddings/rerank: caller
    # degrades, e.g. FTS-only retrieval / skip rerank).
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


# Initial task policy table (AI_ARCHITECTURE §2). 4B local first; escalation
# only for task classes that materially benefit from stronger reasoning.
TASK_POLICIES: dict[TaskClass, TaskPolicy] = {
    # --- Local workhorse (pramya-4b, thinking off) ---
    TaskClass.ROUTINE_GENERATION: _policy(
        TaskClass.ROUTINE_GENERATION, ModelId.PRAMYA_4B, ModelId.DEEPSEEK_V4_FLASH
    ),
    TaskClass.EXTRACTION: _policy(
        TaskClass.EXTRACTION, ModelId.PRAMYA_4B, ModelId.DEEPSEEK_V4_FLASH
    ),
    TaskClass.CLASSIFICATION: _policy(
        TaskClass.CLASSIFICATION, ModelId.PRAMYA_4B, ModelId.DEEPSEEK_V4_FLASH
    ),
    TaskClass.METADATA: _policy(TaskClass.METADATA, ModelId.PRAMYA_4B, ModelId.DEEPSEEK_V4_FLASH),
    TaskClass.STRUCTURED_GENERATION: _policy(
        TaskClass.STRUCTURED_GENERATION, ModelId.PRAMYA_4B, ModelId.DEEPSEEK_V4_FLASH
    ),
    TaskClass.SEMANTIC_TASK: _policy(
        TaskClass.SEMANTIC_TASK, ModelId.PRAMYA_4B, ModelId.DEEPSEEK_V4_FLASH
    ),
    TaskClass.INTERVIEW_CONTENT_GENERATION: _policy(
        TaskClass.INTERVIEW_CONTENT_GENERATION,
        ModelId.PRAMYA_4B,
        ModelId.DEEPSEEK_V4_FLASH,
    ),
    TaskClass.ORDINARY_EVALUATION: _policy(
        TaskClass.ORDINARY_EVALUATION, ModelId.PRAMYA_4B, ModelId.DEEPSEEK_V4_FLASH
    ),
    TaskClass.ANALYSIS: _policy(TaskClass.ANALYSIS, ModelId.PRAMYA_4B, ModelId.DEEPSEEK_V4_FLASH),
    # --- Escalation (deepseek-v4-flash; thinking on by default) ---
    TaskClass.DEEP_EVALUATION: _policy(
        TaskClass.DEEP_EVALUATION, ModelId.DEEPSEEK_V4_FLASH, ModelId.PRAMYA_4B
    ),
    TaskClass.COMPLEX_REASONING: _policy(
        TaskClass.COMPLEX_REASONING, ModelId.DEEPSEEK_V4_FLASH, ModelId.PRAMYA_4B
    ),
    TaskClass.ADAPTIVE_REASONING: _policy(
        TaskClass.ADAPTIVE_REASONING, ModelId.DEEPSEEK_V4_FLASH, ModelId.PRAMYA_4B
    ),
    TaskClass.SYSTEM_DESIGN: _policy(
        TaskClass.SYSTEM_DESIGN, ModelId.DEEPSEEK_V4_FLASH, ModelId.PRAMYA_4B
    ),
    TaskClass.FINAL_SYNTHESIS: _policy(
        TaskClass.FINAL_SYNTHESIS, ModelId.DEEPSEEK_V4_FLASH, ModelId.PRAMYA_4B
    ),
    TaskClass.DIFFICULT_FOLLOWUP: _policy(
        TaskClass.DIFFICULT_FOLLOWUP, ModelId.DEEPSEEK_V4_FLASH, ModelId.PRAMYA_4B
    ),
    # --- Retrieval capabilities (no fallback: caller degrades) ---
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
