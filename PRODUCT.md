# Pramya — Product Context

> Durable product context for the Pramya redesign. This document is the
> anchor for product-level decisions: identity, domain model, principles,
> and constraints. It deliberately contains **no visual/design decisions**
> (those belong in a future DESIGN.md) and **no implementation detail**
> (that lives in `docs/MASTER_IMPLEMENTATION_PLAN.md`).
>
> Verified against the repository as of the `ui-revamp` branch (2026-08).
> Sources: `docs/MASTER_IMPLEMENTATION_PLAN.md` (§1–6), `docs/DECISIONS.md`
> (ADR-016/019/023/026), `docs/PROJECT_MEMORY.md`, `README.md`, and the
> existing frontend (`frontend/src`).

---

## 1. Product Identity

**Pramya — prove you're ready.**

Pramya is an evidence-driven interview preparation and assessment platform
for technical and professional roles. It is a serious training instrument,
not a chatbot, not a question generator, and not a generic AI SaaS wrapper.

The product builds a **closed loop** from a candidate's own materials to a
measurable readiness verdict:

```
Resume + JD → Candidate Intelligence + Role Intelligence → Competency Model
→ Gap Analysis → Preparation Plan → Practice/Assessment (text + voice)
→ Answer/Performance → Evidence Extraction → Evaluation → Candidate Model
Update → Readiness Update → Next Highest-Value Practice
```

Everything the candidate sees — readiness, progress, gaps, scores — is
derived from **evidence** (claims, observations, demonstrations) and
**deterministic aggregation**, never from "LLM → 8/10" vibes.

The flagship experience is a **live spoken mock interview**: the AI
interviewer speaks (local TTS), listens to real speech (local ASR), evaluates
answers with DeepSeek, extracts evidence, and adapts follow-ups — over a
WebSocket with first-class interruption, pause/resume, and reconnect
semantics.

---

## 2. Who It Is For

| Persona | Goals | Needs |
|---|---|---|
| **Alex — Senior SWE switching roles** | Prove readiness for a specific JD; avoid wasting real interviews | JD analysis, resume deep dive, adaptive technical interviews, evidence-backed feedback, targeted practice |
| **Priya — Career switcher / student** | Build confidence and fundamentals from scratch | Competency map, progressive practice, story bank, structured feedback, progress visibility |
| **Dev — New grad** | Interview reps across formats | Mock interviews (technical/behavioral), hints, system-design practice, report |
| **Contributor / AI engineer** | Inspect, extend, evaluate Pramya | Clean architecture, ADRs, eval suite, runnable demo, documented model routing |

Deployment reality (V1): single-user local product. No account system, no
teams, no recruiter side. The candidate is the only user.

---

## 3. Core Domain Concepts

The product's vocabulary — every screen and every message should speak it:

- **Candidate profile** — the person preparing; owns documents, roles,
  evidence, analytics. One user may hold multiple profiles.
- **Documents** — resume and job description (PDF/DOCX/TXT/MD), parsed,
  chunked, embedded, indexed. Preferred resume/JD are explicit per profile.
- **Role model** — competency graph derived from the target JD: required vs
  preferred competencies, weights, seniority.
- **Evidence ledger** — the heart of the product. Claims extracted from the
  resume, observations from practice answers, demonstrations across
  sessions. Provenance ladder:
  **claimed → observed → demonstrated → inferred → unknown**. Evidence is
  first-class: it is the reason behind every score.
- **Readiness** — deterministic aggregation of evidence coverage ×
  importance × recency × demonstrated ability. Per-competency and overall,
  with confidence and critical gaps. Never fabricated; absent data is
  represented explicitly.
- **Preparation queue** — gap → priority → today's practice items, each
  with a reason and expected value.
- **Interview session** — adaptive assessment in 8 modes (general mock,
  resume deep dive, JD interview, technical, behavioral, project deep dive,
  system design (text), coding/technical reasoning (verbal)). Text and
  voice are two modes of the same loop.
- **Evaluation** — 13 dimensions (correctness, technical depth, clarity,
  structure, relevance, evidence, communication, tradeoff awareness,
  reasoning, confidence, specificity, seniority alignment, completeness)
  with an overall 0–10 score, confidence, strengths/weaknesses/missing
  evidence, and follow-up suggestions. Versioned; evidence rows emitted per
  answer.
- **Progressive hints** — 4 levels (nudge → direction → partial reasoning →
  worked approach); hint usage is persisted and affects evaluation.
- **Story bank** — STAR stories (Situation/Task/Action/Result/Metrics/
  Conflict/Learning/Strength) mapped to competencies, with freshness, usage,
  coverage, strength, confidence tracking.
- **History / transcript / debrief** — durable per-session record;
  real-interview debriefs folded into future recommendations.
- **Communication analysis** — measured characteristics only (speaking
  time, latency, fillers, verbosity, structure): never personality or
  deception claims.
- **Runtime / model status** — provider health and model inventory;
  routing visibility for debugging.

---

## 4. Product Principles (constrain every decision)

1. **Evidence-first.** Every important score has observable reasons.
   Never present an inference as candidate-provided fact.
2. **Deterministic where possible.** Readiness, prioritization, scoring
   aggregation, progress are deterministic application logic; LLMs provide
   semantic judgments only.
3. **Not a ChatGPT wrapper.** Pramya owns the candidate model, role model,
   competency model, evidence ledger, readiness model, preparation queue,
   and historical model.
4. **Voice is first-class.** Interruption and cancellation are correctness
   requirements; no stale TTS after interrupt; reconnect behavior is driven
   by authoritative persisted state, never client assumptions.
