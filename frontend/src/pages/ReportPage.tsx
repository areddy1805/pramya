import { useParams, Link } from 'react-router-dom'
import { useReport, DEFAULT_USER_ID } from '../hooks/queries'
import { Button, EmptyState, ErrorState, Micro, Meter, Skeleton, Surface, Tag } from '../components/ui'

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

// Order matters — the report reads top-down as a coaching review.
const DIMENSION_ORDER = [
  'correctness',
  'technical_depth',
  'reasoning',
  'evidence',
  'specificity',
  'structure',
  'clarity',
  'relevance',
  'communication',
  'tradeoff_awareness',
  'seniority_alignment',
  'confidence',
  'completeness',
]

function scoreTone(score: number): { text: string; meter: 'accent' | 'ok' | 'danger' } {
  if (score >= 7.5) return { text: 'text-ok', meter: 'ok' }
  if (score >= 5) return { text: 'text-warn', meter: 'accent' }
  return { text: 'text-danger', meter: 'danger' }
}

function verdictFor(score: number): string {
  if (score >= 8) return 'Strong performance — answers were specific, evidenced, and well structured.'
  if (score >= 6.5) return 'Solid performance — clear strengths with a few areas to tighten.'
  if (score >= 5) return 'Foundation in place — several gaps worth deliberate preparation.'
  if (score >= 3) return 'Early stage — answers lacked depth or evidence; preparation should start with fundamentals.'
  return 'Needs groundwork — revisit core material and practice explaining concrete examples.'
}

