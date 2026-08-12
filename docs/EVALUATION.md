# Pramya — Evaluation

Pramya separates two evaluation concerns. Read both before judging results.

## 1. Candidate evaluation (product feature)

Every practice answer is scored by the interview workflow:

- **13 dimensions** (0–10 each): correctness, technical depth, clarity,
  structure, relevance, evidence, communication, tradeoff awareness,
  reasoning, confidence, specificity, seniority alignment, completeness.
- **Overall** 0–10, **confidence** 0–1, strengths / weaknesses / missing
  evidence, follow-up suggestions.
- Every answer also emits **evidence rows** (status `observed`) with
  provenance (`source_ref=answer:{id}`) into the candidate ledger.
- Evaluations are **immutable and versioned**: `evaluation_version` +
  `evaluator_version` recorded per evaluation; `prompt_hash` ties the
  evaluation to the prompt text that produced it.

Hints penalize the score: `hints_used` is persisted per turn and passed into
the evaluator.

## 2. AI-system evaluation (development harness)

The golden-data harness under `tests/evals/` evaluates **Pramya itself** —
question generation, answer evaluation, evidence extraction, RAG grounding,
adaptation, voice behavior, and structured-output robustness.

### Where datasets live

`tests/evals/datasets/` — one JSON/golden file per suite:

- question generation (difficulty/competency appropriateness)
- answer evaluation (score calibration vs golden judgments)
- evidence extraction (claims found, provenance, no fabrication)
- RAG (retrieval relevance given a query + corpus)
- adaptation (follow-up reacts to prior answer)
- voice (event-contract behavior, interruption)

### How to run

```bash
make evals
# or, from backend/:  uv run pytest ../tests/evals -p no:warnings
```

Requires `DEEPSEEK_API_KEY` (the judge is `deepseek-v4-flash` routed through
the `InferenceRouter` — no router bypass, no OpenAI SDK).

### What the metrics mean

- **PASS** — the check met its criterion exactly.
- **FAIL** — the check demonstrably missed a criterion.
- **WARNING** — borderline/scope variance: e.g. the judge applied an
  inappropriate criterion, or a repeat run showed model variance on a
  borderline metric. Warnings are recorded, never silently upgraded.
- **NOT_VERIFIED** — the check could not run (missing fixture/dependency).

### Thresholds

Thresholds live inside each suite file (`tests/evals/test_*.py`) next to the
assertions so a threshold change is reviewable. The policy is: never lower a
threshold to manufacture PASS; classify honestly instead.

### How to add a golden case

1. Add the case to the suite's dataset (or a new file under
   `tests/evals/datasets/`).
2. Give it an explicit expected outcome (exact JSON, score range, or
   behavioral contract).
3. Run `uv run pytest ../tests/evals/<suite> -p no:warnings` and confirm the
   new case PASSes or is a justified WARNING.

### How results are generated

Each run writes `tests/evals/results/latest.json` (machine-readable: per-suite
checks, status, reason) and prints a human summary. Recorded reference run:
**95 checks, 0 FAIL, 3 WARNING** — the 3 WARNINGs are documented in
`tests/evals/README.md` (model variance / judge-scope), with the raw JSON
preserved as evidence.

### Why not DeepEval

DeepEval is not used: it hard-depends on the OpenAI Python SDK, which
conflicts with the httpx-only provider constraint. ADR-024 records this
deviation; the judge is a custom router-bound adapter instead.
