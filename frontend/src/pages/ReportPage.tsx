import { useParams, Link } from 'react-router-dom'
import { useReport, DEFAULT_USER_ID } from '../hooks/queries'
import { Button, EmptyState, ErrorState, Skeleton, Surface } from '../components/ui'

export function ReportPage() {
  const { id } = useParams<{ id: string }>()
  const interviewId = Number(id)
  const report = useReport(interviewId, DEFAULT_USER_ID, !Number.isNaN(interviewId))

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Interview report</h1>
          <p className="mt-1 text-sm text-ink-500">Synthesis of what was demonstrated, where the gaps are, and what to practice next.</p>
        </div>
        <Link to="/interview">
          <Button variant="secondary">← Back</Button>
        </Link>
      </header>

      {report.isLoading ? (
        <div className="space-y-3">
          <Skeleton className="h-8 w-1/3" />
          <Skeleton className="h-64" />
        </div>
      ) : null}

      {report.isError ? (
        <ErrorState title="Could not generate the report" body={report.error instanceof Error ? report.error.message : undefined} onRetry={() => report.refetch()} />
      ) : null}

      {report.data ? (
        <Surface className="p-8">
          <div className="whitespace-pre-wrap text-[15px] leading-relaxed text-ink-800">{report.data.report}</div>
        </Surface>
      ) : null}

      {!report.isLoading && !report.isError && !report.data ? (
        <EmptyState icon="📄" title="No report yet" body="Complete an interview with at least one evaluated answer, then come back here." />
      ) : null}
    </div>
  )
}
