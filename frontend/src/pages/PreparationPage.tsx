import { useMemo, type ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  useComputeReadiness,
  usePreparation,
  useReadiness,
  useRegeneratePreparation,
  useResolvedProfile,
  useRoles,
  DEFAULT_USER_ID,
} from '../hooks/queries'
import { Button, ErrorState, Skeleton } from '../components/ui'
import {
  DimensionLine,
  LevelCells,
  ProvenanceLegend,
  QueueStamp,
  RedlineCallout,
  RedlineMarker,
  RedlineSeverityKey,
  Ruler,
  Sheet,
  SheetSection,
  StencilNum,
  type Provenance,
} from '../components/sheet'

// demonstrated_level doubles as evidence depth: 1–2 claimed (dotted),
// 3–4 observed (dashed), 5 demonstrated (solid). Same code as the
// readiness drawing — the work order is drawn from the same evidence.
function provenance(level: number | null | undefined): Provenance {
  if (!level || level <= 2) return 'claimed'
  if (level <= 4) return 'observed'
  return 'demonstrated'
}

const ASSESSMENT_LABEL: Record<string, string> = {
  targeted_exercise: 'targeted exercise',
}

function assessmentLabel(type: string | null | undefined): string {
  return type ? ASSESSMENT_LABEL[type] ?? type : 'practice item'
}

// Ghost order band — the unissued work order drawn with the same absence
// notation as the readiness frame: empty cells, em-dash level, dotted
// (claimed) dimension. Never a measured zero.
function GhostTicket({ title, body, action }: { title: string; body: string; action?: ReactNode }) {
  return (
    <div className="flex flex-wrap items-center gap-x-10 gap-y-5 px-6 py-5">
      <div className="min-w-0 flex-1">
        <p className="stencil text-[10px] uppercase tracking-[0.12em] text-redline">{title}</p>
        <p className="mt-1.5 max-w-lg text-[12px] leading-relaxed text-ink-2">{body}</p>
        {action ? <div className="mt-3.5">{action}</div> : null}
      </div>
      <div className="w-44 shrink-0">
        <div className="flex items-center gap-2.5">
          <LevelCells level={0} />
          <span className="stencil text-[15px] leading-none text-ink-3">—/5</span>
        </div>
        <DimensionLine style="claimed" className="mt-2" />
        <Ruler className="mt-2" />
      </div>
    </div>
  )
}

