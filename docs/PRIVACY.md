# Pramya — Privacy

Pramya is a single-user, local-first interview preparation product. This
document states what data the application holds, where it goes, and what is
deliberately not collected.

## Data Pramya processes

- Candidate profile (headline, seniority target, timezone)
- Resumes and job descriptions (uploaded documents)
- Practice interview questions, answers, transcripts
- Voice recordings (candidate audio, opt-in)
- Evaluations, evidence, readiness snapshots, stories, debriefs
- Structured analysis derived from the above (role models, competency
  graphs, preparation plans)

All of it is **sensitive application data** and treated as such.

## Where data lives

- **Primary store:** local PostgreSQL (Postgres + pgvector) reachable only
  on the development host by default.
- **Uploaded bytes:** local storage directory (`.runtime/uploads`),
  keyed by content digest — never by client filename.
- **Voice audio (opt-in):** `.runtime/audio`, retained for
  `VOICE_RETENTION_DAYS` (default 30); rows carry `retention_until`.
  Persistence is disabled entirely with `VOICE_STORE_AUDIO=false`.

## What leaves the machine

- **DeepSeek (text reasoning):** question/evaluation/hint/extraction/role/
  report/debrief prompts are sent to the DeepSeek API. This is the only
  cloud data path in V1 and requires `DEEPSEEK_API_KEY`.
- **oMLX (speech + retrieval):** all local — no audio, embeddings, or
  reranking leaves the machine.
- **Langfuse (optional observability):** when configured, span metadata
  (ids, latencies, token counts, task names) is sent to your **self-hosted**
  Langfuse instance. Raw candidate content is **never** included.

## What is deliberately not collected

- No analytics/tracking beacons, no telemetry SDKs in the frontend.
- No raw transcript/answer/resume text in logs or traces (redaction policy:
  ids + metadata only; enforced by `tests/unit/test_observability.py`).
- No per-user accounts, no third-party identity providers in V1.

## Deletion

- Deleting a candidate cascades to owned data (documents, evidence,
  sessions, turns, audio/transcript segments, stories, debriefs) via foreign
  keys. `DELETE /api/v1/candidates/{id}` is the single-point deletion
  endpoint.

## Security

See `docs/operations/SECURITY.md` (ADR-010) for the threat model: upload
validation, prompt-injection boundaries, LLM output gating, bearer-token
auth (opt-in), rate limiting, and secret handling.
