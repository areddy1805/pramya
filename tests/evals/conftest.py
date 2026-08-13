"""Eval suite fixtures (Phase F).

- Loads golden datasets from tests/evals/datasets/*.json
- Builds a real InferenceRouter (DeepSeek configured) when DEEPSEEK_API_KEY
  is present; semantic evals skip otherwise.
- RouterJudgeLLM adapts the router to DeepEval metrics.
- Collects results into tests/evals/results/latest.json (machine-readable)
  and prints a human-readable summary at session end.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from tests.evals.judge import RouterJudgeLLM

from app.ai.router import InferenceRouter

DATASETS_DIR = Path(__file__).parent / "datasets"
RESULTS_DIR = Path(__file__).parent / "results"

REQUIRES_DEEPSEEK = pytest.mark.skipif(
    not __import__("os").environ.get("DEEPSEEK_API_KEY"),
    reason="DEEPSEEK_API_KEY not set; semantic eval skipped (deterministic evals still run)",
)


def _load_dataset(name: str) -> dict[str, Any]:
    with (DATASETS_DIR / f"{name}.json").open() as fh:
        return json.load(fh)


@pytest.fixture(scope="session")
def golden_question_generation() -> dict[str, Any]:
    return _load_dataset("question_generation")


@pytest.fixture(scope="session")
def golden_answer_evaluation() -> dict[str, Any]:
    return _load_dataset("answer_evaluation")


@pytest.fixture(scope="session")
def golden_evidence_extraction() -> dict[str, Any]:
    return _load_dataset("evidence_extraction")


@pytest.fixture(scope="session")
def golden_rag() -> dict[str, Any]:
    return _load_dataset("rag")


@pytest.fixture(scope="session")
def golden_adaptation() -> dict[str, Any]:
    return _load_dataset("adaptation")


@pytest.fixture(scope="session")
def golden_voice() -> dict[str, Any]:
    return _load_dataset("voice")


@pytest.fixture(scope="session")
def router() -> InferenceRouter | None:
    """Real production router when DeepSeek is configured, else None."""
    import os

    if not os.environ.get("DEEPSEEK_API_KEY"):
        return None
    from app.ai.factory import build_inference_router

    return build_inference_router()


@pytest.fixture(scope="session")
def judge(router: InferenceRouter | None) -> RouterJudgeLLM | None:
    if router is None:
        return None
    return RouterJudgeLLM(router)


# -- results collection -----------------------------------------------------


class EvalResults:
    """Session-scoped results collector: machine-readable + human summary.

    Statuses (evaluation integrity, Phase F steering):
      PASS          metric gate satisfied
      FAIL          metric gate not satisfied (visible, gates the suite)
      WARNING       observed anomaly/variance recorded but not gating
      NOT_VERIFIED  could not be evaluated (e.g., external dependency missing)
      BLOCKED       external blocker
    """

    def __init__(self) -> None:
        self.suites: dict[str, list[dict[str, Any]]] = {}

    def record(
        self,
        suite: str,
        case_id: str,
        metric: str,
        score: float,
        threshold: float,
        passed: bool,
        detail: str = "",
        status: str | None = None,
    ) -> None:
        status = status or ("PASS" if passed else "FAIL")
        self.suites.setdefault(suite, []).append(
            {
                "case_id": case_id,
                "metric": metric,
                "score": round(score, 4),
                "threshold": threshold,
                "passed": bool(passed),
                "status": status,
                "detail": detail,
            }
        )

    def write(self) -> None:
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        payload = {"suites": self.suites}
        with (RESULTS_DIR / "latest.json").open("w") as fh:
            json.dump(payload, fh, indent=2)
        # Human summary
        lines: list[str] = []
        total = passed = warnings = 0
        for suite, rows in self.suites.items():
            p = sum(1 for r in rows if r["status"] == "PASS")
            w = sum(1 for r in rows if r["status"] == "WARNING")
            total += len(rows)
            passed += p
            warnings += w
            lines.append(
                f"  {suite}: {p}/{len(rows)} PASS, {w} WARNING, "
                f"{sum(1 for r in rows if r['status'] == 'FAIL')} FAIL"
            )
        summary = f"EVAL SUMMARY: {passed}/{total} PASS, {warnings} WARNING"
        lines.append(summary)
        print("\n" + summary)
        for line in lines[:-1]:
            print(line)


@pytest.fixture(scope="session")
def eval_results() -> Iterator[EvalResults]:
    collector = EvalResults()
    yield collector
    collector.write()
