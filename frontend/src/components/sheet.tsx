// Drawing-sheet primitives — the drafting grammar shared by sheet surfaces.
//
// Grammar contract (locked direction, .impeccable/decision-direction.json):
//  - one coherent grid (24px ruling, zones align to it)
//  - ink linework with weight = meaning; drafting blue = measured/active
//  - redline = correction/attention only
//  - ghost cells: unachieved evidence drawn as deliberately as achieved
//  - provenance via line style: dotted = claimed, dashed = observed,
//    solid = demonstrated
//  - one raking light: the active region (lit tone) carries the work;
//    side regions fall into their own shadow
//
// Components consume the sheet tokens (--sheet/--ink/--draft/--redline),
// never raw colors.

import type { ReactNode } from 'react'

export type Provenance = 'claimed' | 'observed' | 'demonstrated'

// --- The sheet ---------------------------------------------------------------

export function Sheet({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <div className={`sheet-grid border border-ink/30 bg-sheet text-ink ${className}`}>{children}</div>
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
      <header className="flex items-baseline justify-between gap-3 px-6 pb-3 pt-5">
        <h2 className="text-[11px] font-semibold uppercase tracking-[0.12em] text-ink-2">{title}</h2>
        {aside ? <div className="shrink-0 text-ink-2">{aside}</div> : null}
      </header>
      <div className="min-w-0 flex-1 px-6 pb-6">{children}</div>
    </section>
  )
}

// --- Measurement voice -------------------------------------------------------

export function StencilNum({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <span className={`stencil ${className}`}>{children}</span>
}

// 5-cell level strip: filled cells = achieved, outlined cells = ghost
// (explicit absence). The seven-seg raise: absence is drawn, never a void.
export function LevelCells({
  level,
  total = 5,
  tone = 'ink',
  className = '',
}: {
  level: number
  total?: number
  tone?: 'ink' | 'draft' | 'redline'
  className?: string
}) {
  const filled = {
    ink: 'border-ink bg-ink',
    draft: 'border-draft bg-draft',
    redline: 'border-redline bg-redline',
  }[tone]
  const clamped = Math.max(0, Math.min(total, level))
  return (
    <span role="img" aria-label={`${clamped} of ${total} demonstrated`} className={`inline-flex items-center gap-1 ${className}`}>
      {Array.from({ length: total }, (_, i) => (
        <span key={i} aria-hidden className={`h-2.5 w-2.5 border ${i < clamped ? filled : 'border-ink/35 bg-transparent'}`} />
      ))}
    </span>
  )
}

// Horizontal dimension line with end ticks. Line style = provenance.
export function DimensionLine({ style, className = '' }: { style: Provenance; className?: string }) {
  const line = {
    claimed: 'border-ink/40 border-dotted',
    observed: 'border-ink/60 border-dashed',
    demonstrated: 'border-ink/90 border-solid',
  }[style]
  return (
    <span aria-hidden className={`relative mt-2 flex h-2 items-center ${className}`}>
      <span className={`w-full border-t ${line}`} />
      <span className="absolute -left-px h-2 w-px bg-ink/60" />
      <span className="absolute -right-px h-2 w-px bg-ink/60" />
    </span>
  )
}

// Coverage hatch — a bounded bar whose fill is drafting hatching; the hatch
// density communicates the fraction of required evidence present.
export function CoverageHatch({ value, showLabel = true }: { value: number; showLabel?: boolean }) {
  const pct = Math.round(Math.max(0, Math.min(1, value)) * 100)
  return (
    <span className="flex items-center gap-1.5" title={`Evidence coverage ${pct}%`}>
      <span aria-hidden className="relative h-3 w-16 overflow-hidden border border-ink/30 bg-transparent">
        <span className="absolute inset-y-0 left-0 hatch text-draft" style={{ width: `${pct}%` }} />
      </span>
      {showLabel ? <span className="tabular text-[11px] text-ink-2">{pct}% cov</span> : null}
    </span>
  )
}

// --- Provenance legend (stable, lives in the title block) --------------------

export function ProvenanceLegend() {
  const line: Record<Provenance, string> = {
    claimed: 'border-t border-dotted border-ink/50',
    observed: 'border-t border-dashed border-ink/60',
    demonstrated: 'border-t border-solid border-ink/90',
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
        <span aria-hidden className="inline-block h-2.5 w-2.5 border border-ink/40 bg-transparent" />
        not yet evidenced
      </li>
    </ul>
  )
}

// --- Redline callout (critical gap) ------------------------------------------

export function RedlineCallout({
  name,
  demonstrated,
  required,
  gap,
}: {
  name: string
  demonstrated: number
  required: number
  gap: number
}) {
  return (
    <li className="border border-redline/45 bg-redline-soft/50 px-3 py-2.5">
      <div className="flex items-baseline justify-between gap-2">
        <p className="min-w-0 truncate text-[13px] font-semibold text-ink">{name}</p>
        <StencilNum className="shrink-0 text-[13px] leading-none text-redline">−{gap.toFixed(1)}</StencilNum>
      </div>
      <div className="mt-2 flex items-center gap-2.5">
        <LevelCells level={demonstrated} />
        <span className="tabular text-[10px] uppercase tracking-[0.08em] text-ink-2">now {demonstrated}/5</span>
      </div>
      <p className="mt-1.5 text-[10px] font-semibold uppercase tracking-[0.08em] text-redline">
        requires <StencilNum className="ml-0.5 text-[12px] text-ink">{required}/5</StencilNum>
      </p>
    </li>
  )
}

// --- Parts list (preparation queue as BOM) -----------------------------------

export function PartsRow({
  index,
  name,
  reason,
  minutes,
  priority,
  status,
  action,
  next = false,
}: {
  index: string
  name: string
  reason?: string | null
  minutes?: number | null
  priority: number
  status?: string
  action?: ReactNode
  next?: boolean
}) {
  return (
    <li className={`border border-ink/20 px-3 py-2.5 ${next ? 'bg-draft-soft/60' : ''}`}>
      <div className="flex items-start gap-3">
        <StencilNum className="pt-0.5 text-[11px] leading-none text-ink-3">{index}</StencilNum>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <p className="truncate text-[13px] font-semibold text-ink">{name}</p>
            {next ? (
              <span className="stencil text-[9px] font-semibold uppercase tracking-[0.14em] text-draft">next</span>
            ) : null}
          </div>
          {reason ? (
            <p className="mt-0.5 line-clamp-2 text-[11px] leading-snug text-ink-2">{reason}</p>
          ) : null}
          <p className="mt-1 text-[10px] uppercase tracking-[0.08em] text-ink-3">
            ≈ {minutes ?? 15} min · priority {priority}
            {status ? <span className="ml-1.5 normal-case tracking-normal text-ink-2">· {status}</span> : null}
          </p>
        </div>
        {action ? <div className="shrink-0 pt-0.5">{action}</div> : null}
      </div>
    </li>
  )
}

// --- Fixed-scale registered bar (botanical raise) ----------------------------

// Every competency renders on the same 0–10 scale and the same track width —
// registered, comparable, never re-scaled.
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
          <span className="absolute inset-y-0 left-0 bg-ink/85" style={{ width: `${pct}%` }} />
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
