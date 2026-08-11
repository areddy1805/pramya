import { useNavigate } from 'react-router-dom'
import {
  useComputeReadiness,
  usePreparation,
  useReadiness,
  useRegeneratePreparation,
  useRoles,
  DEFAULT_USER_ID,
} from '../hooks/queries'
import { Badge, Button, Card, EmptyState, ProgressBar, SectionTitle, Spinner } from '../components/ui'

export function PreparationPage() {
  const navigate = useNavigate()
  const readiness = useReadiness(DEFAULT_USER_ID)
  const compute = useComputeReadiness(DEFAULT_USER_ID)
  const prep = usePreparation(DEFAULT_USER_ID)
  const regenerate = useRegeneratePreparation(DEFAULT_USER_ID)
  const roles = useRoles(DEFAULT_USER_ID)

  const roleId = roles.data?.at(-1)?.id

  const busy = compute.isPending || regenerate.isPending

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold text-slate-900">Preparation Map</h1>
        <p className="mt-1 text-sm text-slate-600">Readiness · gaps · today's practice queue</p>
      </header>

      <Card>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="min-w-56 flex-1">
            <ProgressBar value={readiness.data?.overall ?? 0} label="Overall readiness" />
            <div className="mt-2 flex gap-4 text-xs text-slate-500">
              <span>Confidence {readiness.data?.confidence ?? 0}</span>
              <span>Evidence coverage {Math.round((readiness.data?.evidence_coverage ?? 0) * 100)}%</span>
            </div>
          </div>
          <Button onClick={() => void compute.mutateAsync(roleId)} disabled={busy}>
            {compute.isPending ? 'Computing…' : 'Refresh readiness'}
          </Button>
        </div>
      </Card>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <SectionTitle>Per-competency readiness</SectionTitle>
          {!readiness.data?.per_competency.length ? (
            <EmptyState
              title="No competencies yet"
              hint="Analyze a JD in Setup, then compute readiness."
            />
          ) : (
            <ul className="space-y-3">
              {readiness.data.per_competency.map((comp) => (
                <li key={comp.name}>
                  <div className="mb-1 flex items-center justify-between text-sm">
                    <span className="font-medium text-slate-700">
                      {comp.name}{' '}
                      <Badge tone={comp.importance === 'required' ? 'amber' : 'slate'}>{comp.importance}</Badge>
                    </span>
                    <span className="text-slate-500">
                      level {comp.demonstrated_level}/5 · {comp.score.toFixed(1)}
                    </span>
                  </div>
                  <ProgressBar value={comp.score} />
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card>
          <SectionTitle>Today's practice queue</SectionTitle>
          {!prep.data?.length ? (
            <EmptyState
              title="Queue is empty"
              hint="Compute readiness with a role selected, then regenerate the plan."
            />
          ) : (
            <ul className="space-y-3">
              {prep.data.map((item) => (
                <li key={item.id} className="flex items-center justify-between gap-3 rounded-lg border border-slate-100 p-3">
                  <div>
                    <p className="text-sm font-medium text-slate-800">{item.competency_name ?? 'Practice'}</p>
                    <p className="text-xs text-slate-500">{item.reason}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge tone="blue">{item.estimated_minutes ?? '—'} min</Badge>
                    <Badge tone={item.priority >= 70 ? 'red' : item.priority >= 40 ? 'amber' : 'slate'}>
                      p{item.priority}
                    </Badge>
                  </div>
                </li>
              ))}
            </ul>
          )}
          <div className="mt-3 flex gap-2">
            <Button variant="secondary" onClick={() => void regenerate.mutateAsync()} disabled={busy}>
              {regenerate.isPending ? 'Regenerating…' : 'Regenerate queue'}
            </Button>
            <Button variant="ghost" onClick={() => navigate('/interview')}>
              Start practice interview →
            </Button>
          </div>
        </Card>
      </div>

      {busy ? <Spinner label="Working…" /> : null}
    </div>
  )
}
