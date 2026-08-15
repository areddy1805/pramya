import { useNavigate } from 'react-router-dom'
import { ApiError } from '../lib/api'
import { useCandidate, useDocuments, usePreparation, useProgress, useReadiness, useRoles, useResolvedProfile, DEFAULT_USER_ID } from '../hooks/queries'
import { Button, Divider, EmptyState, ErrorState, Meter, Micro, SectionHeading, Skeleton, Stat, Surface } from '../components/ui'

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

  return (
    <div className="space-y-8">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <Micro>
            {targetRole ? `Target role · ${targetRole.seniority ?? ''} ${targetRole.title}` : 'No target role yet'}
          </Micro>
          <h1 className="mt-1 text-xl font-semibold tracking-tight">
            {loading ? 'Loading your readiness…' : `You're ${readinessVal >= 7 ? 'well positioned' : readinessVal >= 4 ? 'making progress' : 'at the start'} for ${targetRole?.title ?? 'your target role'}.`}
          </h1>
          <p className="mt-1 text-sm text-fg-2">
            {candidate.data?.headline ?? 'Set up your profile and target role to begin.'}
          </p>
        </div>
        <Button variant="secondary" onClick={() => navigate('/setup')}>
          {unstarted ? 'Set up profile' : 'Edit profile & role'}
        </Button>
      </header>

      {unstarted ? (
        <EmptyState
         
          title="Start with your target"
          body="Pramya is evidence-driven: we build your readiness from your resume claims, a target role's competency model, and what you demonstrate in practice. Begin by adding your profile and role."
          action={
            <Button size="lg" onClick={() => navigate('/setup')}>
              Set up profile & role →
            </Button>
          }
        />
      ) : (
        <>
          {/* Dominant surface: readiness with reason */}
          <Surface className="p-6">
            <div className="grid gap-6 md:grid-cols-[1fr_auto]">
              <div className="min-w-0">
                <SectionHeading>Overall readiness</SectionHeading>
                <div className="flex items-baseline gap-2">
                  <span className={`tabular text-4xl font-semibold tracking-tight ${readinessVal >= 7.5 ? 'text-ok' : readinessVal >= 5 ? 'text-fg' : 'text-warn'}`}>{readinessVal.toFixed(1)}</span>
                  <span className="text-sm text-fg-3">/ 10</span>
                </div>
                <div className="mt-3 max-w-md">
                  <Meter value={readinessVal} />
                </div>
                <div className="mt-4 flex flex-wrap gap-x-8 gap-y-2">
                  <Stat label="Confidence" value={`${Math.round((readiness.data?.confidence ?? 0) * 100)}%`} sub="in the assessment" />
                  <Stat label="Evidence coverage" value={`${Math.round((readiness.data?.evidence_coverage ?? 0) * 100)}%`} sub="of required competencies" />
                  <Stat label="Critical gaps" value={gaps.length} sub="required competencies below target" />
                </div>
                {!readiness.data && !readiness.isLoading ? (
                  <p className="mt-4 text-sm text-fg-2">
                    No snapshot yet — <button className="font-medium text-accent underline" onClick={() => navigate('/preparation')}>compute readiness</button> after analyzing a role.
                  </p>
                ) : null}
              </div>

              {/* The one action that matters next */}
              <div className="flex w-full flex-col justify-center gap-3 md:w-64">
                <Micro>Do this next</Micro>
                {topPrep ? (
                  <>
                    <div className="rounded-lg border border-line bg-surface p-4">
                      <p className="text-sm font-semibold text-fg">{topPrep.competency_name ?? 'Practice'}</p>
                      <p className="mt-1 text-xs leading-relaxed text-fg-2">{topPrep.reason}</p>
                      <p className="mt-2 text-xs text-fg-3">≈ {topPrep.estimated_minutes ?? 15} min · priority {topPrep.priority}</p>
                    </div>
                    <Button onClick={() => navigate('/interview')}>Start practice →</Button>
                  </>
                ) : topGap ? (
                  <>
                    <div className="rounded-lg border border-line bg-surface p-4">
                      <p className="text-sm font-semibold text-fg">{topGap.name}</p>
                      <p className="mt-1 text-xs text-fg-2">demonstrated {topGap.demonstrated_level}/5 vs required {topGap.required_level}/5</p>
                    </div>
                    <Button onClick={() => navigate('/preparation')}>Build a plan →</Button>
                  </>
                ) : (
                  <div className="rounded-lg border border-line bg-surface p-4">
                    <p className="text-sm font-semibold text-fg">Ready to practice</p>
                    <p className="mt-1 text-xs text-fg-2">No critical gaps. Keep demonstrating what you know.</p>
                  </div>
                )}
              </div>
            </div>
          </Surface>

          <div className="grid grid-cols-[minmax(0,1fr)] gap-6 lg:grid-cols-2">
            <Surface className="p-5">
              <SectionHeading>Critical gaps</SectionHeading>
              {!gaps.length ? (
                <p className="text-sm text-fg-2">No required competency is below target.</p>
              ) : (
                <ul className="space-y-3">
                  {gaps.slice(0, 5).map((gap) => (
                    <li key={gap.competency_id} className="flex items-center justify-between gap-3">
                      <div className="min-w-0">
                        <p className="text-sm font-medium text-fg">{gap.name}</p>
                        <p className="text-xs text-fg-3">demonstrated {gap.demonstrated_level}/5 · required {gap.required_level}/5</p>
                      </div>
                      <span className="shrink-0 text-xs font-semibold text-danger">gap {gap.gap}</span>
                    </li>
                  ))}
                </ul>
              )}
            </Surface>

            <Surface className="p-5">
              <SectionHeading>Recent change</SectionHeading>
              {!series.length ? (
                <p className="text-sm text-fg-2">Complete an interview to see movement.</p>
              ) : (
                <ul className="space-y-4">
                  {series.map((s) => (
                    <li key={s.name}>
                      <div className="mb-1 flex items-center justify-between text-sm">
                        <span className="font-medium text-fg">{s.name}</span>
                        <span className="text-xs text-fg-3">
                          {s.latest?.toFixed(1)}
                          {s.trend != null ? (
                            <span className={`ml-1.5 ${s.trend >= 0 ? 'text-ok' : 'text-danger'}`}>
                              {s.trend >= 0 ? `▲ +${s.trend.toFixed(1)}` : `▼ ${s.trend.toFixed(1)}`}
                            </span>
                          ) : null}
                        </span>
                      </div>
                      <Meter value={s.latest ?? 0} />
                    </li>
                  ))}
                </ul>
              )}
              <Divider className="my-4" />
              <div className="flex items-center justify-between text-sm">
                <span className="text-fg-2">Evaluations</span>
                <span className="font-medium">{progress.data?.total_evaluations ?? 0} across {progress.data?.sessions ?? 0} sessions</span>
              </div>
            </Surface>
          </div>
        </>
      )}

      {loading ? (
        <div className="grid grid-cols-[minmax(0,1fr)] gap-6 lg:grid-cols-2">
          <Skeleton className="h-40" />
          <Skeleton className="h-40" />
        </div>
      ) : null}
    </div>
  )
}
