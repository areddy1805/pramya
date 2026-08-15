import { useProgress, useInterviews, useResolvedProfile, DEFAULT_USER_ID } from '../hooks/queries'
import { ErrorState, Skeleton } from '../components/ui'
import { Sheet, SheetSection, StencilNum } from '../components/sheet'
import type { CompetencySeries, ProgressPoint } from '../lib/types'

// Longitudinal record — movement measured only from completed evaluations.
// Nothing here is estimated or padded: every datum is one real evaluation,
// every trend is last-point minus first-point (backend semantics).

const HISTORY_TONE: Record<string, string> = {
  completed: 'text-draft',
  cancelled: 'text-ink-3',
  error: 'text-redline',
}

function pad2(n: number): string {
  return String(n).padStart(2, '0')
}

function fmtShort(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

function fmtFull(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })
}

function toneOf(v: number): string {
  return v >= 7 ? 'text-draft' : v >= 4 ? 'text-ink' : 'text-redline'
}

// --- Current position cell ----------------------------------------------------

// The record's current measurement: average overall, movement since the
// first evaluation, measurement span. Ghost dashes when nothing is measured.
function PositionCell({ summary }: { summary: { evals: number; sessions: number; average: number | null; delta: number | null; first: string | null; last: string | null } }) {
  const measured = summary.evals > 0 && summary.average != null
  return (
    <div className="w-full border border-ink/30 bg-sheet-lit/45 px-4 py-3 sm:w-[17rem]">
      <div className="flex items-baseline justify-between gap-3">
        <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-ink-2">Current position</p>
        {measured ? (
          <span className={`stencil text-[10px] uppercase tracking-[0.16em] ${toneOf(summary.average as number)}`}>
            {summary.delta != null && summary.delta >= 0 ? 'Rising' : 'Recorded'}
          </span>
        ) : (
          <span className="stencil text-[10px] uppercase tracking-[0.16em] text-ink-3">Not measured</span>
        )}
      </div>
      <div className="mt-1.5 flex items-baseline gap-1.5">
        <span className={`stencil text-4xl leading-none ${measured ? toneOf(summary.average as number) : 'text-ink-3'}`}>
          {measured ? (summary.average as number).toFixed(1) : '—'}
        </span>
        <span className="text-xs text-ink-2">/ 10</span>
      </div>
      <p className="stencil mt-2.5 border-t border-ink/20 pt-2 text-[10px] uppercase leading-relaxed tracking-[0.08em] text-ink-2">
        movement {summary.delta != null ? (summary.delta >= 0 ? `Δ +${summary.delta.toFixed(1)}` : `Δ ${summary.delta.toFixed(1)}`) : '—'} ·{' '}
        {summary.evals} evaluations · {summary.sessions} sessions
        <br />
        span {summary.first && summary.last ? `${fmtShort(summary.first)} → ${fmtShort(summary.last)}` : '—'}
      </p>
    </div>
  )
}

// --- Trajectory ---------------------------------------------------------------

