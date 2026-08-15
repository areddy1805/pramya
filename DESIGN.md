# Pramya — Frontend Design Contract (The Drawing Sheet)

**Status: FROZEN.** This document describes the visual system that actually
exists in the code, surface by surface. It is the permanent design contract.
Do not treat it as aspirational. If code and this document disagree, the
code is the source of truth and this document must be updated to match.

The purpose of this document is to prevent future agents from destroying
the visual language. The nine primary surfaces and the five secondary
surfaces are frozen references — **do not redesign them**; make new work
belong to the same system.

---

## 1. Visual philosophy

Pramya is an evidence-driven interview preparation instrument, not a
chatbot wrapper and not a SaaS dashboard. The interface is an engineering
drawing sheet: every screen is a **technical document** — an operational
record, a ledger, a specification, a work order — drawn with drafting
grammar. The application should read as one coherent engineered instrument,
never as a collection of individually designed AI-generated pages.

Core principles:

- **One raking light.** The active region of each sheet is lit; supporting
  regions fall into shadow. Exactly one region carries the work.
- **Explicit absence.** Unachieved/unmeasured evidence is drawn as ghost
  cells (dashed notation), never as a void and never as a zero.
- **Honesty.** Never fabricate a metric, status, timestamp, or record. If
  the backend does not provide something, represent its absence explicitly
  (`—`, `NOT ASSESSED`, `No history recorded`, `not analyzed`).
- **Fixed scales.** Every measurement registers on a shared, fixed axis.
  Bars are never re-scaled per row.
- **Dense information where density is justified**; deliberate empty space
  elsewhere. No decorative filler.
- **Deterministic classification.** Status words carry meaning
  (PASS/WARNING/FAIL, OPERATIONAL/DEGRADED); color + text together, never
  color alone.

## 2. The Drawing Sheet canon

Locked direction: engineering drafting / blueprint ("The Drawing Sheet",
`.impeccable/decision-direction.json`). Grammar contract:

- one coherent grid (24px ruling, zones align to it)
- ink linework with weight = meaning
- drafting blue = measured/active/positive
- red/orange (redline) = genuine failure/degraded/correction only
- ghost cells: absence drawn as deliberately as achievement
- provenance via line style: dotted = claimed, dashed = observed,
  solid = demonstrated
- redline grammar: circled markers, leader lines, severity via line
  treatment (solid Δ≥3 · dashed 2–2.9 · dotted <2)
- stable title-block legend that never moves
- revision strip at the sheet foot with real values only

## 3. Page shell

- `AppShell` (frontend/src/components/AppShell.tsx): sticky header `h-11`,
  `max-w-6xl`, glass chrome, primary nav (Overview, Preparation, Practice,
  Evidence, Progress) + secondary nav (Profile, History, Settings, Runtime).
  Active route: ink text + 1px accent underline. Mobile: horizontal scroll
  row under the header.
- Main: `mx-auto max-w-6xl px-4 py-6 sm:px-6`.
- Every surface renders as one `Sheet` (`sheet-grid` background, hairline
  `border-ink/30`), full width of the main column.

## 4. Title block

Every sheet opens with a title block:

```
Pramya · {Surface} · {Kind}      [state cell]
{Page title} (h1, text-xl)        STATUS STENCIL
supporting copy (13px, ink-2)     label / value rows
```

- Eyebrow: 10px, uppercase, `tracking-[0.14em]`, `text-ink-2`.
- h1: `text-xl font-semibold tracking-tight text-ink` (frozen pages only;
  no oversized SaaS headings).
- Right state cell: `w-full border border-ink/30 bg-sheet-lit/45 px-4 py-3
  sm:w-[17rem]`, status stencil top-right (draft = good, redline = failure,
  ink-3 = absent), then hairline-separated stencil label/value rows.
  Values are `—` when not derivable. Example cells: VerdictStamp,
  QueueStamp, Record State, Configuration State, Runtime State,
  Initiation State, Assessment State, Findings State, Library State.

## 5. Typography

- Fonts: Inter + JetBrains Mono are named in tokens but **not loaded** —
  the app renders system fallbacks. Do not add a font loader without an
  explicit product decision.
- Hierarchy: eyebrow (10px caps) → h1 (20px) → section title (10px caps,
  `tracking-[0.14em]`) → body (13–15px) → metadata (10–11px stencil caps) →
  dense technical values (10px mono, `text-ink-3`).
- `.stencil`: mono, 600 weight, tabular, tight tracking — used for labels,
  numerals, status words, revision lines. **Do not turn every text into a
  stencil label**; prose stays in the sans stack.
- Typography floor: 10px for labels; the 9px circled RedlineMarker digit is
  the only exception.
- No amber exists in the sheet world. WARNING is carried by the word
  (`text-ink`/`text-ink-2` + text), never by a yellow hue.

