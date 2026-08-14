import { Link } from 'react-router-dom'
import { DEFAULT_USER_ID, useInterviews, useResolvedProfile } from '../hooks/queries'
import { EmptyState, ErrorState, Pill, Skeleton, Surface } from '../components/ui'

const KIND_LABELS: Record<string, string> = {
  general: 'General mock',
  resume_deep_dive: 'Resume deep dive',
  job_description: 'JD interview',
  technical: 'Technical',
  behavioral: 'Behavioral',
  project_deep_dive: 'Project deep dive',
  system_design: 'System design',
  coding_reasoning: 'Coding (verbal)',
}

const STATUS_TONE: Record<string, 'ok' | 'warn' | 'danger' | 'neutral'> = {
  completed: 'ok',
  questioning: 'warn',
  paused: 'warn',
  created: 'neutral',
  cancelled: 'danger',
  error: 'danger',
}

function formatDate(iso?: string | null): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function HistoryPage() {
  const { activeId } = useResolvedProfile(DEFAULT_USER_ID)
  const interviews = useInterviews(DEFAULT_USER_ID, activeId)

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">History</h1>
        <p className="mt-1 text-sm text-fg-2">
          Every practice interview you have run — reports and transcripts stay available here.
        </p>
      </header>

      {interviews.isLoading ? (
        <div className="space-y-3">
          <Skeleton className="h-16" />
          <Skeleton className="h-16" />
          <Skeleton className="h-16" />
        </div>
      ) : null}

      {interviews.isError ? (
        <ErrorState
          title="Could not load history"
          body={interviews.error instanceof Error ? interviews.error.message : undefined}
          onRetry={() => interviews.refetch()}
        />
      ) : null}

      {interviews.data && interviews.data.length === 0 ? (
        <EmptyState
          icon="🗂"
          title="No interviews yet"
          body="Start a practice interview from the Practice screen and it will appear here."
        />
      ) : null}

      {interviews.data && interviews.data.length > 0 ? (
        <div className="space-y-3">
          {interviews.data.map((session) => (
            <Surface key={session.id} className="p-5">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-fg">
                      {KIND_LABELS[session.kind] ?? session.kind} · session #{session.id}
                    </span>
                    <Pill tone={STATUS_TONE[session.status] ?? 'neutral'}>{session.status}</Pill>
                  </div>
                  <p className="mt-1 text-xs text-fg-3">{formatDate(session.started_at)}</p>
                </div>
                <div className="flex gap-2">
                  <Link to={`/interview/${session.id}/report`}>
                    <span className="rounded-lg border border-line px-3 py-1.5 text-sm text-fg-2 hover:border-fg-3 hover:text-fg">
                      Report
                    </span>
                  </Link>
                  <Link to={`/interview/${session.id}/transcript`}>
                    <span className="rounded-lg border border-line px-3 py-1.5 text-sm text-fg-2 hover:border-fg-3 hover:text-fg">
                      Transcript
                    </span>
                  </Link>
                </div>
              </div>
            </Surface>
          ))}
        </div>
      ) : null}
    </div>
  )
}
