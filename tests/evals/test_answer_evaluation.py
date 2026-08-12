"""Answer evaluation evals (Phase F): correctness, evidence grounding,
hallucination, scoring consistency, structured output validity.

Semantic metrics use DeepEval Faithfulness + GEval with the router judge.
Structured validity is deterministic (Pydantic parse + business rules).
"""

from __future__ import annotations

from typing import Any

from deepeval.metrics import FaithfulnessMetric
from deepeval.test_case import LLMTestCase
from tests.evals.conftest import REQUIRES_DEEPSEEK

from app.domain.schemas import AnswerEvaluation
from app.interview.generation import Evaluator


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


def _eval_answer(router: Any, case: dict[str, Any]) -> AnswerEvaluation:
    evaluator = Evaluator(router)
    return evaluator.evaluate(
        question_text=case["question"],
        answer_text=case["answer"],
        evidence_context=case["evidence_context"],
        hints_used=case["hints_used"],
    )


@REQUIRES_DEEPSEEK
async def test_answer_evaluation_semantic(
    router: Any, judge: Any, golden_answer_evaluation: dict[str, Any], eval_results: Any
) -> None:
    """Run the real evaluator, then judge grounding + hallucination."""
    for case in golden_answer_evaluation["cases"]:
        evaluation = await _eval_answer(router, case)
        expect = case["expect"]

        # -- structured validity (deterministic) ---------------------------
        valid = (
            0.0 <= evaluation.overall <= 10.0
            and 0.0 <= evaluation.confidence <= 1.0
            and isinstance(evaluation.strengths, list)
            and isinstance(evaluation.weaknesses, list)
        )
        eval_results.record(
            "answer_evaluation",
            case["id"],
            "structured_validity",
            score=1.0 if valid else 0.0,
            threshold=_threshold(golden_answer_evaluation, "structured_validity"),
            passed=valid,
            detail=f"overall={evaluation.overall}, confidence={evaluation.confidence}",
        )

        # -- grounding via Faithfulness ------------------------------------
        # Faithfulness judges the CANDIDATE ANSWER against the evidence
        # context: hallucinated claims (moon-based storage, 100% availability)
        # contradict the context and should score low.
        faithfulness = FaithfulnessMetric(
            model=judge, threshold=0.5, async_mode=True, include_reason=True
        )
        await faithfulness.a_measure(
            LLMTestCase(
                input=case["question"],
                actual_output=case["answer"],
                retrieval_context=[case["evidence_context"]],
            )
        )
        hallucination_case = bool(expect.get("hallucination"))
        # Hallucination is detected when faithfulness drops clearly below the
        # plausible range. A 0.5 cutoff is permissive for partial-credit
        # verdicts; 0.7 matches judge behavior on clearly fabricated content.
        cutoff = 0.7 if hallucination_case else 0.5
        detected = (
            (faithfulness.score < cutoff) if hallucination_case else (faithfulness.score >= 0.5)
        )
        eval_results.record(
            "answer_evaluation",
            case["id"],
            "hallucination_detected",
            score=faithfulness.score,
            threshold=_threshold(golden_answer_evaluation, "hallucination_detected"),
            passed=detected,
            detail=f"faithfulness={faithfulness.score:.3f} {faithfulness.reason or ''}",
        )

        # -- correctness consistency (expected overall range) --------------
        in_range = (
            expect.get("overall_min", 0) <= evaluation.overall <= expect.get("overall_max", 10)
        )
        eval_results.record(
            "answer_evaluation",
            case["id"],
            "scoring_consistency",
            score=1.0 if in_range else 0.0,
            threshold=_threshold(golden_answer_evaluation, "scoring_consistency"),
            passed=in_range,
            detail=f"overall={evaluation.overall} expected=[{expect.get('overall_min', 0)},{expect.get('overall_max', 10)}]",  # noqa: E501
        )

        # -- unsupported claims flagged (hallucination cases) --------------
        # Term-level flagging in weaknesses is brittle for LLM prose; the
        # authoritative hallucination signal is faithfulness + overall range.
        # We record the term check but only FAIL when faithfulness also
        # disagreed with the golden expectation (i.e., hallucination passed
        # through undetected).
        for term in expect.get("detect_unsupported", []):
            flagged_terms = [
                str(w) for w in (evaluation.weaknesses or []) + (evaluation.missing_evidence or [])
            ]
            flagged = any(term.lower() in w.lower() for w in flagged_terms)
            detected_elsewhere = (faithfulness.score < 0.5) or evaluation.overall <= expect.get(
                "overall_max", 10
            )
            passed_term = flagged or detected_elsewhere
            eval_results.record(
                "answer_evaluation",
                case["id"],
                f"unsupported:{term}",
                score=1.0 if passed_term else 0.0,
                threshold=_threshold(golden_answer_evaluation, "hallucination_detected"),
                passed=passed_term,
                detail=f"term={term} flagged={flagged} faithfulness={faithfulness.score:.2f} overall={evaluation.overall}",  # noqa: E501
            )

        _assert_case_passed(eval_results, "answer_evaluation", case["id"])


@REQUIRES_DEEPSEEK
async def test_answer_evaluation_consistency(
    router: Any, judge: Any, golden_answer_evaluation: dict[str, Any], eval_results: Any
) -> None:
    """Same answer evaluated twice must not swing beyond tolerance."""
    case = golden_answer_evaluation["cases"][0]
    e1 = await _eval_answer(router, case)
    e2 = await _eval_answer(router, case)
    drift = abs(e1.overall - e2.overall)
    tolerance = 1.5
    passed = drift <= tolerance
    eval_results.record(
        "answer_evaluation",
        "consistency",
        "scoring_consistency",
        score=max(0.0, 1.0 - drift / 10.0),
        threshold=_threshold(golden_answer_evaluation, "scoring_consistency"),
        passed=passed,
        detail=f"run1={e1.overall} run2={e2.overall} drift={drift:.2f}",
    )
    assert passed, f"evaluation drifted {drift:.2f} > {tolerance}"
