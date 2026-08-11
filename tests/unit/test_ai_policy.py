"""Unit tests: task-class policy table (ADR-004/ADR-020, AI_ARCHITECTURE §2)."""

from __future__ import annotations

import pytest

from app.ai.policy import (
    MODEL_REGISTRY,
    TASK_POLICIES,
    ModelId,
    ProviderKind,
    TaskClass,
    TaskPolicyTable,
)

# Expected mapping from AI_ARCHITECTURE §2 (authoritative).
LOCAL_WORKHORSE_TASKS = [
    TaskClass.ROUTINE_GENERATION,
    TaskClass.EXTRACTION,
    TaskClass.CLASSIFICATION,
    TaskClass.METADATA,
    TaskClass.STRUCTURED_GENERATION,
    TaskClass.SEMANTIC_TASK,
    TaskClass.INTERVIEW_CONTENT_GENERATION,
    TaskClass.ORDINARY_EVALUATION,
]
ESCALATION_TASKS = [
    TaskClass.DEEP_EVALUATION,
    TaskClass.COMPLEX_REASONING,
    TaskClass.ADAPTIVE_REASONING,
    TaskClass.SYSTEM_DESIGN,
    TaskClass.FINAL_SYNTHESIS,
    TaskClass.DIFFICULT_FOLLOWUP,
]

TABLE = TaskPolicyTable()


def test_local_workhorse_tasks_route_to_pramya_4b() -> None:
    for task in LOCAL_WORKHORSE_TASKS:
        policy = TABLE.for_task(task)
        assert policy.model == ModelId.PRAMYA_4B, task


def test_local_workhorse_thinking_off() -> None:
    spec = TABLE.model_spec(ModelId.PRAMYA_4B)
    assert spec.thinking is False  # explicit thinking-off (catalog §2.2)
    for task in LOCAL_WORKHORSE_TASKS:
        assert TABLE.for_task(task).model == ModelId.PRAMYA_4B


def test_escalation_tasks_route_to_deepseek_only() -> None:
    for task in ESCALATION_TASKS:
        policy = TABLE.for_task(task)
        assert policy.model == ModelId.DEEPSEEK_V4_FLASH, task


def test_escalation_model_is_paid_cloud_flagged() -> None:
    spec = TABLE.model_spec(ModelId.DEEPSEEK_V4_FLASH)
    assert spec.provider == ProviderKind.DEEPSEEK


def test_embedding_and_rerank_capabilities() -> None:
    assert TABLE.for_task(TaskClass.EMBEDDING).model == ModelId.BGE_M3
    assert TABLE.for_task(TaskClass.RERANKING).model == ModelId.QWEN3_RERANKER_0_6B
    assert TABLE.model_spec(ModelId.BGE_M3).capability == "embed"
    assert TABLE.model_spec(ModelId.QWEN3_RERANKER_0_6B).capability == "rerank"


def test_fallback_chains() -> None:
    # 4B unavailable -> escalate to deepseek (degraded)
    for task in LOCAL_WORKHORSE_TASKS:
        assert TABLE.for_task(task).fallback_models == (ModelId.DEEPSEEK_V4_FLASH,)
    # DeepSeek unavailable -> local 4B fallback (degraded)
    for task in ESCALATION_TASKS:
        assert TABLE.for_task(task).fallback_models == (ModelId.PRAMYA_4B,)
    # Embedding/rerank: no fallback (caller degrades: FTS-only / skip rerank)
    assert TABLE.for_task(TaskClass.EMBEDDING).fallback_models == ()
    assert TABLE.for_task(TaskClass.RERANKING).fallback_models == ()


def test_no_deferred_9b_dependency() -> None:
    for model in MODEL_REGISTRY:
        assert "9b" not in model.value.lower()
    for policy in TASK_POLICIES.values():
        assert "9b" not in policy.model.value.lower()
        assert all("9b" not in m.value.lower() for m in policy.fallback_models)


def test_every_task_class_has_policy() -> None:
    assert set(TASK_POLICIES) == set(TaskClass)


def test_unknown_task_rejected() -> None:
    with pytest.raises(ValueError):
        TABLE.for_task(TaskClass("does_not_exist"))  # type: ignore[arg-type]
