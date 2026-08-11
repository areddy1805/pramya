import { useNavigate } from 'react-router-dom'
import { useCandidate, useDocuments, usePreparation, useProgress, useReadiness, DEFAULT_USER_ID } from '../hooks/queries'
import { Badge, Card, EmptyState, ProgressBar, SectionTitle, Spinner, StatCard } from '../components/ui'

export function DashboardPage() {
  const navigate = useNavigate()
  const candidate = useCandidate(DEFAULT_USER_ID)
  const readiness = useReadiness(DEFAULT_USER_ID)
  const preparation = usePreparation(DEFAULT_USER_ID)
  const progress = useProgress(DEFAULT_USER_ID)
  const documents = useDocuments(DEFAULT_USER_ID)

  if (candidate.isLoading || readiness.isLoading) return <Spinner label="Loading dashboard…" />
  const hasSetup = candidate.data && (documents.data?.some((d) => d.kind === 'resume') || readiness.data?.overall !== 0)

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold text-slate-900">Dashboard</h1>
        <p className="mt-1 text-sm text-slate-600">
          Where am I · what to improve · what to do next
        </p>
      </header>

      {!hasSetup ? (
        <EmptyState
          title="Get started with Pramya"
          hint="Add your candidate profile and upload a resume, then analyze a target role to unlock readiness and preparation."
        />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <StatCard label="Overall readiness" value={`${readiness.data?.overall ?? 0}/10`} sub={`${readiness.data?.confidence ?? 0} confidence`} />
          <StatCard label="Evidence coverage" value={`${Math.round((readiness.data?.evidence_coverage ?? 0) * 100)}%`} />
          <StatCard label="Open prep items" value={String(preparation.data?.length ?? 0)} />
          <StatCard label="Evaluations" value={String(progress.data?.total_evaluations ?? 0)} sub={`${progress.data?.sessions ?? 0} sessions`} />
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <SectionTitle>Critical gaps</SectionTitle>
          {!readiness.data?.critical_gaps.length ? (
            <p className="text-sm text-slate-500">No critical gaps — nice work. Keep practicing to raise confidence.</p>
          ) : (
            <ul className="space-y-3">
              {readiness.data.critical_gaps.slice(0, 5).map((gap) => (
                <li key={gap.competency_id} className="flex items-center justify-between gap-3">
                  <div>
                    <p className="text-sm font-medium text-slate-800">{gap.name}</p>
                    <p className="text-xs text-slate-500">
                      demonstrated {gap.demonstrated_level}/5 · required {gap.required_level}/5
                    </p>
                  </div>
                  <Badge tone="red">gap {gap.gap}</Badge>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card>
          <SectionTitle>What to do next</SectionTitle>
          {!preparation.data?.length ? (
            <p className="text-sm text-slate-500">
              Regenerate the preparation plan after your readiness snapshot to get today's queue.
            </p>
          ) : (
            <ul className="space-y-3">
              {preparation.data.slice(0, 5).map((item) => (
                <li key={item.id} className="flex items-center justify-between gap-3">
                  <div>
                    <p className="text-sm font-medium text-slate-800">{item.competency_name ?? 'Practice'}</p>
                    <p className="text-xs text-slate-500">{item.reason}</p>
                  </div>
                  <Badge tone="blue">{item.estimated_minutes ?? '—'} min</Badge>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      <Card>
        <SectionTitle>Recent progress</SectionTitle>
        {!progress.data?.total_evaluations ? (
          <p className="text-sm text-slate-500">Complete an interview to see your progress trends.</p>
        ) : (
          <div className="space-y-4">
            {progress.data.series.map((series) => (
              <div key={series.name}>
                <div className="mb-1 flex items-center justify-between text-sm">
                  <span className="font-medium text-slate-700">{series.name}</span>
                  <span className="text-slate-500">
                    latest {series.latest?.toFixed(1)} {series.trend != null ? (series.trend >= 0 ? `▲ +${series.trend}` : `▼ ${series.trend}`) : ''}
                  </span>
                </div>
                <ProgressBar value={series.latest ?? 0} label="" />
              </div>
            ))}
          </div>
        )}
      </Card>

      <div className="flex flex-wrap gap-3">
        <button
          className="rounded-lg bg-blue-700 px-4 py-2 text-sm font-medium text-white hover:bg-blue-800"
          onClick={() => navigate('/setup')}
        >
          Manage setup
        </button>
        <button
          className="rounded-lg bg-slate-100 px-4 py-2 text-sm font-medium text-slate-800 hover:bg-slate-200"
          onClick={() => navigate('/preparation')}
        >
          Preparation map
        </button>
        <button
          className="rounded-lg bg-slate-100 px-4 py-2 text-sm font-medium text-slate-800 hover:bg-slate-200"
          onClick={() => navigate('/interview')}
        >
          Start practice interview
        </button>
      </div>
    </div>
  )
}
