# Career Profile Workspace — Ownership & Persistence

> Applies to the V1 profile system (ADR-026). The database is the source of
> truth; the frontend is a client of that state; demo data is never an
> invisible fallback.

## Ownership model

```
USER  ──owns──▶  CAREER PROFILE  ──owns──▶  resume documents (kind=resume)
                      │                     JD documents (kind=jd)
                      │                     target roles (+ competencies)
                      │                     evidence (claims)
                      │                     interview sessions
                      │                     readiness snapshots
                      │                     preparation queue
                      └──▶ practice history
```

Every workspace entity carries an unambiguous ownership path:

- `document.profile_id` → `candidate_profile.id` → `user.id`
- `role.profile_id` → `candidate_profile.id` → `user.id`
- `evidence.profile_id` → `candidate_profile.id` → `user.id`
- `interview_session.candidate_profile_id` → `candidate_profile.id` → `user.id`
- `readiness_snapshot.profile_id`, `preparation_item.profile_id`,
  `practice_session.profile_id` → `candidate_profile.id` → `user.id`

Deleting a profile cascades to everything the profile owns (FK CASCADE).
Deleting a user cascades to all their profiles and everything below.

## USER != PROFILE

One user owns **many** profiles. `candidate_profile` is the career-profile
container:

| column | meaning |
|---|---|
| `name` | display name, unique per user (`uq_candidate_profile_user_name`) |
| `slug` | URL-ish key (auto from name if omitted) |
| `positioning` | target positioning statement |
| `status` | e.g. `active` |
| `seniority_target` / `headline` / `timezone` | legacy candidate fields |

## Authorization rules

- **Never trust a client-supplied `profile_id`.** Every profile-scoped
  operation verifies the profile belongs to the caller's `user_id`
  server-side; a mismatch returns 404 (not 403, so cross-user probing
  reveals nothing).
- The **active profile is a UX preference only**
  (`user.active_profile_id`, persisted). It is never an authorization
  boundary: APIs that need profile context take an explicit `profile_id`.
- Legacy callers that omit `profile_id` fall back to the user's active
  profile, else their first profile.

## Active profile semantics

- Stored on `user.active_profile_id` (SET NULL on profile delete).
- First profile created for a user becomes active automatically.
- Switching (`PUT /candidates/{user_id}/active-profile`) persists
  server-side and survives browser refresh and backend restart.
- The frontend mirrors it in a zustand store (localStorage) for instant UI
  switching, but the server value is authoritative and re-syncs on load.

## Resume management

- Resumes are `document` rows with `kind=resume`, profile-scoped.
- One *current* resume per profile: the latest uploaded resume is the
  active one; earlier versions are retained as history rows.
- Upload flow: file → multipart POST → ownership/profile validation →
  persistent storage (`.runtime/uploads`) → parse → PARSED/FAILED status →
  metadata persistence → authoritative response → UI refresh from server.

## JD / document upload + deduplication

- `POST /documents` with `user_id`, `profile_id`, `kind`, `file`.
- **Identical content within the same `(user, profile)` is idempotent:**
  HTTP 200 with `{status: "deduplicated", created: false, document_id,
  processing_status, profile_id}` — a normal application state, never an
  unexplained failure.
- The same file in a **different profile** is a distinct document (each
  profile keeps its own workspace; dedup is per `(user, profile)`).
- Legacy uploads without `profile_id` attribute to the user's default
  profile.

## Derived analytics scoping

Readiness, the preparation queue, and progress aggregate **only** the
requested profile's evidence/evaluations. `GET /readiness/latest`,
`POST /readiness`, `POST /preparation/regenerate`, `GET /preparation`, and
`GET /progress` all accept `profile_id` and filter server-side. Snapshots
and queue items persist their `profile_id`.

## Demo-mode boundary

- **Normal mode:** DB authoritative. API success → server state; API
  failure → real error state; API empty → real empty state.
- **Demo mode:** explicit `POST /api/v1/demo/setup` seeds data for a
  user. Demo fixtures are never an automatic fallback when the API fails
  or returns empty.
