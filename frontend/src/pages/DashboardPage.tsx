import { useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { ApiError } from '../lib/api'
import { useCandidate, useDocuments, usePreparation, useProgress, useReadiness, useRoles, useResolvedProfile, DEFAULT_USER_ID } from '../hooks/queries'
import { Button, ErrorState, Skeleton } from '../components/ui'
import {
  DimensionLine,
  FixedScaleBar,
  LevelCells,
  PartsListHeader,
  PartsRow,
  ProvenanceLegend,
  RedlineCallout,
  RedlineMarker,
  RedlineSeverityKey,
  Ruler,
  Sheet,
  SheetSection,
  VerdictStamp,
  type Provenance,
} from '../components/sheet'

// demonstrated_level doubles as evidence depth: 1–2 claimed (dotted),
// 3–4 observed (dashed), 5 demonstrated (solid). The line style of a
// dimension therefore carries its provenance; the legend fixes the code.
function provenance(level: number | null | undefined): Provenance {
  if (!level || level <= 2) return 'claimed'
  if (level <= 4) return 'observed'
  return 'demonstrated'
}

export function DashboardPage() {
  const navigate = useNavigate()
  const candidate = useCandidate(DEFAULT_USER_ID)
  const { activeId } = useResolvedProfile(DEFAULT_USER_ID)
  const readiness = useReadiness(DEFAULT_USER_ID, activeId)
  const preparation = usePreparation(DEFAULT_USER_ID, activeId)
  const progress = useProgress(DEFAULT_USER_ID, activeId)
  const documents = useDocuments(DEFAULT_USER_ID, activeId)
  const roles = useRoles(DEFAULT_USER_ID, activeId)

  const loading = candidate.isLoading || readiness.isLoading
  const targetRole = roles.data?.at(-1)
  const hasResume = documents.data?.some((d) => d.kind === 'resume' && d.status === 'parsed')
  const hasRole = Boolean(targetRole)
  const readinessVal = readiness.data?.overall ?? 0
  const gaps = readiness.data?.critical_gaps ?? []
  const topGap = gaps[0]
  const topPrep = preparation.data?.[0]
  const series = progress.data?.series ?? []
  const prepItems = preparation.data ?? []

  // ApiError carries `status`; a 404 simply means the single-user profile
  // doesn't exist yet → show the onboarding empty state, not an error.
  const candidateMissing = candidate.isError && candidate.error instanceof ApiError && candidate.error.status === 404

  // Weakest critical competencies first, so the drawing reads as "what to
  // fix". Registered scale: every row's cells land on the shared ruler.
  // Computed before the error early-return so hook order stays stable.
  const competenceRows = useMemo(() => {
    const rows = readiness.data?.per_competency ?? []
    const rank: Record<string, number> = { critical: 0, important: 1, nice_to_have: 2, 'nice-to-have': 2 }
    return [...rows].sort((a, b) => (rank[a.importance] ?? 1) - (rank[b.importance] ?? 1) || a.score - b.score)
  }, [readiness.data])

  if (candidate.isError && !candidateMissing) {
    return (
      <div className="mx-auto max-w-lg">
        <ErrorState
          title="We couldn't load your profile"
          body={candidate.error instanceof Error ? candidate.error.message : undefined}
          onRetry={() => candidate.refetch()}
        />
      </div>
    )
  }

  const unstarted = !hasResume && !hasRole
  const noSnapshot = !readiness.isLoading && !readiness.data

  // A readiness snapshot counts as VERIFIED only when a deterministic
  // measurement actually exists (competencies and/or gaps and/or coverage).
  // An empty/zeroed snapshot is NOT_ASSESSED — never a verified score of
  // zero.
  const assessed = !unstarted && !noSnapshot && Boolean(
    readiness.data &&
      (competenceRows.length > 0 || gaps.length > 0 || (readiness.data.evidence_coverage ?? 0) > 0),
  )

  // Cross-reference: redline callout index → same numbered marker in the
  // drawing, matched by competency name (per_competency carries no id).
  // Only the callouts actually rendered in the margin (first 5) get markers,
  // so every marker always has a matching callout.
  const gapIndexByName = new Map<string, number>(gaps.slice(0, 5).map((g, i) => [g.name, i + 1]))

  const queueMinutes = prepItems.reduce((sum, item) => sum + (item.estimated_minutes ?? 15), 0)
  const drawnDate = readiness.data?.created_at
    ? new Date(readiness.data.created_at).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' })
    : '—'

  const ghostBand = (
    <li className="grid w-full grid-cols-[7.5rem_minmax(0,1fr)_5rem] items-center gap-x-3 px-1 py-2">
      <div className="min-w-0">
        <p className="truncate text-[13px] font-semibold text-ink-2">Required competencies</p>
        <p className="mt-0.5 text-[10px] font-semibold uppercase tracking-[0.1em] text-ink-2">awaiting assessment</p>
      </div>
      <LevelCells level={0} />
      {/* em dash = not measured (drafting convention), never a scored 0 */}
      <p className="stencil text-right text-[15px] leading-none text-ink-3">—/5</p>
    </li>
  )

  return (
    <div className="space-y-6">
      <Sheet aria-label="Readiness drawing sheet">
        {/* ── Title block: verdict stamp + drawing identity ───────────── */}
        <header className="border-b border-ink/25">
          <div className="flex flex-wrap items-start justify-between gap-x-8 gap-y-5 px-6 pb-5 pt-5">
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-ink-2">
                  Pramya · Readiness Overview
                </p>
                {targetRole ? (
                  <p className="text-[10px] uppercase tracking-[0.1em] text-ink-3">
                    {targetRole.seniority ?? ''} {targetRole.title}
                  </p>
                ) : null}
              </div>
              <h1 className="mt-1.5 text-[22px] font-semibold tracking-tight text-ink sm:text-2xl">
                {loading
                  ? 'Loading your readiness…'
                  : !assessed
                    ? unstarted
                      ? 'Set up your profile and role to begin.'
                      : `Not assessed yet — compute readiness for ${targetRole?.title ?? 'your target role'}.`
                    : `You're ${readinessVal >= 7 ? 'well positioned' : readinessVal >= 4 ? 'making progress' : 'at the start'} for ${targetRole?.title ?? 'your target role'}.`}
              </h1>
              <p className="mt-1 text-sm text-ink-2">
                {candidate.data?.headline ?? 'Set up your profile and target role to begin.'}
              </p>
              <div className="mt-3.5">
                <ProvenanceLegend />
              </div>
            </div>

            <VerdictStamp
              loading={loading}
              assessed={assessed}
              value={readiness.data?.overall ?? null}
              confidence={readiness.data?.confidence ?? 0}
              coverage={readiness.data?.evidence_coverage ?? 0}
              gapCount={gaps.length}
              date={drawnDate}
            />
          </div>
        </header>

        {unstarted || noSnapshot || loading ? (
          /* ── Frame state: skeleton or UNASSESSED frame ─────────────── */
          <div className="grid lg:grid-cols-12">
            <SheetSection title="Parts list — preparation order" tone="shadow" className="border-t lg:col-start-1 lg:col-span-3">
              {loading ? (
                <Skeleton className="h-28 w-full" />
              ) : (
                <>
                  <p className="text-[13px] font-semibold text-ink">No preparation order yet</p>
                  <p className="mt-1 text-[11px] leading-snug text-ink-2">
                    {unstarted
                      ? "Pramya is evidence-driven: we build your readiness from your resume claims, a target role's competency model, and what you demonstrate in practice. Begin by adding your profile and role."
                      : 'Compute readiness after analyzing a role to generate an order.'}
                  </p>
                  <Button size="sm" className="mt-3 w-full" onClick={() => navigate(unstarted ? '/setup' : '/preparation')}>
                    {unstarted ? 'Set up profile & role →' : 'Compute readiness →'}
                  </Button>
                </>
              )}
            </SheetSection>

            <SheetSection
              title="Readiness drawing — dimensioned"
              tone="lit"
              className="border-t lg:col-start-4 lg:col-span-6 lg:border-x"
              aside={<span className="text-[10px] uppercase tracking-[0.1em] text-ink-2">fixed scale · level /5 · score /10</span>}
            >
              {loading ? (
                <div className="space-y-3">
                  <Skeleton className="h-10 w-full" />
                  <Skeleton className="h-10 w-full" />
                  <Skeleton className="h-10 w-full" />
                </div>
              ) : (
                <>
                  <ul className="border-b border-ink/10">{ghostBand}</ul>
                  <div className="px-1 pb-2">
                    <DimensionLine style="claimed" />
                  </div>
                  <p className="stencil px-1 pt-1 text-[10px] uppercase tracking-[0.12em] text-redline">
                    unassessed — no measurements on file
                  </p>
                  <p className="mt-1 px-1 text-[11px] leading-relaxed text-ink-2">
                    {unstarted
                      ? 'Add a profile and target role to draw the competency dimension set.'
                      : 'Analyze a role and compute readiness to draw the dimension set.'}
                  </p>
                  <Ruler className="mt-3" />
                </>
              )}
            </SheetSection>

            <SheetSection title="Redline — critical gaps" tone="shadow" className="border-t lg:col-start-10 lg:col-span-3" aside={<span className="stencil text-[10px]">{gaps.length}</span>}>
              {loading ? (
                <Skeleton className="h-24 w-full" />
              ) : (
                <div className="py-1.5">
                  <p className="stencil text-[10px] uppercase tracking-[0.12em] text-redline">not verified</p>
                  <p className="mt-1.5 text-[12px] leading-relaxed text-ink-2">
                    No gaps identified — gaps can only be assessed after a readiness snapshot exists.
                  </p>
                </div>
              )}
            </SheetSection>
          </div>
        ) : (
          /* ── Measured state ────────────────────────────────────────── */
          <div className="grid lg:grid-cols-12">
            {/* BOM: preparation order (hierarchy #4 — the next action) */}
            <SheetSection title="Parts list — preparation order" tone="shadow" className="border-t lg:col-start-1 lg:col-span-3">
              {topPrep ? (
                <>
                  <PartsListHeader />
                  <ul className="divide-y divide-ink/10 border-y border-ink/10">
                    <PartsRow
                      index="01"
                      next
                      name={topPrep.competency_name ?? 'Practice'}
                      reason={topPrep.reason}
                      minutes={topPrep.estimated_minutes}
                      priority={topPrep.priority}
                    />
                    {prepItems.slice(1, 5).map((item, i) => (
                      <PartsRow
                        key={item.id}
                        index={String(i + 2).padStart(2, '0')}
                        name={item.competency_name ?? 'Practice'}
                        reason={item.reason}
                        minutes={item.estimated_minutes}
                        priority={item.priority}
                      />
                    ))}
                  </ul>
                  <div className="mt-3 border-t border-ink/15 pt-2.5">
                    <div className="stencil flex items-baseline justify-between text-[10px] uppercase tracking-[0.1em] text-ink-2">
                      <span>queue ≈ {queueMinutes} min</span>
                      {topPrep.expected_improvement != null ? (
                        <span className="text-draft">gain ≈ +{topPrep.expected_improvement.toFixed(1)}</span>
                      ) : null}
                    </div>
                    <Button size="sm" className="mt-2.5 w-full" onClick={() => navigate('/interview')}>
                      Start practice — {topPrep.competency_name ?? 'top item'} →
                    </Button>
                  </div>
                </>
              ) : topGap ? (
                <div className="py-1">
                  <p className="text-[13px] font-semibold text-ink">No plan yet</p>
                  <p className="mt-1 text-[11px] leading-snug text-ink-2">
                    {topGap.name} needs attention — build a preparation order from your critical gaps.
                  </p>
                  <Button size="sm" className="mt-3 w-full" onClick={() => navigate('/preparation')}>
                    Build a plan →
                  </Button>
                </div>
              ) : (
                <p className="text-[12px] leading-relaxed text-ink-2">
                  Ready to practice — no critical gaps. Keep demonstrating what you know.
                </p>
              )}
            </SheetSection>

            {/* Drawing: dimensioned competencies (hierarchy #5 — the model) */}
            <SheetSection
              title="Readiness drawing — dimensioned"
              tone="lit"
              className="border-t lg:col-start-4 lg:col-span-6 lg:border-x"
              aside={<span className="text-[10px] uppercase tracking-[0.1em] text-ink-2">fixed scale · level /5 · score /10</span>}
            >
              {competenceRows.length === 0 ? (
                <>
                  <ul className="border-b border-ink/10">{ghostBand}</ul>
                  <div className="px-1 pb-2">
                    <DimensionLine style="claimed" />
                  </div>
                  <p className="mt-1 px-1 text-[11px] leading-relaxed text-ink-2">
                    No competency measurements yet — compute readiness after analyzing a role.
                  </p>
                  <Ruler className="mt-3" />
                </>
              ) : (
                <>
                  <ul>
                    {competenceRows.map((c) => {
                      const marker = gapIndexByName.get(c.name)
                      return (
                        <li key={c.name}>
                          <button
                            type="button"
                            onClick={() => navigate('/evidence')}
                            aria-label={`${c.name}: demonstrated level ${c.demonstrated_level} of 5, score ${c.score.toFixed(1)} of 10, coverage ${Math.round((c.evidence_coverage ?? 0) * 100)}%, confidence ${Math.round((c.confidence ?? 0) * 100)}%. Opens the evidence ledger.`}
                            className="group grid w-full grid-cols-[7.5rem_minmax(0,1fr)_5rem] items-center gap-x-3 px-1 py-2 text-left transition-colors hover:bg-draft-soft/40 focus-visible:outline-none"
                          >
                            <div className="min-w-0">
                              <p className="truncate text-[13px] font-semibold text-ink">{c.name}</p>
                              <p className="mt-0.5 text-[10px] font-semibold uppercase tracking-[0.1em] text-ink-2">{c.importance}</p>
                            </div>
                            <LevelCells level={c.demonstrated_level} />
                            <div className="flex flex-col items-end gap-1">
                              <span className="flex items-center gap-1.5">
                                {marker ? <RedlineMarker index={marker} /> : null}
                                <span className="stencil text-[15px] leading-none text-ink">
                                  {c.demonstrated_level}
                                  <span className="text-[10px] text-ink-2">/5</span>
                                </span>
                              </span>
                              <span className="stencil text-[11px] leading-none text-ink-2">{c.score.toFixed(1)}/10</span>
                              <span className="tabular text-[10px] leading-none text-ink-2">
                                cov {Math.round((c.evidence_coverage ?? 0) * 100)} · conf {Math.round((c.confidence ?? 0) * 100)}
                              </span>
                              <span className="stencil text-[10px] uppercase tracking-[0.1em] text-draft opacity-0 transition-opacity group-hover:opacity-100 group-focus-visible:opacity-100">
                                → ledger
                              </span>
                            </div>
                          </button>
                          <div className="px-1 pb-2.5">
                            <DimensionLine style={provenance(c.demonstrated_level)} />
                          </div>
                        </li>
                      )
                    })}
                  </ul>
                  <Ruler className="mt-1 px-1" />
                </>
              )}
            </SheetSection>

            {/* Redline call-outs: critical gaps (hierarchy #3) */}
            <SheetSection
              title="Redline — critical gaps"
              tone="shadow"
              className="border-t lg:col-start-10 lg:col-span-3"
              aside={<span className="stencil text-[10px]">{gaps.length}</span>}
            >
              {gaps.length === 0 ? (
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
                  <footer className="mt-2.5">
                    <button
                      className="stencil text-[10px] font-semibold uppercase tracking-[0.1em] text-draft underline underline-offset-2 hover:text-draft-2"
                      onClick={() => navigate('/evidence')}
                    >
                      View evidence ledger →
                    </button>
                  </footer>
                </>
              )}
            </SheetSection>
          </div>
        )}

        {/* ── Revision strip: status fields + fixed-scale change ──────── */}
        {!unstarted && !loading ? (
          <footer className="border-t border-ink/25">
            <div className="grid gap-5 px-6 py-3.5 lg:grid-cols-[minmax(0,12rem)_minmax(0,1fr)]">
              <div>
                <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-ink-2">Revision · status</p>
                <dl className="mt-2 space-y-1">
                  <div className="flex items-baseline justify-between gap-3 text-[11px]">
                    <dt className="text-ink-2">evaluations</dt>
                    <dd className="tabular text-ink">{progress.data?.total_evaluations ?? 0}</dd>
                  </div>
                  <div className="flex items-baseline justify-between gap-3 text-[11px]">
                    <dt className="text-ink-2">sessions</dt>
                    <dd className="tabular text-ink">{progress.data?.sessions ?? 0}</dd>
                  </div>
                  <div className="flex items-baseline justify-between gap-3 text-[11px]">
                    <dt className="text-ink-2">average</dt>
                    <dd className="tabular text-ink">
                      {progress.data?.average_overall != null ? progress.data.average_overall.toFixed(1) : '—'}
                    </dd>
                  </div>
                </dl>
              </div>
              <div className="min-w-0">
                <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-ink-2">Recent change — fixed scale</p>
                {series.length === 0 ? (
                  <p className="mt-2 text-[11px] text-ink-2">Complete an interview to see movement.</p>
                ) : (
                  <div className="mt-2.5 space-y-1.5">
                    {series.map((s) => (
                      <FixedScaleBar key={s.name} name={s.name} latest={s.latest} trend={s.trend} />
                    ))}
                  </div>
                )}
              </div>
            </div>
          </footer>
        ) : null}
      </Sheet>
    </div>
  )
}