export function ReportPage() {
  const { id } = useParams<{ id: string }>()
  const interviewId = Number(id)
  const report = useReport(interviewId, DEFAULT_USER_ID, !Number.isNaN(interviewId))

  const scorecard = report.data?.scorecard ?? null
  const questions = report.data?.questions ?? null
  const gaps = report.data?.gaps ?? null
  const topics = report.data?.topics ?? null

  const overall = typeof scorecard?.overall === 'number' ? scorecard.overall : null
  const overallTone = overall != null ? scoreTone(overall) : null

  return (
    <div className="mx-auto max-w-3xl space-y-8">
      <header className="flex flex-wrap items-end justify-between gap-3 border-b border-line pb-5">
        <div>
          <Micro>Interview report</Micro>
          <h1 className="mt-1 text-xl font-semibold tracking-tight">What to improve</h1>
        </div>
        <Link to="/interview">
          <Button variant="secondary" size="sm">← Practice</Button>
        </Link>
      </header>

      {report.isLoading ? (
        <div className="space-y-3">
          <Skeleton className="h-10 w-2/3" />
          <Skeleton className="h-48" />
        </div>
      ) : null}

      {report.isError ? (
        <ErrorState
          title="Could not generate the report"
          body={report.error instanceof Error ? report.error.message : undefined}
          onRetry={() => report.refetch()}
        />
      ) : null}

      {report.data ? (
        <>
          {/* Overall assessment */}
          {scorecard ? (
            <section>
              <div className="flex items-baseline gap-4">
                {overall != null && overallTone ? (
                  <>
                    <span className={`tabular text-5xl font-semibold tracking-tight ${overallTone.text}`}>
                      {overall.toFixed(1)}
                    </span>
                    <span className="text-sm text-fg-3">/ 10 overall</span>
                  </>
                ) : null}
              </div>
              {overall != null ? (
                <p className="mt-3 max-w-xl text-sm leading-relaxed text-fg-2">{verdictFor(overall)}</p>
              ) : null}

              {(Array.isArray(scorecard.top_strengths) && scorecard.top_strengths.length > 0) ||
              (Array.isArray(scorecard.top_weaknesses) && scorecard.top_weaknesses.length > 0) ? (
                <div className="mt-6 grid gap-6 sm:grid-cols-2">
                  {Array.isArray(scorecard.top_strengths) && scorecard.top_strengths.length > 0 ? (
                    <div>
                      <Micro className="mb-2 text-ok">Strongest</Micro>
                      <ul className="space-y-1.5">
                        {scorecard.top_strengths.map((s, i) => (
                          <li key={i} className="flex gap-2 text-sm leading-relaxed text-fg-2">
                            <span aria-hidden className="mt-0.5 text-ok">+</span>
                            {String(s)}
                          </li>
                        ))}
                      </ul>
                    </div>
                  ) : null}
                  {Array.isArray(scorecard.top_weaknesses) && scorecard.top_weaknesses.length > 0 ? (
                    <div>
                      <Micro className="mb-2 text-warn">Weakest</Micro>
                      <ul className="space-y-1.5">
                        {scorecard.top_weaknesses.map((s, i) => (
                          <li key={i} className="flex gap-2 text-sm leading-relaxed text-fg-2">
                            <span aria-hidden className="mt-0.5 text-warn">–</span>
                            {String(s)}
                          </li>
                        ))}
                      </ul>
                    </div>
                  ) : null}
                </div>
              ) : null}

              {/* Dense dimension scorecard — a table, not a widget grid */}
              <Surface className="mt-7 p-5" tone="inset">
                <Micro className="mb-4">Dimensions</Micro>
                <div className="grid gap-x-8 gap-y-2.5 sm:grid-cols-2">
                  {DIMENSION_ORDER.map((k) => {
                    const v = scorecard[k]
                    if (typeof v !== 'number') return null
                    const tone = scoreTone(v)
                    return (
                      <div key={k} className="flex items-center gap-3">
                        <span className="w-32 shrink-0 truncate text-[13px] text-fg-2">{DIMENSION_LABELS[k] ?? k}</span>
                        <div className="min-w-0 flex-1"><Meter value={v} tone={tone.meter} /></div>
                        <span className={`tabular w-8 text-right text-[13px] font-semibold ${tone.text}`}>{v.toFixed(1)}</span>
                      </div>
                    )
                  })}
                </div>
              </Surface>

              {gaps && gaps.length > 0 ? (
                <div className="mt-5">
                  <Micro className="mb-2 text-danger">Priority gaps — prepare these next</Micro>
                  <div className="flex flex-wrap gap-1.5">
                    {gaps.map((g, i) => (
                      <Tag key={i}>{String(g)}</Tag>
                    ))}
                  </div>
                </div>
              ) : null}
              {topics && topics.length > 0 ? (
                <p className="mt-4 text-xs text-fg-3">Covered: {topics.join(' · ')}</p>
              ) : null}
            </section>
          ) : null}

          {/* Question-by-question — the coaching record */}
          {questions && questions.length > 0 ? (
            <section>
              <Micro className="mb-3">Question by question</Micro>
              <div className="divide-y divide-line border-y border-line">
                {questions.map((row, qi) => {
                  const tone = scoreTone(row.overall)
                  return (
                    <article key={row.question_id ?? String(row.question)} className="py-5">
                      <div className="flex items-start justify-between gap-4">
                        <p className="text-[13px] font-semibold text-fg">
                          <span className="mr-2 text-fg-3">Q{qi + 1}</span>
                          {row.question}
                        </p>
                        <span className={`tabular shrink-0 text-[13px] font-semibold ${tone.text}`}>
                          {row.overall.toFixed(1)}
                        </span>
                      </div>
                      <div className="mt-3 space-y-2.5 pl-7 text-sm">
                        {row.answer ? (
                          <div>
                            <p className="text-[11px] font-semibold uppercase tracking-[0.09em] text-fg-3">What you said</p>
                            <p className="mt-0.5 leading-relaxed text-fg-2">{row.answer}</p>
                          </div>
                        ) : null}
                        {row.good.length > 0 ? (
                          <div>
                            <p className="text-[11px] font-semibold uppercase tracking-[0.09em] text-ok">What worked</p>
                            <ul className="mt-0.5 space-y-0.5">
                              {row.good.map((g, i) => (
                                <li key={i} className="leading-relaxed text-fg-2">+ {g}</li>
                              ))}
                            </ul>
                          </div>
                        ) : null}
                        {row.missing.length > 0 ? (
                          <div>
                            <p className="text-[11px] font-semibold uppercase tracking-[0.09em] text-warn">What was missing</p>
                            <ul className="mt-0.5 space-y-0.5">
                              {row.missing.map((m, i) => (
                                <li key={i} className="leading-relaxed text-fg-2">– {m}</li>
                              ))}
                            </ul>
                          </div>
                        ) : null}
                        {row.expected_follow_ups.length > 0 ? (
                          <p className="text-xs text-fg-3">
                            A strong answer would have addressed: {row.expected_follow_ups.join(' · ')}
                          </p>
                        ) : null}
                        <p className="text-[13px] font-medium text-accent">Prepare: {row.prep_recommendation}</p>
                      </div>
                    </article>
                  )
                })}
              </div>
            </section>
          ) : null}

          {/* Narrative synthesis */}
          {report.data.report ? (
            <section>
              <Micro className="mb-3">Coach's notes</Micro>
              <div className="whitespace-pre-wrap text-[15px] leading-[1.75] text-fg">{report.data.report}</div>
            </section>
          ) : null}
        </>
      ) : null}

      {!report.isLoading && !report.isError && !report.data ? (
        <EmptyState
          title="No report yet"
          body="Complete an interview with at least one evaluated answer, then come back here."
        />
      ) : null}
    </div>
  )
}
