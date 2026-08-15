# Dashboard surface brief — Pramya

## Scope and mode
- Scope: `/dashboard` (Overview) — the first surface built in the new visual world; sets the grammar every other screen inherits.
- Mode: **Operate** — the visitor reads an instrument and acts. Scanability and real usage scene outrank expression.

## Audience, job, task
- **Audience**: Alex — senior engineer prepping alone at night for a high-stakes interview; the scene is dim, quiet, headphones nearby. Single-user local instrument.
- **Job**: "Where am I, what's the gap, what do I do next" — in under 30 seconds, with every number traceable.
- **Action**: read the readiness verdict → inspect the redlined gaps → open the parts list → start practice.

## Proof / content
- The verdict is deterministic (evidence coverage × importance × recency × demonstrated ability), never "LLM → 8/10". Every dimension must carry its evidence chain (provenance ladder claimed → observed → demonstrated → inferred → unknown).
- Absence of evidence is explicit: unachieved coverage renders as a ghost cell, never a void.

## Constraints
- No fabricated evidence; no fake certainty; no gamification; calm instrument tone; Dark/Light/System themes; `prefers-reduced-motion` respected; 14 screens total — dashboard grammar must extend to interview workspace, evidence, progress, report.
- Voice states are server-authoritative; the dashboard never pretends a live session state.

## Chosen direction (locked 2026-08, decision page .impeccable/decision-direction.json)
- **The Drawing Sheet** — engineering drafting & blueprint world. Readiness = dimensioned instrument reading.
- Palette: paper `#e8e4d8`, ink navy `#14202e`, drafting blue `#2f5d8a`, redline `#c0502e`, graphite `#8a8f98`. Materials: blueprint mylar, india-ink linework, stencil numerals, redline pencil, one raking light.
- **Memorable moment**: the measure tool — hover any dimension, evidence chain draws as leader lines; provenance = line style (dotted claimed / dashed observed / solid demonstrated).
- Composition: title block (verdict stencil) top; readiness drawing center (dimensioned orthographic competency view, coverage hatching); redline gap callouts right; parts list (prep queue) left; revision strip bottom.

## Unresolved decisions
- Fonts (candidates: drafting-adjacent sans + mono for numerals; pick at build).
- Light/dark split across surfaces (draft paper is light-first; interview "field" sheet may go dark — decide at build).
- Exact nav labels in instrument grammar (Status/Readiness, Prepare, Interview, Ledger, Trend).

## Direction contract reference
- Build path: code-led (no image generation). Raises named in decision payload: light discipline, ghost cells, fixed-scale comparison, ruled vertical axis, strict grid, stable legend. DESIGN.md written at finish from the built world.