// Fixed 0-10 scale; datum marks are real evaluation points registered on one
// axis. The connecting line is the dimension of movement, never a fitted
// curve. Fewer than two points = insufficient history (ghost continuation).
function Trajectory({ series, span }: { series: CompetencySeries[]; span: { first: string; last: string } }) {
  const points: ProgressPoint[] = series.flatMap((s) => s.points).sort((a, b) => a.created_at.localeCompare(b.created_at))
  const n = points.length
  if (n === 0) return null

  const W = 600
  const H = 240
  const padL = 40
  const padR = 20
  const padT = 34
  const padB = 30
  const y = (v: number) => padT + (1 - Math.min(10, Math.max(0, v)) / 10) * (H - padT - padB)
  const x = (i: number) => (n > 1 ? padL + (i / (n - 1)) * (W - padL - padR) : padL + (W - padL - padR) / 2)

  const delta = n > 1 ? points[n - 1].overall - points[0].overall : null

  return (
    <div className="py-2">
      <div className="stencil flex items-baseline justify-between gap-3 text-[10px] uppercase tracking-[0.12em] text-ink-2">
        <span>Trajectory · fixed 0–10 scale</span>
        <span>
          {fmtShort(span.first)} → {fmtShort(span.last)} · {n} evaluations
        </span>
      </div>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        role="img"
        aria-label={`Trajectory: ${n} evaluation points from ${fmtFull(span.first)} to ${fmtFull(span.last)}${delta != null ? `, overall movement ${delta >= 0 ? '+' : ''}${delta.toFixed(1)}` : ''}.`}
        className="mt-2 w-full"
      >
        {/* registration gridlines + scale */}
        {[0, 2.5, 5, 7.5, 10].map((v) => (
          <g key={v}>
            <line x1={padL} x2={W - padR} y1={y(v)} y2={y(v)} className="stroke-ink/15" strokeWidth="1" />
            <text x={padL - 6} y={y(v) + 3} textAnchor="end" className="fill-ink-3 stencil" fontSize="9">
              {v === 0 || v === 5 || v === 10 ? v : v.toFixed(1)}
            </text>
          </g>
        ))}
        <line x1={padL} x2={padL} y1={padT} y2={H - padB} className="stroke-ink/40" strokeWidth="1" />
        <line x1={padL} x2={W - padR} y1={H - padB} y2={H - padB} className="stroke-ink/40" strokeWidth="1" />

        {/* ghost continuation when history is insufficient */}
        {n < 2 ? (
          <line
            x1={x(0)}
            x2={W - padR}
            y1={y(points[0].overall)}
            y2={y(points[0].overall)}
            className="stroke-ink/30"
            strokeWidth="1"
            strokeDasharray="4 4"
          />
        ) : null}

        {/* measurement line through the datum marks */}
        {n > 1 ? (
          <polyline
            points={points.map((p, i) => `${x(i)},${y(p.overall)}`).join(' ')}
            className="fill-none stroke-ink/70"
            strokeWidth="1.5"
          />
        ) : null}

        {/* datum marks + value annotations */}
        {points.map((p, i) => (
          <g key={p.evaluation_id}>
            <line x1={x(i)} x2={x(i)} y1={H - padB} y2={H - padB + 4} className="stroke-ink/40" strokeWidth="1" />
            <text x={x(i)} y={H - padB + 14} textAnchor="middle" className="fill-ink-3" fontSize="9">
              {fmtShort(p.created_at)}
            </text>
            <rect
              x={x(i) - 2.5}
              y={y(p.overall) - 2.5}
              width={5}
              height={5}
              className={i === 0 || i === n - 1 ? 'fill-draft' : 'fill-ink'}
            />
            <text x={x(i)} y={y(p.overall) - 8} textAnchor="middle" className="fill-ink-2 stencil" fontSize="9">
              {p.overall.toFixed(1)}
            </text>
          </g>
        ))}

        {/* movement dimension (first → last) */}
        {delta != null ? (
          <g>
            <line x1={x(0)} x2={x(n - 1)} y1={padT - 12} y2={padT - 12} className={delta >= 0 ? 'stroke-draft' : 'stroke-redline'} strokeWidth="1" />
            <line x1={x(0)} x2={x(0)} y1={padT - 16} y2={padT - 8} className={delta >= 0 ? 'stroke-draft' : 'stroke-redline'} strokeWidth="1" />
            <line x1={x(n - 1)} x2={x(n - 1)} y1={padT - 16} y2={padT - 8} className={delta >= 0 ? 'stroke-draft' : 'stroke-redline'} strokeWidth="1" />
            <text x={(x(0) + x(n - 1)) / 2} y={padT - 17} textAnchor="middle" className={delta >= 0 ? 'fill-draft stencil' : 'fill-redline stencil'} fontSize="10">
              Δ {delta >= 0 ? '+' : ''}
              {delta.toFixed(1)}
            </text>
          </g>
        ) : (
          <text x={(x(0) + W - padR) / 2} y={padT - 12} textAnchor="middle" className="fill-ink-3 stencil" fontSize="9">
            1 measurement — insufficient history for a trend
          </text>
        )}
      </svg>
    </div>
  )
}

// --- Change record ------------------------------------------------------------

// Registered measurement ledger: every evaluation as a datum with its delta
// against the previous one. First datum has no delta — that is honest.
const CHANGE_GRID = 'grid-cols-[2rem_minmax(0,1fr)] md:grid-cols-[2.25rem_minmax(0,1fr)_6rem_3.5rem_4.5rem]'

