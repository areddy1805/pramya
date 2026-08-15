# ADR-026 — Persistent multi-profile career workspace

Status: Accepted
Date: 2026-08-14

## Context

Pramya was effectively a single-workspace demo: one user owned exactly one
`candidate_profile` (unique constraint on `user_id`), and documents, roles,
evidence, interviews, and derived analytics were all scoped by `user_id`
alone. There was no way for a user to maintain multiple independent career
identities (e.g. "AI Engineer" vs "Forward Deployed Engineer"), no profile
switcher, and no proof that workspace data survived restarts without demo
seeding. Duplicate uploads surfaced as an unexplained 422 validation error.

## Decision

Make the career profile a first-class, persisted, multi-instance container
owned by a user, and scope every workspace entity to it.

1. **`candidate_profile` becomes the career profile.** It gains `name`,
   `slug`, `positioning`, `status`; the one-per-user unique constraint is
   replaced by unique `(user_id, name)`. A user may own many profiles.
2. **Ownership path is `entity -> profile -> user`.** `document`, `role`,
   `evidence`, `readiness_snapshot`, `preparation_item`, and
   `practice_session` gain `profile_id` (FK, CASCADE on profile delete);
   `interview_session.candidate_profile_id` (pre-existing) is now populated
   at creation. Existing rows are backfilled to the owning user's first
   profile.
3. **Authorization never trusts a client-supplied `profile_id` alone.**
   Every profile-scoped read/write verifies the profile belongs to the
   authenticated `user_id` server-side (404 when it does not).
4. **Active profile is a persisted UX preference only**
   (`user.active_profile_id`, SET NULL). It is never an authorization
   boundary; profile-scoped APIs still take an explicit `profile_id` that is
   ownership-checked.
5. **Duplicate uploads are idempotent.** Identical content within the same
   `(user, profile)` returns HTTP 200 `{status: "deduplicated", created:
   false, document_id, processing_status, profile_id}` — never a generic
   422. The same file in a *different* profile is a distinct document (each
   profile keeps its own workspace).
6. **Derived analytics are profile-scoped.** Readiness, preparation queue,
   and progress read only the evidence/evaluations of the requested profile;
   snapshots and queue items carry `profile_id`.
7. **Demo data never substitutes for real state.** The demo path remains an
   explicit `POST /demo/setup`; normal-mode reads return real server state
   (or a real empty/error state).

## Consequences

- A user can maintain multiple independent persistent career profiles, each
  with its own resumes, target roles, JDs, evidence, interviews, and
  analytics.
- Cross-profile and cross-user access is blocked (404) at the service layer.
- Profile switching is persisted server-side and survives browser refresh
  and backend restart.
- Backward compatibility: legacy callers that omit `profile_id` fall back to
  the user's active-or-first profile; the old `/candidates/{user_id}`
  endpoints keep working.

## Migrations

- `0003_profile_workspace` — profile identity columns + `profile_id` on
  document/role/evidence + `user.active_profile_id` + deterministic
  backfill.
- `0004_profile_analytics` — `profile_id` on readiness_snapshot/
  preparation_item/practice_session + backfill.

## Validation

- 211 unit+contract + 56 integration tests green (incl. 18 new profile
  tests: CRUD, ownership, isolation, dedup idempotency, analytics scoping).
- Real browser E2E (`frontend/e2e/profile-workspace.spec.ts`) proves
  create → upload resume per profile → JD upload → duplicate-JD dedup →
  switch → isolation → refresh, against the live backend + DB.
- Restart durability verified: profiles, documents, and active selection
  survive backend stop/start.
