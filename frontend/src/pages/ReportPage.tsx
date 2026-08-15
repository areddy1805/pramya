// Report — the interview assessment document. One registered record: the
// measured verdict, its dimension breakdown, the question-by-question
// coaching ledger, and the coach's narrative notes. No score is invented —
// every numeral comes from the backend report for this session.

import { Link, useParams } from 'react-router-dom'
import { useReport, DEFAULT_USER_ID } from '../hooks/queries'
import { ErrorState, Skeleton } from '../components/ui'
import { Sheet, SheetSection, StencilNum } from '../components/sheet'

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

// Report thresholds are the report's own (7.5 / 5) — untouched.
function scoreTone(score: number): { bar: string; num: string } {
  if (score >= 7.5) return { bar: 'text-draft', num: 'text-draft' }
  if (score >= 5) return { bar: 'text-ink', num: 'text-ink-2' }
  return { bar: 'text-redline', num: 'text-redline' }
}

function verdictFor(score: number): string {
  if (score >= 8) return 'Strong performance — answers were specific, evidenced, and well structured.'
  if (score >= 6.5) return 'Solid performance — clear strengths with a few areas to tighten.'
  if (score >= 5) return 'Foundation in place — several gaps worth deliberate preparation.'
  if (score >= 3) return 'Early stage — answers lacked depth or evidence; preparation should start with fundamentals.'
  return 'Needs groundwork — revisit core material and practice explaining concrete examples.'
}

function verdictStencil(score: number): string {
  if (score >= 8) return 'Strong'
  if (score >= 6.5) return 'Solid'
  if (score >= 5) return 'Foundation'
  if (score >= 3) return 'Early'
  return 'Groundwork'
}

function pad2(n: number): string {
  return String(n).padStart(2, '0')
}