## 6. Color / status semantics

Tokens in `frontend/src/index.css` (`:root` light, `.dark` overrides,
mapped through `@theme inline`):

| Token   | Light (paper)            | Dark (drafting field)   | Meaning                  |
|---------|--------------------------|-------------------------|--------------------------|
| `--sheet`    | #eae7dc warm paper | #10151d navy field | surface |
| `--sheet-lit`| #f3f0e4              | #171e29             | active region |
| `--sheet-shadow` | #dedbcd          | #0b0f16             | supporting region |
| `--ink`       | #1b2733            | #dfe7f0             | primary text/line |
| `--ink-2`     | #46525f            | #93a0b0             | secondary text |
| `--ink-3`     | #77808c            | #5d6877             | metadata/absent |
| `--draft`     | #2f5d8a            | #7fb0dd             | positive/active/measured |
| `--draft-2`   | #1f4266            | #a3c8ea             | positive emphasis |
| `--redline`   | #b23c22            | #e07a52             | failure/degraded only |
| `--graphite`  | #8a8f98            | #8a8f98             | neutral/unknown |

Status vocabulary (word + color, never color alone):

- Readiness: PASS (≥7, draft) / WARNING (≥4, ink) / FAIL (<4, redline) /
  NOT_ASSESSED (unmeasured — shows `N/A`, never `0.0`).
- Report: thresholds are the report's own (≥7.5 strong / ≥5 foundation /
  <5 weak).
- Transcript: ≥7 draft / ≥4 ink / <4 redline.
- Runtime: OPERATIONAL (draft) / DEGRADED (redline) / UNAVAILABLE
  (redline) / UNKNOWN (graphite).
- Queue: NO TARGET ROLE / NOT ASSESSED / QUEUE NOT GENERATED /
  NO OPEN ORDERS / ORDER ISSUED.

## 7. Grid / background

- `.sheet-grid`: 24px linear-gradient ruling on the sheet background.
- `.hatch`: 45° drafting hatching used to fill measured bars
  (CoverageHatch, FixedScaleBar, dimension bars).
- Registration: shared columns use explicit grid templates, e.g.
  BOM rows `grid-cols-[2.25rem_minmax(0,1fr)_2.75rem_3rem]`, competency
  bands `grid-cols-[7.5rem_minmax(0,1fr)_5rem]`. The same template is
  used for header + rows so columns register.

## 8. Borders / spacing

- Hairlines everywhere: `border-ink/10` (row rules), `border-ink/15`
  (subtle), `border-ink/20` (sections), `border-ink/25` (title/revision
  strips), `border-ink/30` (inputs, cells).
- Sheet padding: `px-6 pb-4 pt-5` title block; `px-6` section content;
  `px-6 pb-4 pt-3` revision strip.
- No default shadows; the only ring is `--focus-ring` on focus.

## 9. Section architecture

`SheetSection` (frontend/src/components/sheet.tsx): a bounded region with
a 10px caps title + right aside, tones `flat` / `lit` (active) / `shadow`
(supporting). Sections stack top-down; a lit section carries the work.

Shared primitives (sheet.tsx):

- `Sheet`, `SheetSection`, `StencilNum`
- `LevelCells` (5-cell evidence strip, ghost = dashed), `Ruler`
  (fixed 0–5 axis), `DimensionLine` (provenance arrowhead line),
  `CoverageHatch` (0–100% hatch bar)
- `ProvenanceLegend` (claimed/observed/demonstrated + not-yet-evidenced)
- `VerdictStamp`, `QueueStamp`
- `RedlineMarker`, `RedlineCallout`, `RedlineSeverityKey`
- `PartsListHeader`, `PartsRow` (BOM rows), `FixedScaleBar`

## 10. Records / ledgers

Ledgers are the primary data structure: numbered rows, hairline `border-b
border-ink/10`, stencil index numerals, stencil status/kind labels,
metadata in `text-ink-3`. Desktop uses registered column grids; mobile
collapses to vertical records with the same data (never a horizontally
scrolling table).

## 11. Forms / controls

- Sheet inputs: `h-9 border border-ink/30 bg-sheet px-3 text-sm`,
  `focus:border-draft` + `--focus-ring`; selects and textareas share the
  same family (textareas `px-3 py-2.5`).
- Buttons: `ui.tsx` Button (primary/secondary/ghost/danger) is used on
  frozen pages. The pre-flight IssueControl (draft-blue engineering
  control) and stencil text links (`text-draft underline underline-offset-2`)
  are the sheet-native alternatives. No pill buttons, no glow, no gradients.
- Uploads: bordered label+file-input controls.
- No unnecessary controls. If an interaction does not exist in the data
  model, do not add a control for it.

## 12. States