function ChangeLedger({ points }: { points: ProgressPoint[] }) {
  if (!points.length) return null
  return (
    <>
      <div className={`stencil grid items-center gap-x-3 border-b border-ink/20 px-3 pb-2 pt-1 text-[10px] uppercase leading-none tracking-[0.12em] text-ink-2 ${CHANGE_GRID}`}>
        <span>Item</span>
        <span>Competency</span>
        <span className="hidden md:block">Date</span>
        <span className="hidden md:block">Overall</span>
        <span className="hidden md:block text-right">Δ prior</span>
      </div>
      <ol>
        {points.map((p, i) => {
          const prev = i > 0 ? points[i - 1].overall : null
          const d = prev != null ? p.overall - prev : null
          return (
            <li key={p.evaluation_id}>
              <div className={`grid w-full items-center gap-x-3 border-b border-ink/10 px-3 py-2 ${CHANGE_GRID}`}>
                <StencilNum className="text-[11px] leading-none text-ink-3">{pad2(i + 1)}</StencilNum>
                <div className="min-w-0">
                  <p className="truncate text-[13px] text-ink">{p.competency_name || 'interview'}</p>
                  <p className="text-[10px] uppercase tracking-[0.08em] text-ink-3 md:hidden">
                    {fmtShort(p.created_at)} · {p.overall.toFixed(1)}/10
                    {d != null ? ` · Δ ${d >= 0 ? '+' : ''}${d.toFixed(1)}` : ''}
                  </p>
                </div>
                <span className="hidden text-[11px] text-ink-2 md:block">{fmtShort(p.created_at)}</span>
                <span className={`stencil hidden text-[11px] leading-none md:block ${toneOf(p.overall)}`}>{p.overall.toFixed(1)}</span>
                <span className={`stencil hidden text-right text-[11px] leading-none md:block ${d == null ? 'text-ink-3' : d >= 0 ? 'text-draft' : 'text-redline'}`}>
                  {d == null ? '—' : `${d >= 0 ? '+' : ''}${d.toFixed(1)}`}
                </span>
              </div>
            </li>
          )
        })}
      </ol>
    </>
  )
}

