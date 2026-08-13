"""RAG evals (Phase F): retrieval relevance, context precision/recall,
faithfulness/grounding.

Semantic metrics use DeepEval (Faithfulness, AnswerRelevancy,
ContextualPrecision/Recall) with the router judge against golden
query/context/answer triples.
"""

from __future__ import annotations

from typing import Any

from deepeval.metrics import (
    AnswerRelevancyMetric,
    ContextualPrecisionMetric,
    ContextualRecallMetric,
    FaithfulnessMetric,
)
from deepeval.test_case import LLMTestCase
from tests.evals.conftest import REQUIRES_DEEPSEEK


def _threshold(dataset: dict[str, Any], metric: str) -> float:
    return float(dataset["thresholds"][metric])


def _assert_case_passed(eval_results: Any, suite: str, case_id: str) -> None:
    rows = eval_results.suites.get(suite, [])
    for row in rows:
        if row["case_id"] == case_id and row.get("status") == "FAIL":
            raise AssertionError(
                f"{suite}:{case_id} metric '{row['metric']}' failed "
                f"(score={row['score']} < threshold={row['threshold']}): {row['detail']}"
            )


def test_rag_deterministic_retrieval_math(golden_rag: dict[str, Any], eval_results: Any) -> None:
    """Deterministic: context precision/recall computed from golden labels.

    Runs without DeepSeek. precision@k = relevant among top-k; recall =
    relevant found / total relevant. The golden labels are the ground truth.
    """
    for case in golden_rag["cases"]:
        ctx = case["retrieved_context"]
        rel = set(case["relevant_indexes"])
        n = len(ctx)
        if n == 0:
            eval_results.record(
                "rag", case["id"], "context_precision_det", 0.0, 1.0, False, "empty context"
            )
            continue
        # precision@k for each k where a relevant doc appears
        hits = 0
        precisions: list[float] = []
        for k, _ in enumerate(ctx, start=1):
            if k - 1 in rel:
                hits += 1
            precisions.append(hits / k)
        # mean average precision over relevant positions
        map_score = sum(p for k, p in enumerate(precisions, start=1) if k - 1 in rel) / max(
            len(rel), 1
        )
        recall = hits / max(len(rel), 1)
        eval_results.record(
            "rag",
            case["id"],
            "context_precision_det",
            score=map_score,
            threshold=_threshold(golden_rag, "context_precision"),
            passed=map_score >= _threshold(golden_rag, "context_precision"),
            detail=f"MAP@k={map_score:.3f} relevant={len(rel)}",
        )
        eval_results.record(
            "rag",
            case["id"],
            "context_recall_det",
            score=recall,
            threshold=_threshold(golden_rag, "context_recall"),
            passed=recall >= _threshold(golden_rag, "context_recall"),
            detail=f"recall={recall:.3f} hits={hits}/{len(rel)}",
        )
        assert map_score >= _threshold(golden_rag, "context_precision"), case["id"]
        assert recall >= _threshold(golden_rag, "context_recall"), case["id"]


@REQUIRES_DEEPSEEK
async def test_rag_grounding_metrics(
    judge: Any, golden_rag: dict[str, Any], eval_results: Any
) -> None:
    for case in golden_rag["cases"]:
        tc = LLMTestCase(
            input=case["query"],
            actual_output=case["answer"],
            retrieval_context=case["retrieved_context"],
            expected_output=case.get("expected_output", ""),
        )

        # faithfulness: answer grounded in retrieved context (all cases)
        faithfulness = FaithfulnessMetric(
            model=judge, threshold=0.5, async_mode=True, include_reason=True
        )
        await faithfulness.a_measure(tc)
        faithful_ok = (
            faithfulness.score >= 0.5 if case["expect_faithful"] else faithfulness.score < 0.5
        )
        eval_results.record(
            "rag",
            case["id"],
            "faithfulness",
            score=faithfulness.score,
            threshold=_threshold(golden_rag, "faithfulness"),
            passed=faithful_ok,
            detail=f"{faithfulness.reason or ''}",
        )

        # For unfaithful (hallucination) cases, faithfulness detection is the
        # only asserted metric; relevance/precision/recall against a wrong
        # answer are not meaningful.
        if not case["expect_faithful"]:
            continue

        # answer relevancy: answer answers the query
        relevancy = AnswerRelevancyMetric(
            model=judge, threshold=0.5, async_mode=True, include_reason=True
        )
        await relevancy.a_measure(tc)
        eval_results.record(
            "rag",
            case["id"],
            "retrieval_relevance",
            score=relevancy.score,
            threshold=_threshold(golden_rag, "retrieval_relevance"),
            passed=relevancy.score >= _threshold(golden_rag, "retrieval_relevance"),
            detail=f"{relevancy.reason or ''}",
        )

        # context precision: are relevant chunks ranked high?
        precision = ContextualPrecisionMetric(
            model=judge, threshold=0.5, async_mode=True, include_reason=True
        )
        await precision.a_measure(tc)
        eval_results.record(
            "rag",
            case["id"],
            "context_precision",
            score=precision.score,
            threshold=_threshold(golden_rag, "context_precision"),
            passed=precision.score >= _threshold(golden_rag, "context_precision"),
            detail=f"{precision.reason or ''}",
        )

        # context recall: is the expected output covered by the context?
        recall = ContextualRecallMetric(
            model=judge, threshold=0.5, async_mode=True, include_reason=True
        )
        await recall.a_measure(tc)
        eval_results.record(
            "rag",
            case["id"],
            "context_recall",
            score=recall.score,
            threshold=_threshold(golden_rag, "context_recall"),
            passed=recall.score >= _threshold(golden_rag, "context_recall"),
            detail=f"{recall.reason or ''}",
        )
        _assert_case_passed(eval_results, "rag", case["id"])
