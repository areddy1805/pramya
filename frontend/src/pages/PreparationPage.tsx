import { useNavigate } from 'react-router-dom'
import {
  useComputeReadiness,
  usePreparation,
  useReadiness,
  useRegeneratePreparation,
  useRoles,
  DEFAULT_USER_ID,
} from '../hooks/queries'
import { Button, EmptyState, ErrorState, Meter, Pill, SectionHeading, Skeleton, Spinner, Stat, Surface } from '../components/ui'

export function PreparationPage() {
  const navigate = useNavigate()
  const readiness = useReadiness(DEFAULT_USER_ID)
  const compute = useComputeReadiness(DEFAULT_USER_ID)
  const prep = usePreparation(DEFAULT_USER_ID)
  const regenerate = useRegeneratePreparation(DEFAULT_USER_ID)
  const roles = useRoles(DEFAULT_USER_ID)

  const roleId = roles.data?.at(-1)?.id
  const busy = compute.isPending || regenerate.isPending
  const ready = readiness.data
  const queue = prep.data ?? []
  const maxPriority = queue.reduce((m, i) => Math.max(m, i.priority), 0)

  return (
    <div className="space-y-8">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Preparation map</h1>
        <p className="mt-1 text-sm text-ink-500">Your competency model against the target role, and the practice queue it generates.</p>
      </header>

      {compute.isError ? <ErrorState title="Readiness computation failed" body={compute.error instanceof Error ? compute.error.message : undefined} onRetry={() => void compute.mutateAsync(roleId)} /> : null}

      {/* Readiness summary */}
      <Surface tone="accent" className="p-6">
        <div className="flex flex-wrap items-end justify-between gap-6">
          <div className="min-w-0">
            <SectionHeading>Overall readiness</SectionHeading>
            <div className="flex items-baseline gap-2">
              <span className="text-4xl font-semibold tracking-tight">{ready?.overall?.toFixed(1) ?? '—'}</span>
              <span className="text-sm text-ink-400">/ 10</span>
            </div>
            <div className="mt-3 flex flex-wrap gap-x-8 gap-y-2">
              <Stat label="Confidence" value={`${Math.round((ready?.confidence ?? 0) * 100)}%`} />
              <Stat label="Evidence coverage" value={`${Math.round((ready?.evidence_coverage ?? 0) * 100)}%`} />
              <Stat label="Critical gaps" value={ready?.critical_gaps.length ?? 0} />
            </div>
          </div>
          <div className="flex gap-2">
            <Button variant="secondary" onClick={() => void compute.mutateAsync(roleId)} disabled={busy || !roleId}>
              {compute.isPending ? 'Computing…' : 'Refresh readiness'}
            </Button>
            <Button variant="secondary" onClick={() => void regenerate.mutateAsync()} disabled={busy || !ready?.critical_gaps?.length}>
              {regenerate.isPending ? 'Regenerating…' : 'Regenerate queue'}
            </Button>
          </div>
        </div>
        {!roleId ? (
          <p className="mt-4 text-sm text-ink-500">
            No target role yet — <button className="font-medium text-accent-700 underline" onClick={() => navigate('/setup')}>analyze a JD in Profile & Role</button> first.
          </p>
        ) : null}
      </Surface>

      {readiness.isLoading ? <Skeleton className="h-48" /> : null}

      {/* Competency model */}
      <div className="grid gap-6 lg:grid-cols-2">
        <Surface className="p-5">
          <SectionHeading>Competencies vs target</SectionHeading>
          {!ready?.per_competency?.length ? (
            <EmptyState
              icon="🧭"
              title="No competency model yet"
              body="Analyze a job description to build the model. Readiness is then computed from evidence and practice — not guessed."
            />
          ) : (
            <ul className="space-y-4">
              {ready.per_competency.map((comp) => {
                const targetLevel = comp.importance === 'required' ? 'required' : 'supporting'
                return (
                  <li key={comp.name}>
                    <div className="mb-1 flex items-center justify-between gap-3">
                      <span className="text-sm font-medium text-ink-800">
                        {comp.name}{' '}
                        <Pill tone={comp.importance === 'required' ? 'warn' : 'neutral'}>{targetLevel}</Pill>
                      </span>
                      <span className="text-xs text-ink-400">
                        level {comp.demonstrated_level}/5 · {comp.score.toFixed(1)}/10
                      </span>
                    </div>
                    <Meter value={comp.score} />
                    <p className="mt-1 text-xs text-ink-400">evidence coverage {Math.round(comp.evidence_coverage * 100)}%</p>
                  </li>
                )
              })}
            </ul>
          )}
        </Surface>

        {/* Practice queue */}
        <Surface className="p-5">
          <SectionHeading aside={<Pill tone={queue.length ? 'accent' : 'neutral'}>{queue.length} open</Pill>}>Today's practice queue</SectionHeading>
          {!queue.length ? (
            <EmptyState
              icon="📋"
              title="Queue is empty"
              body="Refresh readiness with a target role, then regenerate the queue. It prioritizes the largest gaps with the weakest evidence."
            />
          ) : (
            <ol className="space-y-2.5">
              {queue.map((item) => (
                <li
                  key={item.id}
                  className="flex items-center gap-4 rounded-lg border border-ink-200 bg-white p-3.5"
                  style={{ opacity: 0.55 + 0.45 * (item.priority / Math.max(1, maxPriority)) }}
                >
                  <div className="w-12 shrink-0 text-center">
                    <p className="text-lg font-semibold tracking-tight text-ink-800">{item.priority}</p>
                    <p className="text-[10px] uppercase tracking-wide text-ink-400">priority</p>
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-semibold text-ink-800">{item.competency_name ?? 'Practice'}</p>
                    <p className="mt-0.5 text-xs leading-relaxed text-ink-500">{item.reason}</p>
                  </div>
                  <div className="shrink-0 text-right">
                    <Pill tone="accent">≈ {item.estimated_minutes ?? 15} min</Pill>
                    {item.expected_improvement ? (
                      <p className="mt-1 text-[11px] text-ink-400">+{Math.round(item.expected_improvement * 100)}% expected</p>
                    ) : null}
                  </div>
                </li>
              ))}
            </ol>
          )}
          <div className="mt-4">
            <Button onClick={() => navigate('/interview')} disabled={!queue.length && !ready?.critical_gaps?.length}>
              Start practice interview →
            </Button>
          </div>
        </Surface>
      </div>

      {busy ? <Spinner label={compute.isPending ? 'Computing readiness…' : 'Regenerating queue…'} /> : null}
    </div>
  )
}
