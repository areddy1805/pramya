import { useProgress, useInterviews, DEFAULT_USER_ID } from '../hooks/queries'
import { Badge, Card, EmptyState, ProgressBar, SectionTitle, Spinner } from '../components/ui'

export function ProgressPage() {
  const progress = useProgress(DEFAULT_USER_ID)
  const sessions = useInterviews(DEFAULT_USER_ID)

  if (progress.isLoading) return <Spinner label="Loading progress…" />

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold text-slate-900">Progress</h1>
        <p className="mt-1 text-sm text-slate-600">
          Trends come only from completed evaluations — never fabricated.
        </p>
      </header>

      {!progress.data?.total_evaluations ? (
        <EmptyState
          title="No progress yet"
          hint="Complete practice interviews with answers to build evaluation history."
        />
      ) : (
        <div className="grid gap-6 lg:grid-cols-2">
          <Card>
            <SectionTitle>Per-competency trend</SectionTitle>
            <ul className="space-y-4">
              {progress.data.series.map((s) => (
                <li key={s.name}>
                  <div className="mb-1 flex items-center justify-between text-sm">
                    <span className="font-medium text-slate-700">{s.name}</span>
                    <span className="text-slate-500">
                      {s.latest?.toFixed(1)}
                      {s.trend != null ? (
                        <Badge tone={s.trend >= 0 ? 'green' : 'red'}>
                          {s.trend >= 0 ? `▲ +${s.trend.toFixed(1)}` : `▼ ${s.trend.toFixed(1)}`}
                        </Badge>
                      ) : null}
                    </span>
                  </div>
                  <ProgressBar value={s.latest ?? 0} />
                  <p className="mt-0.5 text-xs text-slate-400">
                    {s.points.length} evaluation{s.points.length === 1 ? '' : 's'}
                  </p>
                </li>
              ))}
            </ul>
          </Card>

          <Card>
            <SectionTitle>History</SectionTitle>
            {!sessions.data?.length ? (
              <p className="text-sm text-slate-500">No sessions yet.</p>
            ) : (
              <ul className="divide-y divide-slate-100">
                {sessions.data.map((s) => (
                  <li key={s.id} className="flex items-center justify-between py-2 text-sm">
                    <span className="text-slate-700">{s.kind}</span>
                    <Badge tone={s.status === 'completed' ? 'green' : s.status === 'cancelled' ? 'red' : 'blue'}>
                      {s.status}
                    </Badge>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </div>
      )}
    </div>
  )
}
