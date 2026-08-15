import { useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { ApiError } from '../lib/api'
import { useCandidate, useDocuments, usePreparation, useProgress, useReadiness, useRoles, useResolvedProfile, DEFAULT_USER_ID } from '../hooks/queries'
import { Button, ErrorState, Skeleton } from '../components/ui'
import {
  CoverageHatch,
  DimensionLine,
  FixedScaleBar,
  LevelCells,
  PartsRow,
  ProvenanceLegend,
  RedlineCallout,
  Sheet,
  SheetSection,
  StencilNum,
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

function BasisField({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="min-w-0">
      <p className="text-[10px] font-semibold uppercase tracking-[0.1em] text-ink-2">{label}</p>
      <StencilNum className="mt-1 block text-lg leading-none text-ink">{value}</StencilNum>
      {sub ? <p className="mt-1 truncate text-[10px] text-ink-2">{sub}</p> : null}
    </div>
  )
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

  // ApiError carries `status`; a 404 simply means the single-user profile
  // doesn't exist yet → show the onboarding empty state, not an error.
  const candidateMissing = candidate.isError && candidate.error instanceof ApiError && candidate.error.status === 404

  // Weakest critical competencies first, so the drawing reads as "what to
  // fix". Registered scale: every row is a 5-cell strip. Computed before
  // the error early-return so hook order stays stable.
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

  const verdictTone = readinessVal >= 7.5 ? 'text-draft' : readinessVal >= 5 ? 'text-ink' : 'text-redline'
  const drawnDate = readiness.data?.created_at
    ? new Date(readiness.data.created_at).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' })
    : '—'

  return (
    <div className="space-y-6">
      <Sheet aria-label="Readiness drawing sheet">
        {/* ── Title block: verdict + basis ─────────────────────────────── */}
        <header className="border-b border-ink/25">
          <div className="flex flex-wrap items-start justify-between gap-x-8 gap-y-5 px-6 pb-6 pt-6">
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-ink-2">
                  Pramya · Readiness Overview
                </p>
                {targetRole ? (
                  <p className="text-[11px] tracking-[0.08em] text-ink-3">
                    {targetRole.seniority ?? ''} {targetRole.title}
                  </p>
                ) : null}
              </div>
              <h1 className="mt-2 text-2xl font-semibold tracking-tight text-ink sm:text-[28px]">
                {loading
                  ? 'Loading your readiness…'
                  : `You're ${readinessVal >= 7 ? 'well positioned' : readinessVal >= 4 ? 'making progress' : 'at the start'} for ${targetRole?.title ?? 'your target role'}.`}
              </h1>
              <p className="mt-1.5 text-sm text-ink-2">
                {candidate.data?.headline ?? 'Set up your profile and target role to begin.'}
              </p>
              <div className="mt-4">
                <ProvenanceLegend />
              </div>
            </div>

            <div className="flex w-full shrink-0 flex-col items-stretch gap-3 sm:w-80">
              <div className="flex justify-end">
                <Button variant="secondary" onClick={() => navigate('/setup')}>
                  {unstarted ? 'Set up profile' : 'Edit profile & role'}
                </Button>
              </div>
              <div className="border border-ink/25 bg-sheet-lit/40 px-4 py-3">
                <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-ink-2">Readiness verdict</p>
                {loading ? (
                  <Skeleton className="mt-2 h-12 w-32" />
                ) : noSnapshot ? (
                  <div className="mt-2 flex h-12 items-center">
                    <span className="stencil text-xl tracking-tight text-ink-3">NO SNAPSHOT</span>
                  </div>
                ) : (
                  <div className="mt-1 flex items-baseline gap-1.5">
                    <span className={`stencil text-5xl leading-none ${verdictTone}`}>{readinessVal.toFixed(1)}</span>
                    <span className="text-sm text-ink-2">/ 10</span>
                  </div>
                )}
                <div className="mt-3 grid grid-cols-3 gap-2 border-t border-ink/20 pt-3">
                  <BasisField label="Confidence" value={`${Math.round((readiness.data?.confidence ?? 0) * 100)}%`} sub="in the assessment" />
                  <BasisField label="Coverage" value={`${Math.round((readiness.data?.evidence_coverage ?? 0) * 100)}%`} sub="of required comps" />
                  <BasisField label="Gaps" value={String(gaps.length)} sub="below target" />
                </div>
                {noSnapshot ? (
                  <p className="mt-3 border-t border-ink/20 pt-2.5 text-[11px] leading-relaxed text-ink-2">
                    No snapshot yet —{' '}
                    <button
                      className="stencil text-[11px] text-draft underline underline-offset-2 hover:text-draft-2"
                      onClick={() => navigate('/preparation')}
                    >
                      compute readiness
                    </button>{' '}
                    after analyzing a role.
                  </p>
                ) : null}
              </div>
            </div>
          </div>
        </header>

        {unstarted ? (
          /* ── No inputs yet: onboarding ──────────────────────────────── */
          <SheetSection title="No inputs — begin" tone="shadow" className="border-t">
            <div className="max-w-xl py-4">
              <p className="text-sm font-semibold text-ink">Start with your target</p>
              <p className="mt-1.5 text-sm leading-relaxed text-ink-2">
                Pramya is evidence-driven: we build your readiness from your resume claims, a target role's competency
                model, and what you demonstrate in practice. Begin by adding your profile and role.
              </p>
              <Button size="lg" className="mt-5" onClick={() => navigate('/setup')}>
                Set up profile &amp; role →
              </Button>
            </div>
          </SheetSection>
        ) : loading ? (
          /* ── Sheet under construction ───────────────────────────────── */
          <div className="grid lg:grid-cols-12">
            <div className="border-t border-ink/20 px-6 py-5 lg:col-start-1 lg:col-span-3">
              <Skeleton className="h-3 w-24" />
              <Skeleton className="mt-3 h-32 w-full" />
            </div>
            <div className="border-t border-ink/20 px-6 py-5 lg:col-start-4 lg:col-span-6 lg:border-x">
              <Skeleton className="h-3 w-28" />
              <div className="mt-3 space-y-3">
                <Skeleton className="h-12 w-full" />
                <Skeleton className="h-12 w-full" />
                <Skeleton className="h-12 w-full" />
              </div>
            </div>
            <div className="border-t border-ink/20 px-6 py-5 lg:col-start-10 lg:col-span-3">
              <Skeleton className="h-3 w-24" />
              <Skeleton className="mt-3 h-24 w-full" />
            </div>
          </div>
        ) : (
          <div className="grid lg:grid-cols-12">
            {/* ── Redline call-outs: critical gaps (hierarchy #3) ────── */}
            <SheetSection
              title="Redline — critical gaps"
              tone="shadow"
              className="border-t lg:col-start-10 lg:col-span-3"
            >
              {gaps.length === 0 ? (
                <p className="text-[13px] leading-relaxed text-ink-2">No required competency is below target.</p>
              ) : (
                <ul className="space-y-2.5">
                  {gaps.slice(0, 5).map((gap) => (
                    <RedlineCallout
                      key={gap.competency_id}
                      name={gap.name}
                      demonstrated={gap.demonstrated_level}
                      required={gap.required_level}
                      gap={gap.gap}
                    />
                  ))}
                </ul>
              )}
              <footer className="mt-4 border-t border-ink/15 pt-3">
                <button
                  className="text-[10px] font-semibold uppercase tracking-[0.1em] text-draft underline underline-offset-2 hover:text-draft-2"
                  onClick={() => navigate('/evidence')}
                >
                  View evidence ledger →
                </button>
              </footer>
            </SheetSection>

            {/* ── Parts list: preparation queue (hierarchy #4) ────────── */}
            <SheetSection title="Parts list — preparation order" tone="shadow" className="border-t lg:col-start-1 lg:col-span-3">
              {topPrep ? (
                <ul className="space-y-2.5">
                  <PartsRow
                    index="01"
                    next
                    name={topPrep.competency_name ?? 'Practice'}
                    reason={topPrep.reason}
                    minutes={topPrep.estimated_minutes}
                    priority={topPrep.priority}
                    status={topPrep.status}
                    action={
                      <Button size="sm" onClick={() => navigate('/interview')}>
                        Start practice →
                      </Button>
                    }
                  />
                  {preparation.data?.slice(1, 5).map((item, i) => (
                    <PartsRow
                      key={item.id}
                      index={String(i + 2).padStart(2, '0')}
                      name={item.competency_name ?? 'Practice'}
                      reason={item.reason}
                      minutes={item.estimated_minutes}
                      priority={item.priority}
                      status={item.status}
                    />
                  ))}
                </ul>
              ) : topGap ? (
                <div className="border border-ink/20 px-3 py-3">
                  <p className="text-[13px] font-semibold text-ink">No plan yet</p>
                  <p className="mt-1 text-[11px] leading-snug text-ink-2">
                    {topGap.name} needs attention — build a preparation order from your critical gaps.
                  </p>
                  <Button size="sm" className="mt-3" onClick={() => navigate('/preparation')}>
                    Build a plan →
                  </Button>
                </div>
              ) : (
                <p className="text-[13px] leading-relaxed text-ink-2">
                  Ready to practice — no critical gaps. Keep demonstrating what you know.
                </p>
              )}
            </SheetSection>

            {/* ── Readiness drawing: dimensioned competencies (#5) ────── */}
            <SheetSection
              title="Readiness drawing — dimensioned"
              tone="lit"
              className="border-t lg:col-start-4 lg:col-span-6 lg:border-x"
              aside={<span className="text-[10px] uppercase tracking-[0.1em] text-ink-2">scale · demonstrated / 5</span>}
            >
              {competenceRows.length === 0 ? (
                <p className="text-[13px] leading-relaxed text-ink-2">
                  No competency measurements yet — compute readiness after analyzing a role.
                </p>
              ) : (
                <ul className="divide-y divide-ink/10">
                  {competenceRows.map((c) => (
                    <li key={c.name}>
                      <button
                        type="button"
                        onClick={() => navigate('/evidence')}
                        aria-label={`${c.name}: demonstrated level ${c.demonstrated_level} of 5, confidence ${Math.round((c.confidence ?? 0) * 100)}%, evidence coverage ${Math.round((c.evidence_coverage ?? 0) * 100)}%. Opens the evidence ledger.`}
                        className="group w-full px-2 py-3 text-left transition-colors hover:bg-draft-soft/60 focus-visible:outline-none"
                      >
                        <div className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-4">
                          <div className="min-w-0">
                            <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
                              <span className="truncate text-[13px] font-semibold text-ink">{c.name}</span>
                              <span className="text-[9px] font-semibold uppercase tracking-[0.08em] text-ink-2">
                                {c.importance}
                              </span>
                            </div>
                            <DimensionLine style={provenance(c.demonstrated_level)} />
                          </div>
                          <div className="flex flex-col items-end gap-1.5">
                            <span className="stencil text-lg leading-none text-ink">
                              {c.demonstrated_level}
                              <span className="text-[11px] text-ink-2">/5</span>
                            </span>
                            <LevelCells level={c.demonstrated_level} />
                          </div>
                        </div>
                        <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1">
                          <CoverageHatch value={c.evidence_coverage ?? 0} />
                          <span className="tabular text-[11px] text-ink-2">conf {(c.confidence ?? 0).toFixed(2)}</span>
                          <span className="text-[10px] font-semibold uppercase tracking-[0.1em] text-draft opacity-0 transition-opacity group-hover:opacity-100 group-focus-visible:opacity-100">
                            → evidence ledger
                          </span>
                        </div>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </SheetSection>
          </div>
        )}

        {/* ── Revision strip: status fields + fixed-scale change ──────── */}
        {!unstarted && !loading ? (
          <footer className="border-t border-ink/25">
            <div className="grid gap-6 px-6 py-4 lg:grid-cols-[minmax(0,13rem)_minmax(0,1fr)]">
              <div>
                <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-ink-2">Revision · status</p>
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
                <p className="mt-3 border-t border-ink/15 pt-2 text-[10px] uppercase tracking-[0.1em] text-ink-2">
                  drawn · {drawnDate}
                </p>
              </div>
              <div className="min-w-0">
                <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-ink-2">
                  Recent change — fixed scale
                </p>
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
