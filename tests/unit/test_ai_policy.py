"""Unit tests: task-class policy table (ADR-004/ADR-020/ADR-023).

ADR-023 production topology: TEXT -> DeepSeek (deepseek-v4-flash, no
fallback), AUDIO -> local oMLX (ASR/TTS), retrieval (embed/rerank) stays
local. No local text-generation model may appear in the routing path.
"""

from __future__ import annotations

import pytest

from app.ai.policy import (
    AUDIO_MODEL_IDS,
    MODEL_REGISTRY,
    TASK_POLICIES,
    ModelId,
    ProviderKind,
    TaskClass,
    TaskPolicyTable,
)

# All text task classes (AI_ARCHITECTURE §2).
TEXT_TASKS = [
    TaskClass.ROUTINE_GENERATION,
    TaskClass.EXTRACTION,
    TaskClass.CLASSIFICATION,
    TaskClass.METADATA,
    TaskClass.STRUCTURED_GENERATION,
    TaskClass.SEMANTIC_TASK,
    TaskClass.INTERVIEW_CONTENT_GENERATION,
    TaskClass.ORDINARY_EVALUATION,
    TaskClass.ANALYSIS,
    TaskClass.DEEP_EVALUATION,
    TaskClass.COMPLEX_REASONING,
    TaskClass.ADAPTIVE_REASONING,
    TaskClass.SYSTEM_DESIGN,
    TaskClass.FINAL_SYNTHESIS,
    TaskClass.DIFFICULT_FOLLOWUP,
]

TABLE = TaskPolicyTable()


def test_all_text_tasks_route_to_deepseek() -> None:
    for task in TEXT_TASKS:
        policy = TABLE.for_task(task)
        assert policy.model == ModelId.DEEPSEEK_V4_FLASH, task


def test_no_text_fallback_chain() -> None:
    # A DeepSeek failure must surface as a controlled error — never a silent
    # local text fallback (ADR-023).
    for task in TEXT_TASKS:
        assert TABLE.for_task(task).fallback_models == (), task


def test_deepseek_is_cloud_text_provider() -> None:
    spec = TABLE.model_spec(ModelId.DEEPSEEK_V4_FLASH)
    assert spec.provider == ProviderKind.DEEPSEEK
    assert spec.capability == "generate"


def test_no_local_text_model_in_registry() -> None:
    # PRAMYA_4B / qwen3.5-4b / qwen2.5-coder-7b must be absent from the
    # router registry. Retrieval models (Qwen3-Reranker) are allowed.
    prohibited = ("pramya", "qwen3.5-4b", "qwen2.5-coder", "coder-7b")
    for model in MODEL_REGISTRY:
        value = model.value.lower()
        assert not any(p in value for p in prohibited)


def test_embedding_and_rerank_capabilities_stay_local() -> None:
    assert TABLE.for_task(TaskClass.EMBEDDING).model == ModelId.BGE_M3
    assert TABLE.for_task(TaskClass.RERANKING).model == ModelId.QWEN3_RERANKER_0_6B
    assert TABLE.model_spec(ModelId.BGE_M3).capability == "embed"
    assert TABLE.model_spec(ModelId.QWEN3_RERANKER_0_6B).capability == "rerank"
    assert TABLE.model_spec(ModelId.BGE_M3).provider == ProviderKind.OMLX
    assert TABLE.for_task(TaskClass.EMBEDDING).fallback_models == ()
    assert TABLE.for_task(TaskClass.RERANKING).fallback_models == ()


def test_audio_models_registered_for_voice() -> None:
    # Voice models live outside the router (voice engine talks to oMLX
    # directly) but must be documented in the policy module.
    assert "Qwen3-ASR-1.7B-4bit" in AUDIO_MODEL_IDS
    assert "parakeet-tdt-0.6b-v3-int8" in AUDIO_MODEL_IDS
    assert "Qwen3-TTS-12Hz-0.6B-Base-MLX-4bit" in AUDIO_MODEL_IDS


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
