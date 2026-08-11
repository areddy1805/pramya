# Pramya — Evaluation Strategy

> Companion to master plan §21 and ADR-009/012.
> How we prove AI quality: deterministic tests where possible, DeepEval where semantic judgment is required.

---

## 1. Principles

1. Never claim quality without verification (AGENTS.md).
2. Deterministic tests first; semantic evals only where needed.
3. Golden datasets are fixtures, checked into the repo, versioned.
4. Judge model: deepseek-v4-flash, temperature 0 (cost + privacy; DeepEval's gpt default overridden).
5. Every evaluator/prompt versioned; prompt change reruns affected evals.
6. "Output looks good" is not evidence.

## 2. Golden Datasets

`tests/evals/golden/` — synthetic resumes, JDs, transcripts, answers, expected competency graphs, expected evidence, expected evaluations, expected routing decisions, expected readiness numbers. Never real employer/customer data (spec §34).

Datasets for: role analysis, candidate extraction, question generation, answer evaluation, evidence extraction, adaptive routing, RAG grounding, final report, transcript analysis, debrief analysis, story analysis, readiness math, prioritization.

## 3. Deterministic Evaluations (plain pytest)

- Structured-output validity: every schema-typed output parses + passes business rules (score ranges, enums, no invented evidence).
- Readiness math: golden inputs → exact expected aggregates.
- Prioritization: queue ordering golden cases.
- Scoring aggregation: dimension → overall math.
- State transitions: interview/voice/session transition tables.
- Routing: task → model mapping table.
- Idempotency: duplicate answer submission → single evaluation.
- Prompt-injection: adversarial resume/JD fixtures → system not hijacked; document content stays data.
- PII: emitted observability events contain no candidate content.

## 4. Semantic Evaluations (DeepEval 4.1)

| Metric | Use |
|---|---|
| Faithfulness | evaluation/answer grounded in evidence (anti-hallucination) |
| AnswerRelevancy | question/evaluation relevance |
| ContextualPrecision / Recall / Relevancy | retrieval quality |
| Custom metrics | evidence relevance, evaluation consistency, question relevance, adaptive routing quality, hallucination risk, structured-output validity |

Custom metrics via `DeepEvalBaseMetric` (or LLMTestCase composition) with deepseek-v4-flash judge.

## 5. Runner + CI

- `make evals` → pytest + `deepeval test run`.
- CI: deterministic subset gates every PR; full suite nightly or on demand (token budget).
- Results recorded (pass rate per dataset); regressions block merges.
- Confident AI platform optional (not required).

## 6. Evaluation Versions

- `evaluation_version` table: name, version, prompt_hash, model_policy, created_at.
- Every stored `evaluation` row references its version → audits and regression analysis possible.
- Changing a prompt bumps the version and triggers dataset rerun.

## 7. Quality Gates

- Phase done ⇔ evals for that phase pass (per-phase acceptance criteria in master plan).
- V1 done ⇔ eval suite + full tests green + release checklist complete.
