import { Link, useParams } from 'react-router-dom'
import { DEFAULT_USER_ID, useTranscript } from '../hooks/queries'
import { Button, EmptyState, ErrorState, Pill, Skeleton, Surface } from '../components/ui'

function scoreTone(score: number): 'ok' | 'warn' | 'danger' {
  if (score >= 7) return 'ok'
  if (score >= 4) return 'warn'
  return 'danger'
}

export function TranscriptPage() {
  const { id } = useParams<{ id: string }>()
  const interviewId = Number(id)
  const transcript = useTranscript(interviewId, DEFAULT_USER_ID, !Number.isNaN(interviewId))

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Interview record</h1>
          <p className="mt-1 text-sm text-fg-2">
            The durable memory of the session — every question, answer, and evaluation in order.
          </p>
        </div>
        <Link to="/history">
          <Button variant="secondary">← History</Button>
        </Link>
      </header>

      {transcript.isLoading ? (
        <div className="space-y-3">
          <Skeleton className="h-24" />
          <Skeleton className="h-24" />
          <Skeleton className="h-24" />
        </div>
      ) : null}

      {transcript.isError ? (
        <ErrorState
          title="Could not load the transcript"
          body={transcript.error instanceof Error ? transcript.error.message : undefined}
          onRetry={() => transcript.refetch()}
        />
      ) : null}

      {transcript.data && transcript.data.turns.length === 0 ? (
        <EmptyState
          icon="🗒"
          title="Nothing recorded yet"
          body="This session has no turns. Run an interview to build its record."
        />
      ) : null}

      {transcript.data && transcript.data.turns.length > 0 ? (
        <div className="space-y-4">
          {transcript.data.turns.map((turn) => (
            <Surface key={turn.seq} className="p-5">
              <div className="flex items-center justify-between gap-2">
                <span className="text-xs font-medium uppercase tracking-wide text-fg-3">
                  Turn {turn.seq} · {turn.kind}
                  {turn.hints_used ? ` · ${turn.hints_used} hint${turn.hints_used > 1 ? 's' : ''} used` : ''}
                </span>
                {turn.evaluation_overall !== null && turn.evaluation_overall !== undefined ? (
                  <Pill tone={scoreTone(turn.evaluation_overall)}>
                    {turn.evaluation_overall.toFixed(1)}/10
                  </Pill>
                ) : null}
              </div>
              {turn.question ? (
                <p className="mt-2 text-[15px] font-medium text-fg">{turn.question}</p>
              ) : null}
              {turn.answer ? (
                <p className="mt-2 rounded-lg bg-surface-2 px-3 py-2 text-sm text-fg-2">
                  {turn.answer}
                </p>
              ) : null}
            </Surface>
          ))}
        </div>
      ) : null}
    </div>
  )
}