export function ProgressPage() {
  const { activeId } = useResolvedProfile(DEFAULT_USER_ID)
  const progress = useProgress(DEFAULT_USER_ID, activeId)
  const sessions = useInterviews(DEFAULT_USER_ID, activeId)

  if (progress.isLoading) {
    return (
      <Sheet aria-label="Progress record">
        <div className="flex flex-wrap items-start justify-between gap-x-8 gap-y-4 border-b border-ink/25 px-6 pb-4 pt-5">
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-ink-2">Pramya · Progress · Record</p>
            <h1 className="mt-1.5 text-xl font-semibold tracking-tight text-ink">Progress</h1>
            <p className="mt-1 max-w-xl text-[13px] leading-relaxed text-ink-2">
              Movement measured only from completed evaluations — nothing is estimated or padded.
            </p>
          </div>
          <Skeleton className="h-32 w-full sm:w-[17rem]" />
        </div>
        <div className="px-6 py-8">
          <Skeleton className="h-64" />
        </div>
        <div className="px-6 py-6">
          <Skeleton className="h-40" />
        </div>
      </Sheet>
    )
  }

  if (progress.isError) {
    return (
      <Sheet aria-label="Progress record">
        <div className="px-6 py-8">
          <ErrorState
            title="Could not load progress"
            body={progress.error instanceof Error ? progress.error.message : undefined}
            onRetry={() => progress.refetch()}
          />
        </div>
      </Sheet>
    )
  }

  const series = progress.data?.series ?? []
  const points: ProgressPoint[] = series.flatMap((s) => s.points).sort((a, b) => a.created_at.localeCompare(b.created_at))
  const evals = progress.data?.total_evaluations ?? 0
  const measured = evals > 0 && points.length > 0
  const first = points.length ? points[0].created_at : null
  const last = points.length ? points[points.length - 1].created_at : null
  const delta = points.length > 1 ? points[points.length - 1].overall - points[0].overall : null
  const average = progress.data && measured ? progress.data.average_overall : null

  return (
    <Sheet aria-label="Progress record">
      {/* Title block */}
      <div className="flex flex-wrap items-start justify-between gap-x-8 gap-y-4 border-b border-ink/25 px-6 pb-4 pt-5">
        <div className="min-w-0">
          <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-ink-2">Pramya · Progress · Record</p>
          <h1 className="mt-1.5 text-xl font-semibold tracking-tight text-ink">Progress</h1>
          <p className="mt-1 max-w-xl text-[13px] leading-relaxed text-ink-2">
            Movement measured only from completed evaluations — nothing is estimated or padded.
          </p>
        </div>
        <PositionCell summary={{ evals, sessions: progress.data?.sessions ?? 0, average, delta, first, last }} />
      </div>

      {!measured ? (
        /* Empty record — legitimate absence, ghost-drawn */
        <SheetSection title="Trajectory" aside={<span className="stencil text-[10px] uppercase tracking-[0.14em] text-ink-3">no evaluations</span>}>
          <div className="border border-dashed border-ink/25 px-6 py-10 text-center">
            <p className="stencil text-[12px] uppercase tracking-[0.2em] text-ink-3">No evaluation history yet</p>
            <svg viewBox="0 0 600 120" className="mx-auto mt-6 w-full max-w-xl">
              {[0, 1, 2, 3, 4].map((i) => (
                <line key={i} x1={40} x2={580} y1={16 + i * 24} y2={16 + i * 24} className="stroke-ink/15" strokeWidth="1" strokeDasharray="3 5" />
              ))}
              <line x1={40} x2={580} y1={112} y2={112} className="stroke-ink/25" strokeWidth="1" strokeDasharray="3 5" />
            </svg>
            <p className="mx-auto mt-4 max-w-md text-[13px] leading-relaxed text-ink-2">
              Every practice answer produces an evaluation. Complete a session and your competency trends appear here.
            </p>
          </div>
        </SheetSection>
      ) : (
        <SheetSection
          title="Trajectory"
          tone="lit"
          aside={<span className="stencil text-[10px] uppercase tracking-[0.14em] text-ink-2">{evals} evaluations · {progress.data?.sessions ?? 0} sessions</span>}
        >
          {first && last ? <Trajectory series={series} span={{ first, last }} /> : null}
        </SheetSection>
      )}

      {/* Change record + session record */}
      <div className="grid lg:grid-cols-12">
        <SheetSection
          title="Change record"
          tone="flat"
          className="lg:col-span-8 lg:border-r"
          aside={
            <span className="stencil text-[10px] uppercase tracking-[0.14em] text-ink-2">
              {measured ? (delta != null ? `${delta >= 0 ? 'Δ +' : 'Δ '}${delta.toFixed(1)} first → last` : '1 measurement') : 'no data'}
            </span>
          }
        >
          {measured ? (
            <ChangeLedger points={points} />
          ) : (
            <div className="border border-dashed border-ink/25 px-4 py-6 text-center">
              <p className="stencil text-[10px] uppercase tracking-[0.16em] text-ink-3">No measurements on record</p>
            </div>
          )}
        </SheetSection>

        <SheetSection
          title="Session record"
          tone="shadow"
          className="lg:col-span-4"
          aside={<span className="stencil text-[10px] uppercase tracking-[0.14em] text-ink-2">{sessions.data?.length ?? 0} sessions</span>}
        >
          {!sessions.data?.length ? (
            <p className="py-2 text-[13px] text-ink-2">No sessions yet.</p>
          ) : (
            <ol className="thin-scroll max-h-[22rem] overflow-y-auto">
              {sessions.data.map((s, i) => (
                <li key={s.id} className="grid grid-cols-[2rem_minmax(0,1fr)_auto] items-center gap-x-3 border-b border-ink/10 py-2">
                  <StencilNum className="text-[11px] leading-none text-ink-3">{pad2(i + 1)}</StencilNum>
                  <div className="min-w-0">
                    <p className="truncate text-[13px] text-ink">{s.kind.replace(/_/g, ' ')}</p>
                    <p className="text-[11px] text-ink-3">
                      {s.started_at ? fmtFull(s.started_at) : '—'}
                    </p>
                  </div>
                  <span className={`stencil text-[10px] uppercase tracking-[0.1em] ${HISTORY_TONE[s.status] ?? 'text-ink-2'}`}>{s.status}</span>
                </li>
              ))}
            </ol>
          )}
        </SheetSection>
      </div>

      {/* Revision strip */}
      <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-2 border-t border-ink/25 px-6 pb-4 pt-3">
        <p className="stencil text-[10px] uppercase leading-relaxed tracking-[0.1em] text-ink-2">
          profile {activeId ?? '—'} · {evals} evaluations · {progress.data?.sessions ?? 0} sessions
          <br />
          drawn {new Date().toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })}
        </p>
        <p className="stencil text-[10px] uppercase leading-relaxed tracking-[0.1em] text-ink-3">
          every datum is one completed evaluation — movement is measured, never padded.
        </p>
      </div>
    </Sheet>
  )
}
