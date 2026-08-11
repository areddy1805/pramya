import { useProgress, useInterviews, DEFAULT_USER_ID } from '../hooks/queries'
import { EmptyState, Meter, Pill, SectionHeading, Skeleton, Stat, Surface } from '../components/ui'

export function ProgressPage() {
  const progress = useProgress(DEFAULT_USER_ID)
  const sessions = useInterviews(DEFAULT_USER_ID)

  if (progress.isLoading) return <Skeleton className="h-64" />

  const series = progress.data?.series ?? []

  return (
    <div className="space-y-8">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Progress</h1>
        <p className="mt-1 text-sm text-ink-500">Movement measured only from completed evaluations — nothing is estimated or padded.</p>
      </header>

      {!progress.data?.total_evaluations ? (
        <EmptyState
          icon="📈"
          title="No evaluation history yet"
          body="Every practice answer produces an evaluation. Complete a session and your competency trends appear here."
        />
      ) : (
        <>
          <div className="grid grid-cols-3 gap-4">
            <Surface className="p-4"><Stat label="Evaluations" value={progress.data.total_evaluations} /></Surface>
            <Surface className="p-4"><Stat label="Sessions" value={progress.data.sessions} /></Surface>
            <Surface className="p-4"><Stat label="Average" value={progress.data.average_overall.toFixed(1)} sub="/ 10" /></Surface>
          </div>

          <div className="grid gap-6 lg:grid-cols-2">
            <Surface className="p-6">
              <SectionHeading>Competency trends</SectionHeading>
              <ul className="space-y-5">
                {series.map((s) => (
                  <li key={s.name}>
                    <div className="mb-1 flex items-center justify-between gap-3">
                      <span className="text-sm font-medium text-ink-800">{s.name}</span>
                      <span className="flex items-center gap-2 text-xs text-ink-400">
                        {s.latest?.toFixed(1)}
                        {s.trend != null ? (
                          <Pill tone={s.trend >= 0 ? 'ok' : 'danger'}>{s.trend >= 0 ? `▲ +${s.trend.toFixed(1)}` : `▼ ${s.trend.toFixed(1)}`}</Pill>
                        ) : null}
                      </span>
                    </div>
                    <Meter value={s.latest ?? 0} />
                    <p className="mt-1 text-xs text-ink-400">{s.points.length} evaluation{s.points.length === 1 ? '' : 's'}</p>
                  </li>
                ))}
              </ul>
            </Surface>

            <Surface className="p-6">
              <SectionHeading>Interview history</SectionHeading>
              {!sessions.data?.length ? (
                <p className="text-sm text-ink-500">No sessions yet.</p>
              ) : (
                <ul className="divide-y divide-ink-100">
                  {sessions.data.map((s) => (
                    <li key={s.id} className="flex items-center justify-between py-3">
                      <div>
                        <p className="text-sm font-medium text-ink-800">{s.kind}</p>
                        <p className="text-xs text-ink-400">
                          {s.started_at ? new Date(s.started_at).toLocaleString() : ''}
                        </p>
                      </div>
                      <Pill tone={s.status === 'completed' ? 'ok' : s.status === 'cancelled' ? 'neutral' : 'accent'}>
                        {s.status}
                      </Pill>
                    </li>
                  ))}
                </ul>
              )}
            </Surface>
          </div>
        </>
      )}
    </div>
  )
}
