// Drawing-sheet primitives — the drafting grammar shared by sheet surfaces.
//
// Grammar contract (locked direction, .impeccable/decision-direction.json):
//  - one coherent grid (24px ruling, zones align to it)
//  - ink linework with weight = meaning; drafting blue = measured/active
//  - redline = correction/attention only, drawn with drafting grammar:
//    circled revision markers, leader lines, severity via line treatment
//  - ghost cells: unachieved evidence drawn as dashed notation (explicit
//    absence, never a void)
//  - provenance via line style: dotted = claimed, dashed = observed,
//    solid = demonstrated
//  - one raking light: the active region (lit tone) carries the work;
//    side regions fall into their own shadow
//  - fixed scale: every measurement registers on one shared axis/ruler
//
// Components consume the sheet tokens (--sheet/--ink/--draft/--redline),
// never raw colors.

import type { ReactNode } from 'react'
import { Skeleton } from './ui'

export type Provenance = 'claimed' | 'observed' | 'demonstrated'

// --- The sheet ---------------------------------------------------------------

export function Sheet({
  children,
  className = '',
  'aria-label': ariaLabel,
}: {
  children: ReactNode
  className?: string
  'aria-label'?: string
}) {
  return (
    <div aria-label={ariaLabel} className={`sheet-grid border border-ink/30 bg-sheet text-ink ${className}`}>
      {children}
    </div>
  )
}

// A bounded region of the sheet. tone controls the raking light:
// lit = the working region, shadow = supporting regions, flat = neutral.
export function SheetSection({
  title,
  aside,
  tone = 'flat',
  className = '',
  children,
}: {
  title: string
  aside?: ReactNode
  tone?: 'flat' | 'lit' | 'shadow'
  className?: string
  children: ReactNode
}) {
  const tones = {
    flat: '',
    lit: 'bg-sheet-lit/55',
    shadow: 'bg-sheet-shadow/40',
  }[tone]
  return (
    <section className={`relative flex flex-col border-ink/20 ${tones} ${className}`}>
      <header className="flex items-baseline justify-between gap-3 px-6 pb-2.5 pt-4">
        <h2 className="text-[10px] font-medium uppercase tracking-[0.12em] text-ink-2/70">{title}</h2>
        {aside ? <div className="shrink-0 text-ink-3">{aside}</div> : null}
      </header>
      <div className="min-w-0 flex-1 px-6 pb-5">{children}</div>
    </section>
  )
}

// --- Measurement voice -------------------------------------------------------