// Dimension row — registered on one fixed 0–10 hatch scale.
function DimRow({ label, value }: { label: string; value: number }) {
  const tone = scoreTone(value)
  const pct = Math.max(0, Math.min(1, value / 10)) * 100
  return (
    <li className="grid grid-cols-[7.5rem_minmax(0,1fr)_2.25rem] items-center gap-x-4 border-b border-ink/10 py-2 sm:grid-cols-[10rem_minmax(0,1fr)_2.25rem]">
      <span className="truncate text-[12px] text-ink-2">{label}</span>
      <span aria-hidden className="relative h-2.5 overflow-hidden border border-ink/30 bg-transparent">
        <span className={`absolute inset-y-0 left-0 hatch ${tone.bar}`} style={{ width: `${pct}%` }} />
      </span>
      <span className={`stencil text-right text-[11px] leading-none ${tone.num}`}>{value.toFixed(1)}</span>
    </li>
  )
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
  const dims = DIMENSION_ORDER.filter((k) => typeof scorecard?.[k] === 'number')
  const strengths = Array.isArray(scorecard?.top_strengths) ? (scorecard.top_strengths as string[]) : []
  const weaknesses = Array.isArray(scorecard?.top_weaknesses) ? (scorecard.top_weaknesses as string[]) : []

  return (
    <Sheet aria-label="Interview assessment report">
      {/* Title block */}
      <div className="flex flex-wrap items-start justify-between gap-x-8 gap-y-4 border-b border-ink/25 px-6 pb-4 pt-5">
        <div className="min-w-0">
          <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-ink-2">Pramya · Interview · Report</p>
          <h1 className="mt-1.5 text-xl font-semibold tracking-tight text-ink">What to improve</h1>
          <p className="mt-1 max-w-xl text-[13px] leading-relaxed text-ink-2">
            The assessed record of this session — dimensions, per-question feedback, and the coach's notes.
          </p>
        </div>
        <div className="w-full border border-ink/30 bg-sheet-lit/45 px-4 py-3 sm:w-[17rem]">
          <div className="flex items-baseline justify-between gap-3">
            <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-ink-2">Assessment state</p>
            <span className={`stencil text-[10px] uppercase tracking-[0.16em] ${overall != null ? 'text-draft' : 'text-ink-3'}`}>
              {overall != null ? 'Assessed' : 'No score'}
            </span>
          </div>
          <dl className="mt-2">
            {[
              ['Interview', interviewId != null && !Number.isNaN(interviewId) ? `#${interviewId}` : '—'],
              ['Overall', overall != null ? `${overall.toFixed(1)} / 10` : '—'],
              ['Verdict', overall != null ? verdictStencil(overall) : '—'],
              ['Dimensions', dims.length ? `${dims.length} measured` : '—'],
              ['Questions', questions?.length != null ? `${questions.length} evaluated` : '—'],
            ].map(([label, value]) => (
              <div key={label} className="flex items-baseline justify-between gap-3 border-t border-ink/15 pt-1.5">
                <dt className="stencil text-[10px] uppercase tracking-[0.12em] text-ink-3">{label}</dt>
                <dd className={`stencil truncate text-[10px] uppercase tracking-[0.12em] ${value === '—' ? 'text-ink-3' : 'text-ink-2'}`}>{value}</dd>
              </div>
            ))}
          </dl>
        </div>
      </div>

      {report.isLoading ? (
        <div className="space-y-2 px-6 py-8">
          <Skeleton className="h-16 w-2/3" />
          <Skeleton className="h-48" />
          <Skeleton className="h-48" />
        </div>
      ) : null}

      {report.isError ? (
        <div className="px-6 py-6">
          <ErrorState
            title="Could not generate the report"
            body={report.error instanceof Error ? report.error.message : undefined}
            onRetry={() => report.refetch()}
          />
        </div>
      ) : null}

      {!report.isLoading && !report.isError && !report.data ? (
        <SheetSection title="Assessment record" aside={<span className="stencil text-[10px] uppercase tracking-[0.14em] text-ink-3">no report</span>}>
          <div className="border border-dashed border-ink/25 px-6 py-10 text-center">
            <p className="stencil text-[12px] uppercase tracking-[0.2em] text-ink-3">No report yet</p>
            <div className="mx-auto mt-6 w-full max-w-2xl space-y-2.5" aria-hidden>
              <span className="block h-2.5 w-2/3 border border-dashed border-ink/30" />
              <span className="block h-2.5 w-full border border-dashed border-ink/30" />
              <span className="block h-2.5 w-5/6 border border-dashed border-ink/30" />
            </div>
            <p className="mx-auto mt-4 max-w-md text-[13px] leading-relaxed text-ink-2">
              Complete an interview with at least one evaluated answer, then come back here.
            </p>
            <Link className="stencil mt-5 inline-block text-[10px] uppercase tracking-[0.1em] text-draft underline underline-offset-2 hover:text-draft-2" to="/interview">
              ← Practice
            </Link>
          </div>
        </SheetSection>
      ) : null}

      {report.data ? (
        <>
          {/* 01 · OVERALL ASSESSMENT */}
          {scorecard ? (
            <SheetSection
              title="Overall assessment"
              tone="lit"
              aside={<span className="stencil text-[10px] uppercase tracking-[0.14em] text-ink-2">deterministic · backend report</span>}
            >
              <div className="flex flex-wrap items-start justify-between gap-x-8 gap-y-4 pt-1">
                <div className="min-w-0 max-w-xl">
                  {overall != null ? (
                    <p className="text-[13px] leading-relaxed text-ink-2">{verdictFor(overall)}</p>
                  ) : (
                    <p className="text-[13px] leading-relaxed text-ink-3">No overall measurement was returned for this session.</p>
                  )}
                  {topics && topics.length > 0 ? (
                    <p className="stencil mt-3 text-[10px] uppercase leading-relaxed tracking-[0.1em] text-ink-3">
                      covered · {topics.join(' · ')}
                    </p>
                  ) : null}
                </div>
                <div className="flex items-baseline gap-2">
                  {overall != null && overallTone ? (
                    <>
                      <StencilNum className={`text-5xl leading-none ${overallTone.num}`}>{overall.toFixed(1)}</StencilNum>
                      <span className="stencil text-[10px] uppercase tracking-[0.12em] text-ink-2">/ 10 overall</span>
                    </>
                  ) : (
                    <StencilNum className="text-5xl leading-none text-ink-3">—</StencilNum>
                  )}
                </div>
              </div>

              {strengths.length > 0 || weaknesses.length > 0 ? (
                <div className="mt-5 grid gap-x-10 gap-y-5 lg:grid-cols-2">
                  {strengths.length > 0 ? (
                    <div>
                      <p className="stencil text-[10px] uppercase tracking-[0.12em] text-draft">Strongest</p>
                      <ol className="mt-1.5">
                        {strengths.map((s, i) => (
                          <li key={i} className="flex items-baseline gap-2.5 border-b border-ink/10 py-1.5">
                            <StencilNum className="text-[10px] leading-none text-ink-3">{pad2(i + 1)}</StencilNum>
                            <span className="text-[13px] leading-relaxed text-ink">{String(s)}</span>
                          </li>
                        ))}
                      </ol>
                    </div>
                  ) : null}
                  {weaknesses.length > 0 ? (
                    <div>
                      <p className="stencil text-[10px] uppercase tracking-[0.12em] text-redline">Weakest</p>
                      <ol className="mt-1.5">
                        {weaknesses.map((s, i) => (
                          <li key={i} className="flex items-baseline gap-2.5 border-b border-ink/10 py-1.5">
                            <StencilNum className="text-[10px] leading-none text-ink-3">{pad2(i + 1)}</StencilNum>
                            <span className="text-[13px] leading-relaxed text-ink">{String(s)}</span>
                          </li>
                        ))}
                      </ol>
                    </div>
                  ) : null}
                </div>
              ) : null}

              {dims.length > 0 ? (
                <div className="mt-5 border-t border-ink/15 pt-3">
                  <p className="stencil pb-2 text-[10px] uppercase tracking-[0.12em] text-ink-2">Dimensions · fixed 0–10 scale</p>
                  <ol>
                    {dims.map((k) => (
                      <DimRow key={k} label={DIMENSION_LABELS[k] ?? k} value={scorecard[k] as number} />
                    ))}
                  </ol>
                </div>
              ) : null}

              {gaps && gaps.length > 0 ? (
                <div className="mt-5 border-t border-ink/15 pt-3">
                  <p className="stencil text-[10px] uppercase tracking-[0.12em] text-redline">Priority gaps — prepare these next</p>
                  <ol className="mt-1.5">
                    {gaps.map((g, i) => (
                      <li key={i} className="flex items-baseline gap-2.5 border-b border-ink/10 py-1.5">
                        <StencilNum className="text-[10px] leading-none text-ink-3">{pad2(i + 1)}</StencilNum>
                        <span className="text-[13px] leading-relaxed text-ink">{String(g)}</span>
                      </li>
                    ))}
                  </ol>
                </div>
              ) : null}
            </SheetSection>
          ) : null}

          {/* 02 · QUESTION BY QUESTION */}
          {questions && questions.length > 0 ? (
            <SheetSection
              title="Question by question"
              aside={<span className="stencil text-[10px] uppercase tracking-[0.14em] text-ink-2">coaching record</span>}
            >
              <ol>
                {questions.map((row, qi) => {
                  const tone = scoreTone(row.overall)
                  return (
                    <li key={row.question_id ?? String(row.question)} className="border-b border-ink/10 py-4 last:border-b-0">
                      <div className="flex items-start justify-between gap-4">
                        <p className="min-w-0 text-[13px] font-semibold leading-relaxed text-ink">
                          <StencilNum className="mr-2 text-[11px] leading-none text-ink-3">Q{pad2(qi + 1)}</StencilNum>
                          {row.question}
                        </p>
                        <StencilNum className={`shrink-0 text-[13px] leading-none ${tone.num}`}>{row.overall.toFixed(1)}</StencilNum>
                      </div>
                      <div className="mt-3 space-y-3 pl-8">
                        {row.answer ? (
                          <div>
                            <p className="stencil text-[10px] uppercase tracking-[0.12em] text-ink-3">What you said</p>
                            <p className="mt-0.5 text-[13px] leading-relaxed text-ink-2">{row.answer}</p>
                          </div>
                        ) : null}
                        {row.good.length > 0 ? (
                          <div>
                            <p className="stencil text-[10px] uppercase tracking-[0.12em] text-draft">What worked</p>
                            <ul className="mt-0.5 space-y-0.5">
                              {row.good.map((g, i) => (
                                <li key={i} className="text-[13px] leading-relaxed text-ink-2">+ {g}</li>
                              ))}
                            </ul>
                          </div>
                        ) : null}
                        {row.missing.length > 0 ? (
                          <div>
                            <p className="stencil text-[10px] uppercase tracking-[0.12em] text-redline">What was missing</p>
                            <ul className="mt-0.5 space-y-0.5">
                              {row.missing.map((m, i) => (
                                <li key={i} className="text-[13px] leading-relaxed text-ink-2">– {m}</li>
                              ))}
                            </ul>
                          </div>
                        ) : null}
                        {row.expected_follow_ups.length > 0 ? (
                          <p className="stencil text-[10px] uppercase leading-relaxed tracking-[0.1em] text-ink-3">
                            strong answer would have addressed · {row.expected_follow_ups.join(' · ')}
                          </p>
                        ) : null}
                        <p className="stencil text-[10px] uppercase leading-relaxed tracking-[0.1em] text-draft-2">
                          prepare · {row.prep_recommendation}
                        </p>
                      </div>
                    </li>
                  )
                })}
              </ol>
            </SheetSection>
          ) : null}

          {/* 03 · COACH'S NOTES */}
          {report.data.report ? (
            <SheetSection title="Coach's notes" aside={<span className="stencil text-[10px] uppercase tracking-[0.14em] text-ink-2">narrative</span>}>
              <p className="whitespace-pre-wrap pt-1 text-[14px] leading-[1.75] text-ink">{report.data.report}</p>
            </SheetSection>
          ) : null}
        </>
      ) : null}

      {/* Revision strip */}
      <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-2 border-t border-ink/25 px-6 pb-4 pt-3">
        <p className="stencil text-[10px] uppercase leading-relaxed tracking-[0.1em] text-ink-2">
          interview {interviewId != null && !Number.isNaN(interviewId) ? `#${interviewId}` : '—'} ·{' '}
          {overall != null ? `${overall.toFixed(1)}/10 overall` : 'no overall score'} · {questions?.length ?? 0} questions evaluated
          <br />
          drawn {new Date().toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })}
        </p>
        <p className="stencil text-[10px] uppercase leading-relaxed tracking-[0.1em] text-ink-3">
          every numeral comes from the backend report — nothing is estimated here.
        </p>
      </div>
    </Sheet>
  )
}