- **Loading**: skeleton rows inside the preserved section structure —
  never a giant centered spinner. In-flight actions show stencil/spinner
  labels (`checking provider health…`, `Analyzing…`).
- **Error**: `ErrorState` block inside the sheet with title, message, and
  retry; the surrounding record structure stays visible. Failed backend
  calls never destroy page structure.
- **Empty**: ghost frame — `border border-dashed border-ink/25` with a
  stencil statement (`No history recorded`, `No evidence yet`,
  `NOT ASSESSED`), dashed skeleton shapes, and honest copy explaining what
  is missing and what to do.
- **Partial/unavailable**: explicit `—`, `not analyzed`, `not uploaded`,
  `no overall score`. Absence is drawn, never hidden, never faked.
- **Disabled**: `disabled:cursor-not-allowed` + reduced opacity; disabled
  reasons are visible.

## 13. Interaction

- Quiet and precise. Hover/focus reveals affordances (e.g. `→ detail`,
  `→ ledger`) without hover being required for comprehension.
- Keyboard navigation + visible `--focus-ring` on all controls; semantic
  HTML (buttons vs links, `role=radio` + `aria-checked`, labels, disabled
  states). `prefers-reduced-motion` disables all animation
  (index.css global override).
- No interaction purely for visual polish.

## 14. Responsive

- Desktop ≥ ~1280 (sheet full width), laptop, 375px mobile.
- Zero horizontal overflow at 375px (verified per surface).
- Mobile rules: title cell goes full width (`w-full sm:w-[17rem]`),
  ledgers become vertical records (wrapper column + `md:hidden` cells,
  e.g. History/Evidence/Runtime), grids stack, revision strips wrap.
- Do not solve mobile by shrinking desktop; the hierarchy (question field /
  primary action / instrument) must survive.

## 15. Dark / light

- Dark is the default (drafting field) and the signature theme; light is a
  true counterpart (warm paper, dark ink, drafting blue) — not an
  afterthought and not a trivial inversion.
- The same grammar, tokens, and hierarchy must survive both. No pure-black
  hacker aesthetics, no neon glow, no washed-out light mode.

## 16. Footer / revision strip

Every sheet ends with a revision strip (`border-t border-ink/25 px-6 pb-4
pt-3`): stencil 10px caps, left = real facts (`profile X · N records · span
· drawn {date}`), right = a scope-honesty note (`configuration is global…`,
`every numeral comes from the backend report…`). Values are real or `—`;
never invent a workspace fact.

## 17. Surface register (frozen)

Primary (do not touch except genuine shared-primitive bugs):

| Surface | Route | Record | Commit |
|---|---|---|---|
| Overview | /dashboard | dimensioned readiness drawing + BOM + redlines | f6061eb |
| Preparation | /preparation | work order + queue schedule | 3773d3f |
| Practice | /interview | live field sheet (dark-first) | e3c3d9b |
| Evidence | /evidence | evidence ledger (view cap 200) | 595db0b |
| Progress | /progress | longitudinal measurement record | bbb8a86 |
| Profile | /profile | candidate dossier | 3c27fea |
| History | /history | audit ledger + server paging | ae5169b, a9ce802 |
| Settings | /settings | workspace configuration record | a985e35 |
| Runtime | /models | operations inspection record | 88bf5e6 |

Secondary (same grammar, subordinate records):

| Surface | Route | Record |
|---|---|---|
| Setup | /setup | workspace initialization record |
| Report | /interview/:id/report | assessment document |
| Transcript | /interview/:id/transcript | source interview record |
| Debrief | /debriefs | post-interview findings |
| Stories | /stories | evidence story library |

Consistency rule: pages share grammar, not cloned layouts. A report is a
document, a debrief is a findings ledger, the practice screen is a field
sheet — each keeps its own hierarchy inside the same instrument family.

## 18. What NOT to introduce

- cards-as-dashboard / card walls / KPI tiles
- gradients, glassmorphism, decorative blobs, glow, neon
- arbitrary rounded rectangles, pill buttons, excessive radius
- decorative illustrations or icons (including emoji)
- a new color palette (no amber; redline only for real failure)
- a new typography system; arbitrary font sizes/weights
- arbitrary animation (motion only communicates state transitions)
- fabricated data, metrics, statuses, timestamps, records, CRUD
- new dependencies, new design systems, second visual worlds
- duplicate tokens or second implementations of sheet grammar
  (reuse sheet.tsx + index.css; page-local primitives only when the
  surface genuinely requires them)

## 19. Validation

Before any UI change: `npx tsc -b`, `npm run build`, `npx oxlint`, then
per-surface DOM probes at 1440 and 375 (overflowX = 0, focus visibility,
status semantics, reduced motion, no console errors) and dark+light
screenshots. Frozen pages must be smoke-checked after any shared
primitive/token change.