export function StencilNum({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <span className={`stencil ${className}`}>{children}</span>
}

// 5-cell evidence strip, registered to the drawing ruler (same 5 equal
// columns). Filled cell = achieved; dashed-outline cell = ghost (absence
// drawn as deliberately as achievement). The seven-seg raise.
export function LevelCells({ level, tone = 'ink', className = '' }: { level: number; tone?: 'ink' | 'draft' | 'redline'; className?: string }) {
  const filled = {
    ink: 'border-ink bg-ink',
    draft: 'border-draft bg-draft',
    redline: 'border-redline bg-redline',
  }[tone]
  const clamped = Math.max(0, Math.min(5, level))
  return (
    <span role="img" aria-label={`${clamped} of 5 demonstrated`} className={`grid grid-cols-5 items-center gap-x-2 ${className}`}>
      {Array.from({ length: 5 }, (_, i) => (
        <span
          key={i}
          aria-hidden
          className={`h-3 w-3 justify-self-center border ${i < clamped ? filled : 'border-dashed border-ink/45 bg-transparent'}`}
        />
      ))}
    </span>
  )
}

// Horizontal dimension line with drafting arrowheads. Line weight and
// continuity carry provenance: dotted = claimed, dashed = observed,
// solid = demonstrated.
export function DimensionLine({ style, className = '' }: { style: Provenance; className?: string }) {
  const line = {
    claimed: 'border-t border-dotted border-ink/45',
    observed: 'border-t border-dashed border-ink/65',
    demonstrated: 'border-t-2 border-solid border-ink/90',
  }[style]
  const ink = {
    claimed: 'text-ink/45',
    observed: 'text-ink/65',
    demonstrated: 'text-ink/90',
  }[style]
  return (
    <span aria-hidden className={`relative flex h-2.5 items-center ${className}`}>
      <span className={`w-full ${line}`} />
      <svg viewBox="0 0 8 8" className={`absolute -left-1.5 top-1/2 h-2 w-2 -translate-y-1/2 ${ink}`}>
        <path d="M8 4 L0 0 V8 Z" fill="currentColor" />
      </svg>
      <svg viewBox="0 0 8 8" className={`absolute -right-1.5 top-1/2 h-2 w-2 -translate-y-1/2 ${ink}`}>
        <path d="M0 4 L8 0 V8 Z" fill="currentColor" />
      </svg>
    </span>
  )
}

// Shared measurement axis: one ruled line with registration ticks. All
// evidence cells on the sheet register against these tick positions.
export function Ruler({ className = '' }: { className?: string }) {
  return (
    <div aria-hidden className={className}>
      <div className="relative h-2.5">
        <div className="absolute inset-x-0 top-0 border-t border-ink/60" />
        {Array.from({ length: 6 }, (_, i) => (
          <span key={i} className="absolute top-0 h-2.5 w-px bg-ink/50" style={{ left: `${(i / 5) * 100}%` }} />
        ))}
      </div>
      <div className="stencil mt-1 flex justify-between text-[10px] leading-none text-ink-2">
        {Array.from({ length: 6 }, (_, i) => (
          <span key={i}>{i}</span>
        ))}
      </div>
    </div>
  )
}

// Coverage hatch — bounded bar filled with drafting hatching; density
// communicates the fraction of required evidence present.
export function CoverageHatch({ value, showLabel = true }: { value: number; showLabel?: boolean }) {
  const pct = Math.round(Math.max(0, Math.min(1, value)) * 100)
  return (
    <span className="flex items-center gap-1.5" title={`Evidence coverage ${pct}%`}>
      <span aria-hidden className="relative h-3 w-16 overflow-hidden border border-ink/30 bg-transparent">
        <span className="absolute inset-y-0 left-0 hatch text-draft" style={{ width: `${pct}%` }} />
      </span>
      {showLabel ? <span className="tabular text-[10px] text-ink-3">{pct}% cov</span> : null}
    </span>
  )
}

// --- Provenance legend (stable, lives in the title block) --------------------

export function ProvenanceLegend() {
  const line: Record<Provenance, string> = {
    claimed: 'border-t border-dotted border-ink/50',
    observed: 'border-t border-dashed border-ink/65',
    demonstrated: 'border-t-2 border-solid border-ink/90',
  }
  const items: Array<{ style: Provenance; label: string }> = [
    { style: 'claimed', label: 'claimed' },
    { style: 'observed', label: 'observed' },
    { style: 'demonstrated', label: 'demonstrated' },
  ]
  return (
    <ul className="flex flex-wrap items-center gap-x-5 gap-y-1.5 text-[10px] font-medium uppercase tracking-[0.08em] text-ink-2">
      {items.map((i) => (
        <li key={i.label} className="flex items-center gap-1.5">
          <span aria-hidden className={`w-7 ${line[i.style]}`} />
          {i.label}
        </li>
      ))}
      <li className="flex items-center gap-1.5">
        <span aria-hidden className="inline-block h-3 w-3 border border-dashed border-ink/45 bg-transparent" />
        not yet evidenced
      </li>
    </ul>
  )
}

// --- Verdict stamp -----------------------------------------------------------

// The primary measurement, stamped into the title block: one stencil
// numeral plus a measurement note (confidence · coverage · gaps · date).
// Status is honest per Pramya semantics: NOT_ASSESSED when no deterministic
// measurement exists (an empty/zeroed snapshot is NOT a verified zero),
// otherwise PASS / WARNING / FAIL from the measured value. An unmeasured
// profile never shows a numeral that could read as a score of zero.
export function VerdictStamp({
  value,
  assessed,
  confidence,
  coverage,
  gapCount,
  date,
  loading = false,
}: {
  value: number | null
  assessed: boolean
  confidence: number
  coverage: number
  gapCount: number
  date: string
  loading?: boolean
}) {
  const pct = (n: number) => `${Math.round(n * 100)}%`
  const measured = assessed && value != null
  const status = !measured ? 'NOT_ASSESSED' : value >= 7 ? 'PASS' : value >= 4 ? 'WARNING' : 'FAIL'
  const statusTone = !measured ? 'text-redline' : value >= 7 ? 'text-draft' : value >= 4 ? 'text-ink-2' : 'text-redline'
  const numeralTone = !measured ? 'text-ink-3' : value >= 7 ? 'text-draft' : value >= 4 ? 'text-ink' : 'text-redline'
  return (
    <div className="w-full border border-ink/30 bg-sheet-lit/45 px-5 py-4 sm:w-[19rem]">
      <div className="flex items-baseline justify-between gap-3">
        <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-ink-2">Overall readiness</p>
        {loading ? null : (
          <span className={`stencil text-[10px] uppercase tracking-[0.16em] ${statusTone}`}>{status}</span>
        )}
      </div>
      <div className="mt-2 flex items-baseline gap-1.5">
        {loading ? (
          <Skeleton className="h-16 w-36" />
        ) : (
          <>
            <span className={`stencil text-6xl leading-none sm:text-7xl ${numeralTone}`}>
              {measured ? value.toFixed(1) : 'N/A'}
            </span>
            <span className="text-sm text-ink-2">/ 10</span>
          </>
        )}
      </div>
      <p className="stencil mt-3 border-t border-ink/15 pt-2.5 text-[10px] uppercase leading-relaxed tracking-[0.08em] text-ink-3">
        conf {measured ? pct(confidence) : '—'} · cov {measured ? pct(coverage) : '—'} · gaps {measured ? gapCount : '—'}
        <br />
        drawn {date}
      </p>
    </div>
  )
}

// --- Queue status stamp ------------------------------------------------------

// The work-order status, stamped into the preparation sheet's title block.
// Parallel to VerdictStamp but measures the ORDER, not the drawing: open
// order count, estimated effort, and estimated readiness movement (the
// deterministic sum of each order's expected_improvement — an estimate,
// never a guarantee). Status labels are honest per Pramya semantics:
// NOT ASSESSED / NO TARGET ROLE / QUEUE NOT GENERATED / NO OPEN ORDERS /
// ORDER ISSUED. No issued order ever shows a numeral that could read as
// a measured zero.
export function QueueStamp({
  openCount,
  minutes,
  gain,
  date,
  status,
  statusTone,
  loading = false,
}: {
  openCount: number | null
  minutes: number | null
  gain: number | null
  date: string
  status: string
  statusTone: 'draft' | 'redline' | 'ink-2' | 'ink-3'
  loading?: boolean
}) {
  const tone = {
    draft: 'text-draft',
    redline: 'text-redline',
    'ink-2': 'text-ink-2',
    'ink-3': 'text-ink-3',
  }[statusTone]
  return (
    <div className="w-full border border-ink/30 bg-sheet-lit/45 px-5 py-3 sm:w-[19rem]">
      <div className="flex items-baseline justify-between gap-3">
        <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-ink-2">Work order · queue status</p>
        {loading ? null : <span className={`stencil text-[10px] uppercase tracking-[0.16em] ${tone}`}>{status}</span>}
      </div>
      <div className="mt-2">
        <p className="stencil text-[10px] uppercase tracking-[0.12em] text-ink-2">Σ est. movement · full order</p>
        <div className="mt-0.5 flex items-baseline gap-1.5">
          {loading ? (
            <Skeleton className="h-12 w-28" />
          ) : (
            <>
              <span className={`stencil text-4xl leading-none sm:text-5xl ${gain != null ? 'text-draft' : 'text-ink-3'}`}>
                {gain != null ? `+${gain.toFixed(1)}` : '—'}
              </span>
              <span className="text-[10px] uppercase tracking-[0.08em] text-ink-2">if completed</span>
            </>
          )}
        </div>
      </div>
      <p className="stencil mt-3 border-t border-ink/15 pt-2.5 text-[10px] uppercase leading-relaxed tracking-[0.08em] text-ink-3">
        {openCount != null ? `${openCount} open` : 'open —'} · {minutes != null ? `≈ ${minutes} min` : '≈ — min'}
        <br />
        drawn {date}
      </p>
    </div>
  )
}

// --- Redline grammar ---------------------------------------------------------

// Circled revision marker — the reference symbol that links a redline
// callout in the margin back to its competency in the drawing.
export function RedlineMarker({ index }: { index: number }) {
  return (
    <span
      aria-hidden
      className="stencil grid h-4 w-4 shrink-0 place-items-center rounded-full border border-redline/80 text-[9px] leading-none text-redline"
    >
      {index}
    </span>
  )
}

// Redline callout: circled number, leader line with arrowhead, short
// annotation. Severity is encoded through the leader treatment itself:
// solid = gap ≥ 3, dashed = 2–2.9, dotted = < 2. No card chrome.
export function RedlineCallout({
  index,
  name,
  demonstrated,
  required,
  gap,
}: {
  index: number
  name: string
  demonstrated: number
  required: number
  gap: number
}) {
  const severe = gap >= 3
  const mid = gap >= 2
  const leader = severe
    ? 'border-t border-redline'
    : mid
      ? 'border-t border-dashed border-redline/75'
      : 'border-t border-dotted border-redline/60'
  const ink = severe ? 'text-redline' : mid ? 'text-redline/80' : 'text-redline/60'
  const ring = severe
    ? 'border-redline bg-redline/10 text-redline'
    : mid
      ? 'border-redline/80 text-redline'
      : 'border-redline/60 text-redline/70'
  return (
    <li className="py-2.5">
      <span className="sr-only">
        Gap {index}: {name}, demonstrated {demonstrated} of {required} required, delta {gap.toFixed(1)}.
      </span>
      <div className="flex items-center gap-2.5">
        <span aria-hidden className={`stencil grid h-5 w-5 shrink-0 place-items-center rounded-full border text-[10px] leading-none ${ring}`}>
          {index}
        </span>
        <span aria-hidden className={`relative flex-1 ${leader}`}>
          <svg viewBox="0 0 8 8" className={`absolute -right-1.5 -top-[3px] h-2 w-2 ${ink}`}>
            <path d="M0 4 L8 0 V8 Z" fill="currentColor" />
          </svg>
        </span>
        <p className="min-w-0 shrink-0 truncate text-[13px] font-semibold text-ink">{name}</p>
      </div>
      <p className="tabular mt-1 pl-8 text-[11px] text-ink-2">
        now {demonstrated}/5 → req {required}/5
      </p>
      <p className={`stencil mt-0.5 pl-8 text-[11px] ${severe ? 'text-redline' : 'text-redline/80'}`}>Δ {gap.toFixed(1)}</p>
    </li>
  )
}

// Key explaining the redline severity encoding (shown when gaps exist).
export function RedlineSeverityKey() {
  return (
    <p className="stencil mt-3 border-t border-ink/15 pt-2.5 text-[10px] uppercase leading-relaxed tracking-[0.1em] text-ink-3">
      leader · solid Δ≥3 · dashed 2–2.9 · dotted &lt;2
    </p>
  )
}

// --- Parts list (preparation queue as BOM schedule) --------------------------

// Tabular bill-of-materials row: item number · part · priority · estimate.
// Hairlines only — no card chrome. The designated NEXT item takes a lit
// tint plus a stamped NEXT tag.
export function PartsRow({
  index,
  name,
  reason,
  minutes,
  priority,
  next = false,
}: {
  index: string
  name: string
  reason?: string | null
  minutes?: number | null
  priority: number
  next?: boolean
}) {
  return (
    <li className={`grid grid-cols-[2.25rem_minmax(0,1fr)_2.75rem_3rem] items-center gap-x-2 px-1 py-1.5 ${next ? 'bg-draft-soft/50' : ''}`}>
      <StencilNum className="text-[11px] leading-none text-ink-3">{index}</StencilNum>
      <div className="min-w-0">
        <div className="flex items-center gap-1.5">
          <p className="truncate text-[13px] font-semibold text-ink">{name}</p>
          {next ? (
            <span className="stencil text-[9px] font-semibold uppercase tracking-[0.16em] text-draft">next</span>
          ) : null}
        </div>
        {reason ? <p className="truncate text-[11px] text-ink-2">{reason}</p> : null}
      </div>
      <StencilNum className="text-right text-[11px] leading-none text-ink-2">P{priority}</StencilNum>
      <StencilNum className="tabular text-right text-[11px] leading-none text-ink-2">{minutes ?? 15}m</StencilNum>
    </li>
  )
}

// BOM column header — same grid template as PartsRow so columns register.
export function PartsListHeader() {
  return (
    <div className="stencil grid grid-cols-[2.25rem_minmax(0,1fr)_2.75rem_3rem] gap-x-2 px-1 pb-1.5 text-[10px] uppercase leading-none tracking-[0.12em] text-ink-2">
      <span>item</span>
      <span>part</span>
      <span className="text-right">prio</span>
      <span className="text-right">est</span>
    </div>
  )
}

// --- Fixed-scale registered bar (botanical raise) ----------------------------

// Every competency renders on the same 0–10 scale and the same track width —
// registered, comparable, never re-scaled. Fill is drafting hatching so the
// strip carries the sheet's material grammar.
export function FixedScaleBar({
  name,
  latest,
  trend,
}: {
  name: string
  latest: number | null
  trend: number | null
}) {
  const pct = latest == null ? 0 : Math.max(0, Math.min(1, latest / 10)) * 100
  return (
    <div className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-3">
      <div className="flex min-w-0 items-center gap-2">
        <span className="w-32 shrink-0 truncate text-[11px] text-ink-2">{name}</span>
        <span aria-hidden className="relative h-2.5 flex-1 overflow-hidden border border-ink/30 bg-transparent">
          <span className="absolute inset-y-0 left-0 hatch text-draft" style={{ width: `${pct}%` }} />
        </span>
      </div>
      <span className="tabular text-[11px] text-ink-2">
        {latest == null ? '—' : latest.toFixed(1)}
        {trend != null ? (
          <span className={`ml-1 ${trend >= 0 ? 'text-draft' : 'text-redline'}`}>
            {trend >= 0 ? `▲ +${trend.toFixed(1)}` : `▼ ${trend.toFixed(1)}`}
          </span>
        ) : null}
      </span>
    </div>
  )
}
