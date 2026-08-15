// Debrief — post-interview operational findings. Real interviews recorded
// elsewhere, each one either saved as a plain record or analyzed against
// the competency model. Analysis output is shown exactly as the backend
// returns it; unanalyzed records stay unanalyzed.

import { useState } from 'react'
import {
  DEFAULT_USER_ID,
  useAnalyzeDebrief,
  useCreateDebrief,
  useDebriefs,
  useProfiles,
  useResolvedProfile,
  type Debrief,
} from '../hooks/queries'
import { Button, ErrorState, Skeleton } from '../components/ui'
import { Sheet, SheetSection, StencilNum } from '../components/sheet'

interface DebriefAnalysisView {
  weaknesses: string[]
  strengths: string[]
  recommendations: string[]
  competency_hints: string[]
}

const inputCls =
  'h-9 w-full border border-ink/30 bg-sheet px-3 text-sm text-ink placeholder:text-ink-3 focus:border-draft focus:outline-none focus:shadow-[var(--focus-ring)]'
const taCls =
  'w-full resize-y border border-ink/30 bg-sheet px-3 py-2.5 text-sm leading-relaxed text-ink placeholder:text-ink-3 focus:border-draft focus:outline-none focus:shadow-[var(--focus-ring)]'

function pad2(n: number): string {
  return String(n).padStart(2, '0')
}

function fmtDate(iso: string | null | undefined): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })
}

// Numbered annotation block — weaknesses redline, strengths draft,
// recommendations neutral, competency hints draft-2.
function AnalysisBlock({ label, items, tone }: { label: string; items: string[]; tone: 'redline' | 'draft' | 'ink' | 'draft-2' }) {
  const toneCls = {
    redline: 'text-redline',
    draft: 'text-draft',
    ink: 'text-ink-2',
    'draft-2': 'text-draft-2',
  }[tone]
  if (items.length === 0) return null
  return (
    <div>
      <p className={`stencil text-[10px] uppercase tracking-[0.12em] ${toneCls}`}>{label}</p>
      <ol className="mt-1.5">
        {items.map((s, i) => (
          <li key={i} className="flex items-baseline gap-2.5 border-b border-ink/5 py-1.5">
            <StencilNum className="text-[10px] leading-none text-ink-3">{pad2(i + 1)}</StencilNum>
            <span className="text-[13px] leading-relaxed text-ink">{s}</span>
          </li>
        ))}
      </ol>
    </div>
  )
}