5. **Local-first.** Minimize expensive cloud inference; local speech and
   retrieval models through oMLX; DeepSeek reserved for text reasoning that
   needs it.
6. **Calm, professional, trustworthy UI.** No gimmicks, no fake confidence,
   no meaningless percentages. The product must feel like a serious
   instrument, not a toy or a hype dashboard.
7. **Treat AI output as untrusted data.** Structured proposal → validation
   → application logic → persistence.
8. **Honest status.** PASS / FAIL / WARNING / NOT_VERIFIED are distinct.
   Absence of evidence is shown as absence, never filled in.

---

## 5. Experience Principles (tone of the product)

- The product is an **instrument panel for preparation**: the candidate
  should be able to see, at a glance, where they are, what to improve, and
  what to do next — with the reasons visible behind every number.
- **Seriousness**: high-stakes context (real interviews are on the line).
  The UI must inspire trust: precise, restrained, editorial. No cartoon
  avatars, no celebratory confetti for ordinary progress, no fake-chat
  theater.
- **Evidence visibility**: every score should be traceable to evidence;
  every recommendation to a gap. Where evidence is missing, the absence is
  explicit.
- **Focus**: practice/interview is a focused workspace — the candidate is
  performing; the interface must recede. Preparation, evidence, and progress
  are reading/analysis surfaces.
- **Voice presence**: the live interview communicates interviewer state
  (listening/speaking/thinking/processing) clearly but calmly; errors
  (mic permission, device unavailable) are actionable, not generic.

Current UI (as of `ui-revamp`, verified): dark-flagship editorial
instrument-panel language — flat semantic surfaces, hairline borders, one
accent, tabular numerals for measurements, small consistent radii, motion
only where meaningful, `prefers-reduced-motion` respected, Dark/Light/System
themes. 14 screens (see §7).

---

## 6. What Must Never Be Compromised

- **Evidence integrity**: no fabricated experience, achievements, skills,
  or interview history. Inference is never presented as fact.
- **Honest measurement**: readiness/progress/scores are deterministic and
  reproducible; variance in AI judgments is recorded, not gamed.
- **Voice correctness**: stale TTS after interruption is a bug; duplicate
  answer submission is a bug; uncontrolled background audio is a bug.
- **Privacy**: candidate content (resumes, transcripts, audio) is sensitive;
  observability carries IDs + redacted metadata, never raw content.
- **Single-user local reality**: the product must not pretend to be a
  multi-tenant SaaS; deployment is a local instrument.

---

## 7. Current Product Surface (verified inventory)

Navigation shell (AppShell): primary — Overview (dashboard), Preparation,
Practice, Evidence, Progress; secondary — Profile, History, Settings,
Runtime; plus Report/Transcript/Debrief reachable from history.

| Surface | Route | Purpose |
|---|---|---|
| Overview (dashboard) | `/dashboard` | Where am I: readiness verdict, confidence, evidence coverage, critical gaps, next action |
| Candidate setup | `/setup` | First-run bootstrap: profile, resume, JD |
| Profile workspace | `/profile` | Multi-profile CRUD, preferred resume/JD per profile, documents, roles, evidence, switcher |
| Preparation | `/preparation` | Gap analysis → today's practice queue with reasons; pre-flight briefing |
| Practice (interview) | `/interview` | Flagship: 8 modes, adaptive questions, hints, live transcript; text and voice workspaces |
| Interview report | `/interview/:id/report` | Coach-style report: scores, strengths/weaknesses, evidence, follow-ups |
| Transcript | `/interview/:id/transcript` | Durable per-session record |
| Evidence | `/evidence` | Evidence ledger with provenance |
| Progress | `/progress` | Longitudinal trends, strengths, recurring issues |
| Stories | `/stories` | STAR story bank |
| History | `/history` | Past sessions → report/transcript/debrief |
| Debriefs | `/debriefs` | Real-interview debrief ingestion + analysis |
| Settings | `/settings` | Theme, demo data, model/provider configuration |
| Runtime | `/models` | Provider health + model inventory + routing status |

---

## 8. Voice — Product-Grade Requirements

- Server-authoritative states: idle → starting → listening → processing →
  speaking (+ paused / interrupted / cancelled / completed / error).
- Interruption, pause, resume, stop, cancel, reconnect all work; stale TTS
  never plays after interrupt; reconnect resumes from persisted state.
- Turn finalization: automatic (speech detection + silence watchdog) and
  manual ("Done speaking").
- Degradation is explicit, never silent: TTS down → text interviewer
  response; ASR down → typed transcript mode.
- Audio persistence is opt-in with a retention policy; candidate audio is
  sensitive data.

---

## 9. Non-Goals (V1 — do not design for these)

No video, no executable coding sandbox, no whiteboard canvas, no
anti-cheating/browser monitoring, no recruiter platform, no enterprise
teams, no payments, no mobile apps, no LinkedIn integration/scraping, no
per-user account system.

---

## 10. Open Product Questions (for the redesign — decisions deferred)

These are product-level questions the redesign must answer (or consciously
accept), not visual ones:

1. How prominently should the **evidence ledger** be surfaced relative to
   readiness numbers? (Evidence-first vs verdict-first hierarchy.)
2. Is the dashboard a single "instrument panel" or a layered
   at-a-glance → drill-in structure?
3. How should the **practice workspace** balance interview performance
   (focus) with evaluation feedback (analysis) — separate phases or
   side-by-side?
4. What is the product's information architecture for 14 screens: is the
   current 5-primary/4-secondary nav the right model?
5. How should **voice interview** presence be communicated when the
   interviewer is thinking/processing (no audio yet)?
6. Where does the product draw the line between "AI coach" voice and
   "instrument" voice in copy and tone?
