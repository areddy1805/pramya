import { useParams, Link } from 'react-router-dom'
import { useReport, DEFAULT_USER_ID } from '../hooks/queries'
import { Button, EmptyState, ErrorState, Skeleton, Surface } from '../components/ui'

const DIMENSION_LABELS: Record<string, string> = {
  overall: 'Overall',
  correctness: 'Correctness',
  technical_depth: 'Technical depth',
  clarity: 'Clarity',
  structure: 'Structure',
  relevance: 'Relevance',
  evidence: 'Evidence',
  communication: 'Communication',
  tradeoff_awareness: 'Tradeoff awareness',
  reasoning: 'Reasoning',
  confidence: 'Confidence',
  specificity: 'Specificity',
  seniority_alignment: 'Seniority alignment',
  completeness: 'Completeness',
}

function scoreTone(score: number): string {
  if (score >= 7.5) return 'bg-ok/15 text-ok'
  if (score >= 5) return 'bg-warn/15 text-warn'
  return 'bg-danger/15 text-danger'
}

export function ReportPage() {
  const { id } = useParams<{ id: string }>()
  const interviewId = Number(id)
  const report = useReport(interviewId, DEFAULT_USER_ID, !Number.isNaN(interviewId))

  const scorecard = report.data?.scorecard ?? null
  const questions = report.data?.questions ?? null
  const gaps = report.data?.gaps ?? null
  const topics = report.data?.topics ?? null

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Interview report</h1>
          <p className="mt-1 text-sm text-fg-2">Synthesis of what was demonstrated, where the gaps are, and what to practice next.</p>
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
        <>
          {/* Deterministic scorecard (report v2) */}
          {scorecard ? (
            <Surface className="p-6">
              <h2 className="text-sm font-semibold uppercase tracking-wide text-fg-3">Scorecard</h2>
              <div className="mt-4 grid grid-cols-2 gap-2.5 sm:grid-cols-3">
                {Object.entries(scorecard)
                  .filter(([k]) => !k.startsWith('top_'))
                  .map(([k, v]) => {
                    const score = typeof v === 'number' ? v : 0
                    const label = DIMENSION_LABELS[k] ?? k
                    return (
                      <div key={k} className="rounded-lg border border-line bg-surface-2 p-3">
                        <p className="text-[11px] font-medium uppercase tracking-wide text-fg-3">{label}</p>
                        <p className={`mt-1 text-xl font-semibold ${scoreTone(score)}`}>{score.toFixed(1)}</p>
                      </div>
                    )
                  })}
              </div>
              <div className="mt-4 grid gap-4 sm:grid-cols-2">
                {Array.isArray(scorecard.top_strengths) && scorecard.top_strengths.length > 0 ? (
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-wide text-ok">Top strengths</p>
                    <ul className="mt-2 space-y-1">
                      {scorecard.top_strengths.map((s, i) => (
                        <li key={i} className="text-sm text-fg-2">• {String(s)}</li>
                      ))}
                    </ul>
                  </div>
                ) : null}
                {Array.isArray(scorecard.top_weaknesses) && scorecard.top_weaknesses.length > 0 ? (
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-wide text-warn">Top weaknesses</p>
                    <ul className="mt-2 space-y-1">
                      {scorecard.top_weaknesses.map((s, i) => (
                        <li key={i} className="text-sm text-fg-2">• {String(s)}</li>
                      ))}
                    </ul>
                  </div>
                ) : null}
              </div>
              {gaps && gaps.length > 0 ? (
                <div className="mt-5 rounded-lg border border-danger/25 bg-danger/5 p-4">
                  <p className="text-xs font-semibold uppercase tracking-wide text-danger">Detected gaps — practice these next</p>
                  <ul className="mt-2 flex flex-wrap gap-2">
                    {gaps.map((g, i) => (
                      <li key={i} className="rounded-full border border-danger/25 bg-surface px-3 py-1 text-xs font-medium text-fg">{g}</li>
                    ))}
                  </ul>
                </div>
              ) : null}
              {topics && topics.length > 0 ? (
                <p className="mt-4 text-xs text-fg-3">Covered topics: {topics.join(' · ')}</p>
              ) : null}
            </Surface>
          ) : null}

          {/* Per-question feedback */}
          {questions && questions.length > 0 ? (
            <Surface className="p-6">
              <h2 className="text-sm font-semibold uppercase tracking-wide text-fg-3">Per-question feedback</h2>
              <div className="mt-4 space-y-5">
                {questions.map((row) => (
                  <div key={row.question_id ?? String(row.question)} className="rounded-xl border border-line bg-surface-2 p-4">
                    <div className="flex items-start justify-between gap-3">
                      <p className="text-sm font-medium leading-relaxed text-fg">{row.question}</p>
                      <span className={`shrink-0 rounded-full px-2.5 py-1 text-xs font-semibold ${scoreTone(row.overall)}`}>
                        {row.overall.toFixed(1)}
                      </span>
                    </div>
                    {row.answer ? (
                      <details className="mt-2">
                        <summary className="cursor-pointer text-xs font-medium text-fg-3 hover:text-fg-2">Your answer</summary>
                        <p className="mt-2 whitespace-pre-wrap text-sm leading-relaxed text-fg-2">{row.answer}</p>
                      </details>
                    ) : null}
                    <div className="mt-3 grid gap-3 sm:grid-cols-2">
                      {row.good.length > 0 ? (
                        <div>
                          <p className="text-[11px] font-semibold uppercase tracking-wide text-ok">Good</p>
                          <ul className="mt-1 space-y-0.5">
                            {row.good.map((g, i) => <li key={i} className="text-xs text-fg-2">✓ {g}</li>)}
                          </ul>
                        </div>
                      ) : null}
                      {row.missing.length > 0 ? (
                        <div>
                          <p className="text-[11px] font-semibold uppercase tracking-wide text-warn">Missing</p>
                          <ul className="mt-1 space-y-0.5">
                            {row.missing.map((m, i) => <li key={i} className="text-xs text-fg-2">✗ {m}</li>)}
                          </ul>
                        </div>
                      ) : null}
                    </div>
                    {row.expected_follow_ups.length > 0 ? (
                      <p className="mt-2 text-xs text-fg-3">Expected follow-ups: {row.expected_follow_ups.join(' · ')}</p>
                    ) : null}
                    <p className="mt-2 text-xs font-medium text-accent">Prep: {row.prep_recommendation}</p>
                  </div>
                ))}
              </div>
            </Surface>
          ) : null}

          {/* Narrative synthesis (kept) */}
          <Surface className="p-8">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-fg-3">Narrative synthesis</h2>
            <div className="mt-3 whitespace-pre-wrap text-[15px] leading-relaxed text-fg">{report.data.report}</div>
          </Surface>
        </>
      ) : null}

      {!report.isLoading && !report.isError && !report.data ? (
        <EmptyState icon="📄" title="No report yet" body="Complete an interview with at least one evaluated answer, then come back here." />
      ) : null}
    </div>
  )
}
