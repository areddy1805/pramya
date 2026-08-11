import { useParams, Link } from 'react-router-dom'
import { useReport, DEFAULT_USER_ID } from '../hooks/queries'
import { Button, Card, EmptyState, ErrorState, Spinner } from '../components/ui'

export function ReportPage() {
  const { id } = useParams<{ id: string }>()
  const interviewId = Number(id)
  const report = useReport(interviewId, DEFAULT_USER_ID, !Number.isNaN(interviewId))

  return (
    <div className="space-y-6">
      <header className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-slate-900">Interview Report</h1>
        <Link to="/interview">
          <Button variant="secondary">← Back to interviews</Button>
        </Link>
      </header>

      {report.isLoading ? <Spinner label="Generating report…" /> : null}
      {report.isError ? <ErrorState message={report.error instanceof Error ? report.error.message : 'report failed'} /> : null}

      {report.data ? (
        <Card>
          <div className="prose prose-slate max-w-none whitespace-pre-wrap text-sm leading-relaxed text-slate-800">
            {report.data.report}
          </div>
        </Card>
      ) : null}

      {!report.isLoading && !report.isError && !report.data ? (
        <EmptyState title="No report yet" hint="Complete an interview with at least one evaluated answer." />
      ) : null}
    </div>
  )
}
