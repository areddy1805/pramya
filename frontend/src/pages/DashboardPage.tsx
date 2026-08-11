import { useNavigate } from 'react-router-dom'
import { useCandidate, useDocuments, usePreparation, useProgress, useReadiness, useRoles, DEFAULT_USER_ID } from '../hooks/queries'
import { Button, Divider, EmptyState, ErrorState, Meter, Pill, SectionHeading, Skeleton, Stat, Surface } from '../components/ui'

export function DashboardPage() {
  const navigate = useNavigate()
  const candidate = useCandidate(DEFAULT_USER_ID)
  const readiness = useReadiness(DEFAULT_USER_ID)
  const preparation = usePreparation(DEFAULT_USER_ID)
  const progress = useProgress(DEFAULT_USER_ID)
  const documents = useDocuments(DEFAULT_USER_ID)
  const roles = useRoles(DEFAULT_USER_ID)

  const loading = candidate.isLoading || readiness.isLoading
  const targetRole = roles.data?.at(-1)
  const hasResume = documents.data?.some((d) => d.kind === 'resume' && d.status === 'parsed')
  const hasRole = Boolean(targetRole)
  const readinessVal = readiness.data?.overall ?? 0
  const gaps = readiness.data?.critical_gaps ?? []
  const topGap = gaps[0]
  const topPrep = preparation.data?.[0]
  const series = progress.data?.series ?? []

  if (candidate.isError) {
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
          <p className="text-xs font-medium uppercase tracking-[0.08em] text-ink-400">
            {targetRole ? `Target role · ${targetRole.seniority ?? ''} ${targetRole.title}` : 'No target role yet'}
          </p>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight">
            {loading ? 'Loading your readiness…' : `You're ${readinessVal >= 7 ? 'well positioned' : readinessVal >= 4 ? 'making progress' : 'at the start'} for ${targetRole?.title ?? 'your target role'}.`}
          </h1>
          <p className="mt-1 text-sm text-ink-500">
            {candidate.data?.headline ?? 'Set up your profile and target role to begin.'}
          </p>
        </div>
        <Button variant="secondary" onClick={() => navigate('/setup')}>
          {unstarted ? 'Set up profile' : 'Edit profile & role'}
        </Button>
      </header>

      {unstarted ? (
        <EmptyState
          icon="🎯"
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
          <Surface tone="accent" className="p-6">
            <div className="grid gap-6 md:grid-cols-[1fr_auto]">
              <div className="min-w-0">
                <SectionHeading>Overall readiness</SectionHeading>
                <div className="flex items-baseline gap-2">
                  <span className="text-4xl font-semibold tracking-tight">{readinessVal.toFixed(1)}</span>
                  <span className="text-sm text-ink-400">/ 10</span>
                  {readiness.data ? <Pill tone={readinessVal >= 7 ? 'ok' : readinessVal >= 4 ? 'warn' : 'danger'}>{readinessVal >= 7 ? 'On track' : readinessVal >= 4 ? 'Building' : 'Early'}</Pill> : null}
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
                  <p className="mt-4 text-sm text-ink-500">
                    No snapshot yet — <button className="font-medium text-accent-700 underline" onClick={() => navigate('/preparation')}>compute readiness</button> after analyzing a role.
                  </p>
                ) : null}
              </div>

              {/* The one action that matters next */}
              <div className="flex w-full flex-col justify-center gap-3 md:w-64">
                <p className="text-xs font-medium uppercase tracking-[0.08em] text-ink-400">Do this next</p>
                {topPrep ? (
                  <>
                    <div className="rounded-lg border border-ink-200 bg-white p-4">
                      <p className="text-sm font-semibold text-ink-800">{topPrep.competency_name ?? 'Practice'}</p>
                      <p className="mt-1 text-xs leading-relaxed text-ink-500">{topPrep.reason}</p>
                      <p className="mt-2 text-xs text-ink-400">≈ {topPrep.estimated_minutes ?? 15} min · priority {topPrep.priority}</p>
                    </div>
                    <Button onClick={() => navigate('/interview')}>Start practice →</Button>
                  </>
                ) : topGap ? (
                  <>
                    <div className="rounded-lg border border-ink-200 bg-white p-4">
                      <p className="text-sm font-semibold text-ink-800">{topGap.name}</p>
                      <p className="mt-1 text-xs text-ink-500">demonstrated {topGap.demonstrated_level}/5 vs required {topGap.required_level}/5</p>
                    </div>
                    <Button onClick={() => navigate('/preparation')}>Build a plan →</Button>
                  </>
                ) : (
                  <div className="rounded-lg border border-ink-200 bg-white p-4">
                    <p className="text-sm font-semibold text-ink-800">Ready to practice</p>
                    <p className="mt-1 text-xs text-ink-500">No critical gaps. Keep demonstrating what you know.</p>
                  </div>
                )}
              </div>
            </div>
          </Surface>

          <div className="grid gap-6 lg:grid-cols-2">
            <Surface className="p-5">
              <SectionHeading>Critical gaps</SectionHeading>
              {!gaps.length ? (
                <p className="text-sm text-ink-500">No required competency is below target.</p>
              ) : (
                <ul className="space-y-3">
                  {gaps.slice(0, 5).map((gap) => (
                    <li key={gap.competency_id} className="flex items-center justify-between gap-3">
                      <div className="min-w-0">
                        <p className="text-sm font-medium text-ink-800">{gap.name}</p>
                        <p className="text-xs text-ink-400">demonstrated {gap.demonstrated_level}/5 · required {gap.required_level}/5</p>
                      </div>
                      <Pill tone="danger">gap {gap.gap}</Pill>
                    </li>
                  ))}
                </ul>
              )}
            </Surface>

            <Surface className="p-5">
              <SectionHeading>Recent change</SectionHeading>
              {!series.length ? (
                <p className="text-sm text-ink-500">Complete an interview to see movement.</p>
              ) : (
                <ul className="space-y-4">
                  {series.map((s) => (
                    <li key={s.name}>
                      <div className="mb-1 flex items-center justify-between text-sm">
                        <span className="font-medium text-ink-700">{s.name}</span>
                        <span className="text-xs text-ink-400">
                          {s.latest?.toFixed(1)}
                          {s.trend != null ? (
                            <span className={`ml-1.5 ${s.trend >= 0 ? 'text-ok-700' : 'text-danger-700'}`}>
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
                <span className="text-ink-500">Evaluations</span>
                <span className="font-medium">{progress.data?.total_evaluations ?? 0} across {progress.data?.sessions ?? 0} sessions</span>
              </div>
            </Surface>
          </div>
        </>
      )}

      {loading ? (
        <div className="grid gap-6 lg:grid-cols-2">
          <Skeleton className="h-40" />
          <Skeleton className="h-40" />
        </div>
      ) : null}
    </div>
  )
}