export function DebriefPage() {
  const debriefs = useDebriefs(DEFAULT_USER_ID)
  const createDebrief = useCreateDebrief()
  const analyzeDebrief = useAnalyzeDebrief()
  const { activeId } = useResolvedProfile(DEFAULT_USER_ID)
  const profiles = useProfiles(DEFAULT_USER_ID)

  const [company, setCompany] = useState('')
  const [role, setRole] = useState('')
  const [round, setRound] = useState('')
  const [questions, setQuestions] = useState('')
  const [feedback, setFeedback] = useState('')
  const [result, setResult] = useState('')
  const [error, setError] = useState<string | null>(null)

  function clearForm() {
    setCompany('')
    setRole('')
    setRound('')
    setQuestions('')
    setFeedback('')
    setResult('')
  }

  async function saveDebrief() {
    if (!company.trim()) return
    setError(null)
    const body = {
      user_id: DEFAULT_USER_ID,
      company: company.trim(),
      role: role.trim() || null,
      round: round.trim() || null,
      questions: questions
        .split('\n')
        .map((q) => q.trim())
        .filter(Boolean),
      feedback: feedback.trim() || null,
      result: result.trim() || null,
    }
    try {
      await createDebrief.mutateAsync(body)
      clearForm()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not save debrief')
    }
  }

  async function analyzeDebriefForCurrent() {
    if (!company.trim()) return
    setError(null)
    try {
      await analyzeDebrief.mutateAsync({
        user_id: DEFAULT_USER_ID,
        company: company.trim(),
        role: role.trim() || null,
        round: round.trim() || null,
        questions: questions
          .split('\n')
          .map((q) => q.trim())
          .filter(Boolean),
        feedback: feedback.trim() || null,
        result: result.trim() || null,
      })
      clearForm()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Analysis failed')
    }
  }

  const analysisOf = (d: Debrief): DebriefAnalysisView | null => {
    const a = d.analysis
    if (!a || typeof a !== 'object') return null
    const pick = (k: string) => (Array.isArray(a[k]) ? (a[k] as string[]) : [])
    return {
      weaknesses: pick('weaknesses'),
      strengths: pick('strengths'),
      recommendations: pick('recommendations'),
      competency_hints: pick('competency_hints'),
    }
  }

  const data = debriefs.data ?? []
  const analyzed = data.filter((d) => analysisOf(d) !== null).length
  const profileName = profiles.data?.find((p) => p.id === activeId)?.name ?? null

  return (
    <Sheet aria-label="Interview debrief findings">
      {/* Title block */}
      <div className="flex flex-wrap items-start justify-between gap-x-8 gap-y-4 border-b border-ink/25 px-6 pb-4 pt-5">
        <div className="min-w-0">
          <p className="text-[10px] font-medium uppercase tracking-[0.12em] text-ink-2/70">Pramya · Debrief · Findings</p>
          <h1 className="mt-1.5 text-xl font-semibold tracking-tight text-ink">Debriefs</h1>
          <p className="mt-1 max-w-xl text-[13px] leading-relaxed text-ink-2">
            Record real interviews you have had elsewhere, then get a structured analysis mapped to your competencies.
          </p>
        </div>
        <div className="w-full border border-ink/30 bg-sheet-lit/45 px-4 py-3 sm:w-[17rem]">
          <div className="flex items-baseline justify-between gap-3">
            <p className="text-[10px] font-medium uppercase tracking-[0.12em] text-ink-2/70">Findings state</p>
            <span className={`stencil text-[10px] uppercase tracking-[0.16em] ${data.length ? 'text-draft' : 'text-ink-3'}`}>
              {data.length ? 'On record' : 'Empty'}
            </span>
          </div>
          <dl className="mt-2">
            {[
              ['Profile', profileName ?? '—'],
              ['Debriefs', data.length ? `${data.length} on record` : '—'],
              ['Analyzed', data.length ? `${analyzed} with analysis` : '—'],
              ['Latest', data.length ? fmtDate(data[data.length - 1].created_at) : '—'],
            ].map(([label, value]) => (
              <div key={label} className="flex items-baseline justify-between gap-3 border-t border-ink/10 pt-1.5">
                <dt className="stencil text-[10px] uppercase tracking-[0.12em] text-ink-3">{label}</dt>
                <dd className={`stencil truncate text-[10px] uppercase tracking-[0.12em] ${value === '—' ? 'text-ink-3' : 'text-ink-2'}`}>{value}</dd>
              </div>
            ))}
          </dl>
        </div>
      </div>

      {error ? <ErrorState title="That didn't work" body={error} className="m-6" /> : null}

      {/* 01 · NEW DEBRIEF */}
      <SheetSection
        title="New debrief"
        tone="lit"
        aside={<span className="stencil text-[10px] uppercase tracking-[0.14em] text-ink-2">company required</span>}
      >
        <div className="mt-1 grid gap-x-6 gap-y-4 sm:grid-cols-2">
          <label className="block">
            <span className="stencil block pb-1.5 text-[10px] uppercase tracking-[0.12em] text-ink-3">Company *</span>
            <input className={inputCls} value={company} onChange={(e) => setCompany(e.target.value)} placeholder="Acme Corp" />
          </label>
          <label className="block">
            <span className="stencil block pb-1.5 text-[10px] uppercase tracking-[0.12em] text-ink-3">Role</span>
            <input className={inputCls} value={role} onChange={(e) => setRole(e.target.value)} placeholder="Senior Engineer" />
          </label>
          <label className="block">
            <span className="stencil block pb-1.5 text-[10px] uppercase tracking-[0.12em] text-ink-3">Round</span>
            <input className={inputCls} value={round} onChange={(e) => setRound(e.target.value)} placeholder="HR / Technical / On-site" />
          </label>
          <label className="block">
            <span className="stencil block pb-1.5 text-[10px] uppercase tracking-[0.12em] text-ink-3">Result</span>
            <input className={inputCls} value={result} onChange={(e) => setResult(e.target.value)} placeholder="Offer / Rejected / Awaiting" />
          </label>
        </div>
        <label className="mt-4 block">
          <span className="stencil block pb-1.5 text-[10px] uppercase tracking-[0.12em] text-ink-3">Questions asked · one per line</span>
          <textarea
            className={`${taCls} min-h-24`}
            value={questions}
            onChange={(e) => setQuestions(e.target.value)}
            placeholder={'System design: design a URL shortener\nBehavioral: tell me about a conflict'}
          />
        </label>
        <label className="mt-4 block">
          <span className="stencil block pb-1.5 text-[10px] uppercase tracking-[0.12em] text-ink-3">Feedback you received</span>
          <textarea
            className={`${taCls} min-h-20`}
            value={feedback}
            onChange={(e) => setFeedback(e.target.value)}
            placeholder="What did the interviewer say you did well or could improve?"
          />
        </label>
        <div className="mt-4 flex flex-wrap items-center gap-3">
          <Button variant="secondary" onClick={saveDebrief} disabled={createDebrief.isPending || !company.trim()}>
            Save debrief
          </Button>
          <Button onClick={analyzeDebriefForCurrent} disabled={analyzeDebrief.isPending || !company.trim()}>
            {analyzeDebrief.isPending ? 'Analyzing…' : 'Save + analyze'}
          </Button>
        </div>
      </SheetSection>

      {/* 02 · RECORDED DEBRIEFS */}
      {debriefs.isLoading ? (
        <div className="space-y-2 px-6 py-6">
          <Skeleton className="h-16" />
          <Skeleton className="h-16" />
        </div>
      ) : debriefs.isError ? (
        <div className="px-6 py-6">
          <ErrorState
            title="Could not load debriefs"
            body={debriefs.error instanceof Error ? debriefs.error.message : undefined}
            onRetry={() => debriefs.refetch()}
          />
        </div>
      ) : data.length === 0 ? (
        <SheetSection title="Recorded debriefs" aside={<span className="stencil text-[10px] uppercase tracking-[0.14em] text-ink-3">no records</span>}>
          <div className="border border-dashed border-ink/25 px-6 py-10 text-center">
            <p className="stencil text-[12px] uppercase tracking-[0.2em] text-ink-3">No debriefs yet</p>
            <div className="mx-auto mt-6 w-full max-w-2xl space-y-2.5" aria-hidden>
              <span className="block h-2.5 w-1/3 border border-dashed border-ink/30" />
              <span className="block h-2.5 w-full border border-dashed border-ink/30" />
            </div>
            <p className="mx-auto mt-4 max-w-md text-[13px] leading-relaxed text-ink-2">
              After a real interview, record what happened here and analyze it.
            </p>
          </div>
        </SheetSection>
      ) : (
        <SheetSection
          title="Recorded debriefs"
          aside={<span className="stencil text-[10px] uppercase tracking-[0.14em] text-ink-2">{data.length} records · {analyzed} analyzed</span>}
        >
          <ol>
            {data.map((d, i) => {
              const analysis = analysisOf(d)
              return (
                <li key={d.id} className="border-b border-ink/5 py-4 last:border-b-0">
                  <div className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1">
                    <p className="flex min-w-0 flex-wrap items-baseline gap-x-3 gap-y-1">
                      <StencilNum className="text-[11px] leading-none text-ink-3">{pad2(i + 1)}</StencilNum>
                      <span className="text-[14px] font-semibold text-ink">{d.company}</span>
                      <span className="stencil text-[10px] uppercase tracking-[0.12em] text-ink-2">{d.role ?? '—'}</span>
                      {d.round ? <span className="stencil text-[10px] uppercase tracking-[0.12em] text-ink-3">{d.round}</span> : null}
                      {d.result ? (
                        <span className={`stencil text-[10px] uppercase tracking-[0.12em] ${d.result.toLowerCase().includes('offer') ? 'text-draft' : d.result.toLowerCase().includes('reject') ? 'text-redline' : 'text-ink-2'}`}>
                          {d.result}
                        </span>
                      ) : null}
                    </p>
                    <span className="stencil shrink-0 text-[10px] uppercase tracking-[0.12em] text-ink-3">{fmtDate(d.created_at)}</span>
                  </div>
                  {d.feedback ? <p className="mt-2 pl-7 text-[13px] leading-relaxed text-ink-2">{d.feedback}</p> : null}
                  {analysis ? (
                    <div className="mt-3 grid gap-x-10 gap-y-4 pl-7 lg:grid-cols-2">
                      <AnalysisBlock label="Strengths" items={analysis.strengths} tone="draft" />
                      <AnalysisBlock label="Weaknesses" items={analysis.weaknesses} tone="redline" />
                      <AnalysisBlock label="Recommendations" items={analysis.recommendations} tone="ink" />
                      <AnalysisBlock label="Competency hints" items={analysis.competency_hints} tone="draft-2" />
                    </div>
                  ) : (
                    <p className="stencil mt-2.5 pl-7 text-[10px] uppercase tracking-[0.1em] text-ink-3">
                      not analyzed — saved without analysis
                    </p>
                  )}
                </li>
              )
            })}
          </ol>
        </SheetSection>
      )}

      {/* Revision strip */}
      <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-2 border-t border-ink/25 px-6 pb-4 pt-3">
        <p className="stencil text-[10px] uppercase leading-relaxed tracking-[0.1em] text-ink-2">
          profile {profileName ?? '—'} · {data.length} debriefs · {analyzed} analyzed
          <br />
          drawn {new Date().toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })}
        </p>
        <p className="stencil text-[10px] uppercase leading-relaxed tracking-[0.1em] text-ink-3">
          analysis is stored with the record exactly as returned — records without analysis stay unanalyzed.
        </p>
      </div>
    </Sheet>
  )
}
