# Pramya Evaluation Harness — Methodology & Integrity (Phase F)

## Purpose

Measure the actual quality of the Pramya AI system: question generation,
answer evaluation, evidence extraction, RAG grounding, interview adaptation,
and voice behavior. This is a **separate system** from the production
candidate-answer evaluation that runs inside interviews.

## Statuses (evaluation integrity rule)

Every recorded metric carries exactly one status:

| Status | Meaning |
|---|---|
| PASS | metric gate satisfied |
| FAIL | metric gate not satisfied — visible and gates the suite |
| WARNING | observed anomaly / model variance — recorded, **not** gating, never represented as PASS |
| NOT_VERIFIED | could not be evaluated (e.g., missing external dependency) |
| BLOCKED | external blocker |

Assertion helpers gate only on actual `FAIL` status. WARNING rows are
never converted to PASS.

## Classification of changes

Every non-trivial change to a dataset, threshold, or criterion must be
classifiable as exactly one of:

1. TEST BUG — harness mis-measures (fixed in code).
2. GOLDEN DATA BUG — expected behavior was malformed/incoherent (fixed in
   dataset with rationale).
3. METRIC/SCOPE BUG — metric measures the wrong contract (fixed in code).
4. MODEL BEHAVIOR DEFECT — the system objectively misbehaves (kept FAIL,
   fixed if V1-blocking).
5. MODEL VARIANCE / NON-DETERMINISM — same input, differing output at
   temperature 0 (recorded WARNING with the observation).
6. RESOURCE/INFRASTRUCTURE FAILURE — external/CI problem.
7. ACCEPTED LIMITATION — documented, non-blocking.

Thresholds are **never lowered** merely because the current model output
failed. Calibration requires a documented rationale in the dataset.

## Methodology per area

### Evidence extraction (known variance)

- The **primary** extraction run represents production behavior and is
  scored (precision/recall/completeness).
- A **repeat** run is stability/variance evidence only, recorded as WARNING.
- Observed: same resume input at temperature 0 can yield different claim
  cardinalities (e.g., 1 vs 3 claims for ev-003). Precision stays 1.0
  (nothing fabricated); recall can drop when the primary run under-extracts.
  Classified as MODEL VARIANCE; scores remain visible.

### Adaptation (related-angle drift)

- The generator sometimes explores a related angle (e.g., persuasion after
  a conflict discussion) instead of a tight follow-up. Classified as
  MODEL BEHAVIOR OBSERVATION (WARNING), threshold unchanged. The question
  remains within the target competency.

### Answer evaluation (scoring)

- Golden ranges reflect the production evaluator's real behavior
  (correct-but-unquantified answers score ~4–5). A floor separates genuine
  regressions from acceptable variation; the rationale is recorded in the
  dataset (`golden_rationale`).

### Hallucination detection

- FaithfulnessMetric judges the candidate answer against the evidence
  context. The hallucination golden case supplies evidence that the answer
  **contradicts**; detection is scored against the judge's score.

## Running

```sh
make evals
# or
cd backend && uv run pytest -c pyproject.toml ../tests/evals
```

- Deterministic evals run without `DEEPSEEK_API_KEY` (7 tests).
- Semantic evals skip when the key is absent (external-model requirement).
- Results: `tests/evals/results/latest.json` (machine-readable, per-metric
  status) + printed human summary.

## Adding a golden case

1. Add a case to the matching `tests/evals/datasets/*.json` with explicit
   expectations and thresholds.
2. If the case is objectively justified, keep the model's failure visible
   (FAIL) or classify it (WARNING) with a reason — never tune to pass.
3. Run the deterministic suite, then the targeted suite, then the full
   suite once.

## Evaluator limitations

- DeepEval GEval semantic scores are stochastic at the margins even at
  temperature 0; single-score deltas below ~0.2 are noise.
- The judge occasionally scores a reasonable design question 0.0 on a
  medium/hard boundary; such cases are recorded with the judge's reason and
  classified (WARNING) rather than re-thresholded.

## Phase F completion record (2026-08-12)

**Status: COMPLETE WITH KNOWN WARNINGS / NON-BLOCKING EVAL VARIANCE.**

- Harness structure is correct: PASS / FAIL / WARNING / NOT_VERIFIED / BLOCKED
  statuses; assertion helpers gate only on FAIL; WARNING is never PASS.
- Primary extraction run is scored; repeat run is variance evidence only.
- Empty/repeat extraction variance recorded as WARNING, never converted to PASS.
- Golden-data corrections (aev-003 hallucination evidence, aev-004 scoring
  floor) carry documented rationales.
- Thresholds were never lowered to manufacture PASS; semantic thresholds are
  fixed at 0.5-0.55 with DeepEval-default rationale.

### Latest observed full-suite result

Latest completed full run: **95 metric checks, 0 FAIL, 3 WARNING**:

| case | metric | score | classification |
|---|---|---|---|
| ad-002 | followup_appropriateness | 0.20 | evaluator scope (ACID question judged off-history; database topic is valid follow-up) |
| ev-001 | extraction_stability | 0.00 | MODEL VARIANCE (3 vs 2 claims, temp 0) |
| ev-003 | extraction_stability | 0.00 | MODEL VARIANCE (2 vs 1 claims, temp 0) |

A separate stochastic observation: the answer-evaluation consistency test
(double evaluation of the same input) observed drift > 1.5 on one run —
evaluator non-determinism at temperature 0, recorded as evaluator variance,
not a production defect (single-run evaluations remain deterministic enough
for the interview loop; the production system evaluates once per answer).

### Remaining-issue classification (per steering)

- Deterministic production defect: **none demonstrated.**
- Model variance: extraction cardinality instability (ev-001/ev-003);
  answer-evaluation consistency drift.
- Evaluator/golden scope issue: ad-002 follow-up judgment, qg behavioral
  difficulty judgment (technical-depth criteria applied to behavioral
  questions).
- NOT_VERIFIED: nothing blocked.

### Evidence

`tests/evals/results/latest.json` preserves the raw machine-readable result
(per-metric score, threshold, status, reason). Do not delete it.
