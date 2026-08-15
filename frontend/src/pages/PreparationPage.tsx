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
import { Button, EmptyState, ErrorState, Meter, Micro, SectionHeading, Skeleton, Spinner, Stat, Surface, Tag } from '../components/ui'

export function PreparationPage() {
  const navigate = useNavigate()
  const { activeId } = useResolvedProfile(DEFAULT_USER_ID)
  const readiness = useReadiness(DEFAULT_USER_ID, activeId)
  const compute = useComputeReadiness(DEFAULT_USER_ID, activeId)
  const prep = usePreparation(DEFAULT_USER_ID, activeId)
  const regenerate = useRegeneratePreparation(DEFAULT_USER_ID, activeId)
  const roles = useRoles(DEFAULT_USER_ID, activeId)

  const roleId = roles.data?.at(-1)?.id
  const busy = compute.isPending || regenerate.isPending
  const ready = readiness.data
  const queue = prep.data ?? []

  return (
    <div className="space-y-8">
      <header>
        <Micro>Preparation</Micro>
        <h1 className="mt-1 text-xl font-semibold tracking-tight">Preparation map</h1>
        <p className="mt-1 max-w-xl text-sm leading-relaxed text-fg-2">Your competency model against the target role, and the practice queue it generates.</p>
      </header>

      {compute.isError ? <ErrorState title="Readiness computation failed" body={compute.error instanceof Error ? compute.error.message : undefined} onRetry={() => void compute.mutateAsync(roleId)} /> : null}

      {/* Readiness summary */}
      <Surface className="p-6">
        <div className="flex flex-wrap items-end justify-between gap-6">
          <div className="min-w-0">
            <SectionHeading>Overall readiness</SectionHeading>
            <div className="flex items-baseline gap-2">
              <span className={`tabular text-4xl font-semibold tracking-tight ${ready?.overall != null && ready.overall >= 7.5 ? 'text-ok' : ready?.overall != null && ready.overall >= 5 ? 'text-fg' : 'text-warn'}`}>{ready?.overall?.toFixed(1) ?? '—'}</span>
              <span className="text-sm text-fg-3">/ 10</span>
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
          <p className="mt-4 text-sm text-fg-2">
            No target role yet — <button className="font-medium text-accent underline" onClick={() => navigate('/setup')}>analyze a JD in Profile & Role</button> first.
          </p>
        ) : null}
      </Surface>

      {readiness.isLoading ? <Skeleton className="h-48" /> : null}

      {/* Competency model */}
      <div className="grid grid-cols-[minmax(0,1fr)] gap-6 lg:grid-cols-2">
        <Surface className="p-5">
          <SectionHeading>Competencies vs target</SectionHeading>
          {!ready?.per_competency?.length ? (
              <EmptyState
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
                      <span className="text-sm font-medium text-fg">
                        {comp.name}{' '}
                        <Tag>{targetLevel}</Tag>
                      </span>
                      <span className="text-xs text-fg-3">
                        level {comp.demonstrated_level}/5 · {comp.score.toFixed(1)}/10
                      </span>
                    </div>
                    <Meter value={comp.score} />
                    <p className="mt-1 text-xs text-fg-3">evidence coverage {Math.round(comp.evidence_coverage * 100)}%</p>
                  </li>
                )
              })}
            </ul>
          )}
        </Surface>

        {/* Practice queue */}
        <Surface className="p-5">
          <SectionHeading aside={<Tag>{queue.length} open</Tag>}>Today's practice queue</SectionHeading>
          {!queue.length ? (
            <EmptyState
              title="Queue is empty"
              body="Refresh readiness with a target role, then regenerate the queue. It prioritizes the largest gaps with the weakest evidence."
            />
          ) : (
            <ol className="space-y-2">
              {queue.map((item) => (
                <li
                  key={item.id}
                  className="flex items-center gap-4 rounded-[var(--r-md)] border border-line bg-surface px-3.5 py-3"
                >
                  <span className="tabular w-8 shrink-0 text-center text-lg font-semibold tracking-tight text-fg">{item.priority}</span>
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-semibold text-fg">{item.competency_name ?? 'Practice'}</p>
                    <p className="mt-0.5 text-xs leading-relaxed text-fg-2">{item.reason}</p>
                  </div>
                  <span className="shrink-0 text-xs text-fg-3">≈ {item.estimated_minutes ?? 15} min</span>
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
