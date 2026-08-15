# ADR-029 — Frontend Visual Canon: The Drawing Sheet, Frozen

Status: Accepted (2026-08-15)
Scope: Frontend / UI-UX

## Context

Pramya's frontend was rebuilt surface-by-surface during the UI revamp
(branch `ui-revamp`). Each of the fourteen routes needed to read as one
coherent engineered instrument — an evidence-driven interview preparation
platform, not an AI SaaS dashboard. The direction was chosen through the
Impeccable new-work flow and confirmed by the user: engineering
drafting/blueprint — **The Drawing Sheet** (see `DESIGN.md`, the permanent
design contract).

After all fourteen surfaces were built and frozen, two final corrections
were authorized and completed:

1. **Secondary navigation discoverability** — five routes (Setup, Report,
   Transcript, Debrief, Stories) existed but had no visible navigation
   entry. Added a `More ▾` disclosure in the shell.
2. **Visual density refinement** — the interface was structurally coherent
   but visually too busy (grid prominence, repeated rules, competing
   micro-labels). Reduced perceived density without redesign.

## Decision

1. **The Drawing Sheet is the frozen visual canon.** Nine primary surfaces
   (Overview, Preparation, Practice, Evidence, Progress, Profile, History,
   Settings, Runtime) and five secondary surfaces (Setup, Report,
   Transcript, Debrief, Stories) share one grammar: 24px sheet grid, hairline
   ink rules, drafting blue for positive/measured, redline for genuine
   failure only, provenance line styles (dotted claimed / dashed observed /
   solid demonstrated), ghost cells for explicit absence, title block +
   state cell, revision strip, fixed-scale measurement, stencil numerals.
   Dark = navy drafting field (default); light = warm paper.
   `DESIGN.md` is the contract and the source of truth; the code wins on
   disagreement.

2. **Navigation.** Primary and secondary nav labels/order unchanged; the
   `More ▾` menu (same nav vocabulary, keyboard complete, mobile-safe
   fixed positioning) exposes the five secondary routes. Report/Transcript
   resolve to the most recent real session (Report → latest completed);
   disabled with an honest note when no session exists.

3. **Density.** Grid alpha lowered (light 0.035 / dark 0.04); three-tier
   rule hierarchy (/25 primary, /10 secondary, /5 tertiary row rules);
   micro-labels as annotations (font-medium, 0.12em, ink-2/70; asides at
   ink-3); `.stencil` weight 500; redline markers outlined not filled.
   See DESIGN.md §20. This is a refinement of the canon, not a redesign —
   it is now part of the canon.

## Consequences

- Frozen surfaces are not to be redesigned; changes only for genuine
  shared-primitive bugs, with the smallest possible correction.
- Any new UI must belong to the same system; "what NOT to introduce" is
  enumerated in DESIGN.md §18 (no cards-as-dashboard, gradients, glass,
  new palettes, decorative icons/emoji, fabricated data, new dependencies).
- No backend/API/data-contract changes were made during the frontend
  freeze; all validation was deterministic (tsc/build/oxlint, DOM probes at
  1440 + 375, dark + light, overflowX = 0, focus, reduced motion).
- Impeccable detector: clean on all 14 rendered surfaces; one advisory
  (`codex-grid-background` on `.sheet-grid`) rejected as intentional canon.

## Commits

f948214, f6061eb, 3773d3f, e3c3d9b, 595db0b, bbb8a86, 3c27fea, ae5169b,
a9ce802, a985e35, 88bf5e6 (primary), 90bd43c (secondary surfaces +
DESIGN.md), c41690b (More ▾ navigation), be87af6 (density pass).