export function PreparationPage() {
  const navigate = useNavigate()
  const { activeId } = useResolvedProfile(DEFAULT_USER_ID)
  const readiness = useReadiness(DEFAULT_USER_ID, activeId)
  const compute = useComputeReadiness(DEFAULT_USER_ID, activeId)
  const prep = usePreparation(DEFAULT_USER_ID, activeId)
  const regenerate = useRegeneratePreparation(DEFAULT_USER_ID, activeId)
  const roles = useRoles(DEFAULT_USER_ID, activeId)

  const targetRole = roles.data?.at(-1)
  const roleId = targetRole?.id
  const busy = compute.isPending || regenerate.isPending
  const loading = readiness.isLoading || prep.isLoading
  const queue = prep.data ?? []
  const gaps = readiness.data?.critical_gaps ?? []
  const readinessVal = readiness.data?.overall ?? 0

  // Weakest critical competencies first — the dimension set reads as the
  // model the order was drawn from. Same ranking as the readiness drawing.
  const perCompRows = useMemo(() => {
    const rows = readiness.data?.per_competency ?? []
    const rank: Record<string, number> = { critical: 0, important: 1, nice_to_have: 2, 'nice-to-have': 2 }
    return [...rows].sort((a, b) => (rank[a.importance] ?? 1) - (rank[b.importance] ?? 1) || a.score - b.score)
  }, [readiness.data])

  // Per-competency dimension lookup: demonstrated level from the drawing,
  // required/gap/marker from the redline set (markers stay 1:1 with the
  // callouts actually rendered — first 5 gaps).
  const dimByName = useMemo(() => {
    const m = new Map<string, { demonstrated: number; required: number | null; gap: number | null; marker: number | null }>()
    for (const c of readiness.data?.per_competency ?? []) {
      m.set(c.name, { demonstrated: c.demonstrated_level, required: null, gap: null, marker: null })
    }
    ;(readiness.data?.critical_gaps ?? []).slice(0, 5).forEach((g, i) => {
      m.set(g.name, { demonstrated: g.demonstrated_level, required: g.required_level, gap: g.gap, marker: i + 1 })
    })
    return m
  }, [readiness.data])

  // A snapshot counts as assessed only when a deterministic measurement
  // exists — an empty/zeroed snapshot is NOT_ASSESSED, never a verified zero.
  const assessed =
    !readiness.isLoading &&
    Boolean(
      readiness.data &&
        (perCompRows.length > 0 || gaps.length > 0 || (readiness.data.evidence_coverage ?? 0) > 0),
    )

  const noRole = !roleId
  const issued = !noRole && assessed && queue.length > 0
  const estMinutes = issued ? queue.reduce((sum, i) => sum + (i.estimated_minutes ?? 15), 0) : null
  const estGain = issued ? queue.reduce((sum, i) => sum + (i.expected_improvement ?? 0), 0) : null

  const queueStatus = noRole
    ? { label: 'NO TARGET ROLE', tone: 'redline' as const }
    : !assessed
      ? { label: 'NOT ASSESSED', tone: 'redline' as const }
      : queue.length === 0 && gaps.length > 0
        ? { label: 'QUEUE NOT GENERATED', tone: 'redline' as const }
        : queue.length === 0
          ? { label: 'NO OPEN ORDERS', tone: 'ink-2' as const }
          : { label: 'ORDER ISSUED', tone: 'draft' as const }

  const h1 = loading
    ? 'Loading the work order…'
    : noRole
      ? 'No target role yet — analyze a job description to build the competency model.'
      : !assessed
        ? 'Not assessed yet — compute readiness to issue the preparation order.'
        : queue.length === 0 && gaps.length > 0
          ? 'Critical gaps found — the queue has not been generated yet.'
          : queue.length === 0
            ? 'No open orders — no critical gaps identified.'
            : `${queue.length} open orders — ${queue[0].competency_name ?? 'top item'} first.`

  const drawnDate = readiness.data?.created_at
    ? new Date(readiness.data.created_at).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' })
    : '—'

  const top = queue[0]
  const topDim = top?.competency_name ? dimByName.get(top.competency_name) : null

  const scheduleHeader = (
    <div className="stencil hidden grid-cols-[2.25rem_minmax(0,1fr)_11rem_3.25rem_3.75rem] gap-x-2 px-1 pb-1.5 text-[10px] uppercase leading-none tracking-[0.12em] text-ink-2 md:grid">
      <span>order</span>
      <span>competency</span>
      <span>now → target</span>
      <span className="text-right">effort</span>
      <span className="text-right">est. gain</span>
    </div>
  )

  return (
    <div className="space-y-6">
      {compute.isError ? (
        <ErrorState
          title="Readiness computation failed"
          body={compute.error instanceof Error ? compute.error.message : undefined}
          onRetry={() => void compute.mutateAsync(roleId)}
        />
      ) : null}

      <Sheet aria-label="Preparation work order sheet">
        {/* ── Title block: queue status stamp + work-order identity ───── */}
        <header className="border-b border-ink/25">
          <div className="flex flex-wrap items-start justify-between gap-x-8 gap-y-5 px-6 pb-5 pt-5">
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                <p className="text-[10px] font-medium uppercase tracking-[0.12em] text-ink-2/70">
                  Pramya · Preparation · Work Order
                </p>
                {targetRole ? (
                  <p className="text-[10px] uppercase tracking-[0.1em] text-ink-3">
                    {targetRole.seniority ?? ''} {targetRole.title}
                  </p>
                ) : null}
              </div>
              <h1 className="mt-1.5 text-[22px] font-semibold tracking-tight text-ink sm:text-2xl">{h1}</h1>
              <p className="mt-1 text-sm text-ink-2">
                The prioritized intervention schedule drawn from your readiness drawing — what to work on next, and why.
              </p>
              <div className="mt-3.5">
                <ProvenanceLegend />
              </div>
            </div>

            <QueueStamp
              loading={loading}
              openCount={issued ? queue.length : null}
              minutes={estMinutes}
              gain={estGain}
              date={drawnDate}
              status={queueStatus.label}
              statusTone={queueStatus.tone}
            />
          </div>
        </header>

        {/* ── Work order 01 — today's item (the raking light) ─────────── */}
        <SheetSection
          title={issued ? "Work order 01 — today's item" : 'Work order — today\u2019s item'}
          tone={issued ? 'lit' : 'flat'}
          className="border-t"
          aside={
            issued ? <span className="text-[10px] uppercase tracking-[0.1em] text-ink-2">highest value · next</span> : undefined
          }
        >
          {loading ? (
            <div className="space-y-3 px-0 py-1">
              <Skeleton className="h-12 w-full" />
              <Skeleton className="h-9 w-3/4" />
            </div>
          ) : noRole ? (
            <GhostTicket
              title="No target role — work order cannot be issued"
              body="Add a profile and target role to build the competency model the order is drawn from."
              action={
                <Button size="sm" onClick={() => navigate('/setup')}>
                  Set up profile & role →
                </Button>
              }
            />
          ) : !assessed ? (
            <GhostTicket
              title="Not assessed — no measurements on file"
              body="Compute readiness after analyzing a role to generate the preparation order."
              action={
                <Button size="sm" onClick={() => void compute.mutateAsync(roleId)} disabled={busy}>
                  {compute.isPending ? 'Computing…' : 'Compute readiness →'}
                </Button>
              }
            />
          ) : !issued ? (
            gaps.length > 0 ? (
              <GhostTicket
                title="Queue not generated"
                body="Critical gaps are on file but no order exists — regenerate the queue to issue it."
                action={
                  <Button size="sm" onClick={() => void regenerate.mutateAsync()} disabled={busy}>
                    {regenerate.isPending ? 'Regenerating…' : 'Regenerate queue →'}
                  </Button>
                }
              />
            ) : (
              <GhostTicket
                title="No open orders"
                body="No critical gaps identified — keep demonstrating what you know."
              />
            )
          ) : top ? (
            <>
              <div className="grid gap-x-10 gap-y-5 lg:grid-cols-12">
              <div className="min-w-0 lg:col-span-7">
                <div className="flex items-center gap-3">
                  <span
                    aria-hidden
                    className="stencil grid h-9 w-9 shrink-0 place-items-center rounded-full border-2 border-ink/70 text-[16px] leading-none text-ink"
                  >
                    01
                  </span>
                  <div className="min-w-0">
                    <p className="truncate text-xl font-semibold tracking-tight text-ink">
                      {top.competency_name ?? 'Practice'}
                    </p>
                    <p className="mt-0.5 text-[10px] font-semibold uppercase tracking-[0.12em] text-ink-2">
                      {assessmentLabel(top.assessment_type)} · priority {top.priority}
                    </p>
                  </div>
                </div>

                <div className="mt-3 max-w-md">
                  <Ruler />
                </div>
                <div className="mt-2 flex items-center gap-3 px-1">
                  <LevelCells level={topDim?.demonstrated ?? 0} />
                  <span className="stencil text-[13px] leading-none text-ink">
                    now {topDim?.demonstrated ?? 0}/5
                    {topDim?.required != null ? ` · req ${topDim.required}/5` : ''}
                  </span>
                </div>
                <DimensionLine style={provenance(topDim?.demonstrated)} className="max-w-md" />

                <div className="mt-3 border-t border-ink/10 pt-3">
                  <div className="flex items-center gap-2">
                    {topDim?.marker != null ? <RedlineMarker index={topDim.marker} /> : null}
                    <span className="stencil text-[10px] font-semibold uppercase tracking-[0.14em] text-redline">
                      Gap {topDim?.marker != null ? topDim.marker : 'ref'}
                    </span>
                    <span aria-hidden className="h-px w-10 bg-redline/50" />
                  </div>
                  {topDim?.gap != null && topDim.required != null ? (
                    <>
                      <div className="mt-2 flex items-center gap-2.5">
                        <span className="stencil text-[15px] leading-none text-ink">demonstrated {topDim.demonstrated}/5</span>
                        <svg aria-hidden viewBox="0 0 8 8" className="h-2.5 w-2.5 text-redline">
                          <path d="M0 4 L8 0 V8 Z" fill="currentColor" />
                        </svg>
                        <span className="stencil text-[15px] leading-none text-redline">required {topDim.required}/5</span>
                      </div>
                      <p className="stencil mt-1.5 text-[10px] uppercase tracking-[0.12em] text-redline">
                        {Number.isInteger(topDim.gap) ? `${topDim.gap} level gap` : `${topDim.gap.toFixed(1)} level gap`}
                      </p>
                    </>
                  ) : (
                    <p className="mt-2 text-[12px] leading-relaxed text-ink-2">{top.reason ?? 'Gap-driven preparation order.'}</p>
                  )}
                </div>
              </div>

              <div className="lg:col-span-5">
                <div className="grid grid-cols-2 gap-x-6 gap-y-3">
                  <div>
                    <p className="text-[10px] font-medium uppercase tracking-[0.12em] text-ink-2/70">est. effort</p>
                    <p className="stencil mt-1 text-2xl leading-none text-ink">
                      {top.estimated_minutes ?? 15}
                      <span className="text-sm text-ink-2"> min</span>
                    </p>
                  </div>
                  <div>
                    <p className="text-[10px] font-medium uppercase tracking-[0.12em] text-ink-2/70">est. gain</p>
                    <p className="stencil mt-1 text-2xl leading-none text-draft">
                      {top.expected_improvement != null ? `+${top.expected_improvement.toFixed(2)}` : '—'}
                    </p>
                  </div>
                </div>
                <p className="mt-3 text-[10px] uppercase tracking-[0.1em] text-ink-2">
                  expected readiness movement if completed — estimated, not guaranteed.
                </p>
              </div>
            </div>
            <div className="mt-3 flex flex-wrap items-center justify-end gap-x-4 gap-y-2 border-t border-ink/10 pt-3.5">
              <span className="stencil text-[10px] uppercase tracking-[0.1em] text-ink-2">
                next order: {queue[1]?.competency_name ?? '—'}
              </span>
              <Button onClick={() => navigate('/interview')}>
                Start practice — {top.competency_name ?? 'top item'} →
              </Button>
            </div>
            </>
          ) : null}
        </SheetSection>

        {/* ── Main work row: schedule + gap references ────────────────── */}
        <div className="grid lg:grid-cols-12">
        <SheetSection
          title="Preparation schedule — remaining orders"
          tone="flat"
          className="border-t lg:col-span-8"
          aside={
            issued ? (
              <span className="stencil text-[10px] uppercase tracking-[0.1em] text-ink-2">
                {queue.length - 1} more · ≈ {estMinutes! - (top?.estimated_minutes ?? 15)} min
              </span>
            ) : (
              <span className="stencil text-[10px]">—</span>
            )
          }
        >
          {loading ? (
            <div className="space-y-2.5 px-0 py-1">
              <Skeleton className="h-9 w-full" />
              <Skeleton className="h-9 w-full" />
              <Skeleton className="h-9 w-full" />
            </div>
          ) : !issued ? (
            <div className="py-1.5">
              <p className="text-[13px] font-semibold text-ink">No orders issued yet</p>
              <p className="mt-1 max-w-xl text-[11px] leading-snug text-ink-2">
                {noRole
                  ? 'Analyze a target role to build the competency model, then compute readiness to generate the order.'
                  : !assessed
                    ? 'Compute readiness after analyzing a role to generate the order.'
                    : gaps.length > 0
                      ? 'Critical gaps exist but the queue is empty — regenerate to issue the remaining orders.'
                      : 'The queue clears when no critical gaps remain — practice to keep demonstrating what you know.'}
              </p>
            </div>
          ) : queue.length > 1 ? (
            <>
              {scheduleHeader}
              <ul className="divide-y divide-ink/10 border-y border-ink/10">
                {queue.slice(1).map((item, i) => {
                  const dim = item.competency_name ? dimByName.get(item.competency_name) : null
                  const gain = item.expected_improvement
                  return (
                    <li key={item.id}>
                      <button
                        type="button"
                        onClick={() => navigate('/evidence')}
                        aria-label={`${item.competency_name ?? 'Practice'}: now ${dim?.demonstrated ?? 0} of 5 demonstrated${dim?.required != null ? `, required ${dim.required} of 5` : ''}, ${item.estimated_minutes ?? 15} minutes, expected gain ${gain != null ? `+${gain.toFixed(2)}` : 'unknown'}. Opens the evidence ledger.`}
                        className="group grid w-full grid-cols-[2rem_minmax(0,1fr)_auto] items-center gap-x-2 px-1 py-2.5 text-left transition-colors hover:bg-draft-soft/40 focus-visible:outline-none md:grid-cols-[2.25rem_minmax(0,1fr)_11rem_3.25rem_3.75rem]"
                      >
                        <StencilNum className="text-[11px] leading-none text-ink-3">{String(i + 2).padStart(2, '0')}</StencilNum>
                        <div className="min-w-0">
                          <div className="flex items-center gap-1.5">
                            <p className="truncate text-[13px] font-semibold text-ink">{item.competency_name ?? 'Practice'}</p>
                            {dim?.marker != null ? <RedlineMarker index={dim.marker} /> : null}
                            <span className="stencil hidden text-[9px] font-semibold uppercase tracking-[0.14em] text-draft opacity-0 transition-opacity group-hover:opacity-100 group-focus-visible:opacity-100 md:inline">
                              → evidence
                            </span>
                          </div>
                          <p className="truncate text-[11px] text-ink-2">{item.reason}</p>
                        </div>
                        <div className="flex flex-col items-end gap-0.5 md:flex-row md:items-center md:gap-2 md:self-center">
                          <LevelCells level={dim?.demonstrated ?? 0} />
                          <span className="stencil text-[9px] leading-none text-ink-2 md:hidden">
                            {dim?.demonstrated ?? 0}
                            {dim?.required != null ? `→${dim.required}` : ''} · {item.estimated_minutes ?? 15}m ·{' '}
                            {gain != null ? `+${gain.toFixed(2)}` : '—'}
                          </span>
                          <span className="stencil hidden text-[10px] leading-none text-ink-2 md:inline">
                            {dim?.required != null ? `req ${dim.required}/5` : ''}
                          </span>
                        </div>
                        <StencilNum className="hidden text-right text-[11px] leading-none text-ink-2 md:block">
                          {item.estimated_minutes ?? 15}m
                        </StencilNum>
                        <StencilNum className={`hidden text-right text-[11px] leading-none md:block ${gain != null ? 'text-draft' : 'text-ink-3'}`}>
                          {gain != null ? `+${gain.toFixed(2)}` : '—'}
                        </StencilNum>
                      </button>
                    </li>
                  )
                })}
              </ul>
              <div className="mt-2.5 border-t border-ink/10 pt-2.5">
                <div className="stencil flex items-baseline justify-between gap-3 text-[10px] uppercase tracking-[0.1em] text-ink-2">
                  <span>queue ≈ {estMinutes ?? '—'} min</span>
                  <span className="text-draft">gain ≈ +{estGain != null ? estGain.toFixed(1) : '—'}</span>
                </div>
              </div>
            </>
          ) : (
            <p className="py-1 text-[12px] leading-relaxed text-ink-2">No further orders — the work order above is the only one issued.</p>
          )}
        </SheetSection>

        {/* ── Gap references — the why, beside the schedule ───────────── */}
          <SheetSection
            title="Redline — gap references"
            tone="shadow"
            className="border-t lg:col-span-4 lg:border-l"
            aside={<span className="stencil text-[10px]">{gaps.length}</span>}
          >
            {loading ? (
              <Skeleton className="h-28 w-full" />
            ) : gaps.length === 0 ? (
              <p className="py-1 text-[12px] leading-relaxed text-ink-2">No required competency is below target.</p>
            ) : (
              <>
                <ul className="divide-y divide-ink/10">
                  {gaps.slice(0, 5).map((gap, i) => (
                    <RedlineCallout
                      key={gap.competency_id}
                      index={i + 1}
                      name={gap.name}
                      demonstrated={gap.demonstrated_level}
                      required={gap.required_level}
                      gap={gap.gap}
                    />
                  ))}
                </ul>
                <RedlineSeverityKey />
              </>
            )}
          </SheetSection>
        </div>

        {/* ── Reference band: compressed dimension set ─────────────────── */}
        <SheetSection
          title="Competency dimension set — reference"
          tone="flat"
          className="border-t"
          aside={
            readiness.data ? (
              <span className="stencil text-[10px] uppercase tracking-[0.1em] text-ink-2">
                overall {readinessVal.toFixed(1)}/10 · conf {Math.round((readiness.data.confidence ?? 0) * 100)}%
              </span>
            ) : undefined
          }
        >
          {loading ? (
            <Skeleton className="h-20 w-full" />
          ) : perCompRows.length === 0 ? (
            <p className="py-1 text-[12px] leading-relaxed text-ink-2">
              No competency model yet — analyze a job description to build the model.
            </p>
          ) : (
            <ul className="grid gap-x-6 gap-y-1 sm:grid-cols-2 xl:grid-cols-3">
              {perCompRows.map((c) => (
                <li key={c.name}>
                  <button
                    type="button"
                    onClick={() => navigate('/evidence')}
                    aria-label={`${c.name}: demonstrated level ${c.demonstrated_level} of 5, score ${c.score.toFixed(1)} of 10, coverage ${Math.round((c.evidence_coverage ?? 0) * 100)}%. Opens the evidence ledger.`}
                    className="group flex w-full items-center gap-2.5 py-1.5 text-left transition-colors hover:bg-draft-soft/40 focus-visible:outline-none"
                  >
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-[12px] font-semibold text-ink">{c.name}</span>
                      <span className="stencil text-[9px] uppercase tracking-[0.1em] text-ink-2">{c.importance}</span>
                    </span>
                    <LevelCells level={c.demonstrated_level} />
                    <span className="tabular w-20 shrink-0 text-right text-[10px] leading-none text-ink-2">
                      {c.score.toFixed(1)}/10 · cov {Math.round((c.evidence_coverage ?? 0) * 100)}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </SheetSection>

        {/* ── Revision strip: queue totals + maintenance actions ──────── */}
        <footer className="border-t border-ink/25">
          <div className="grid gap-x-6 gap-y-4 px-6 py-3.5 lg:grid-cols-[minmax(0,15rem)_minmax(0,1fr)_auto]">
            <div>
              <p className="text-[10px] font-medium uppercase tracking-[0.12em] text-ink-2/70">Revision · queue totals</p>
              <dl className="mt-2 grid grid-cols-2 gap-x-6 gap-y-1 sm:grid-cols-4 lg:grid-cols-2 xl:grid-cols-4">
                <div className="flex items-baseline justify-between gap-3 text-[11px]">
                  <dt className="text-ink-2">orders</dt>
                  <dd className="tabular text-ink">{issued ? queue.length : '—'}</dd>
                </div>
                <div className="flex items-baseline justify-between gap-3 text-[11px]">
                  <dt className="text-ink-2">est. effort</dt>
                  <dd className="tabular text-ink">{estMinutes != null ? `≈ ${estMinutes} min` : '—'}</dd>
                </div>
                <div className="flex items-baseline justify-between gap-3 text-[11px]">
                  <dt className="text-ink-2">est. movement</dt>
                  <dd className="tabular text-draft">{estGain != null ? `+${estGain.toFixed(1)}` : '—'}</dd>
                </div>
                <div className="flex items-baseline justify-between gap-3 text-[11px]">
                  <dt className="text-ink-2">drawn</dt>
                  <dd className="tabular text-ink">{drawnDate}</dd>
                </div>
              </dl>
            </div>
            <div className="min-w-0">
              {noRole ? (
                <p className="text-[11px] leading-relaxed text-ink-2">
                  No target role yet —{' '}
                  <button
                    className="font-medium text-draft underline underline-offset-2 hover:text-draft-2"
                    onClick={() => navigate('/setup')}
                  >
                    analyze a JD in Profile &amp; Role
                  </button>{' '}
                  first.
                </p>
              ) : null}
              {busy ? (
                <p className="stencil mt-1 text-[10px] uppercase tracking-[0.12em] text-draft">
                  {compute.isPending ? 'computing readiness…' : 'regenerating queue…'}
                </p>
              ) : null}
            </div>
            <div className="flex flex-wrap items-start gap-2">
              <Button size="sm" variant="secondary" onClick={() => void compute.mutateAsync(roleId)} disabled={busy || !roleId}>
                {compute.isPending ? 'Computing…' : 'Refresh readiness'}
              </Button>
              <Button size="sm" variant="secondary" onClick={() => void regenerate.mutateAsync()} disabled={busy || !gaps.length}>
                {regenerate.isPending ? 'Regenerating…' : 'Regenerate queue'}
              </Button>
              <button
                type="button"
                className="stencil mt-1.5 text-[10px] font-semibold uppercase tracking-[0.1em] text-draft underline underline-offset-2 hover:text-draft-2"
                onClick={() => navigate('/evidence')}
              >
                Evidence ledger →
              </button>
            </div>
          </div>
        </footer>
      </Sheet>
    </div>
  )
}
