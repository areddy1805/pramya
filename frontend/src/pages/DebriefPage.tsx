import { useState } from 'react'
import {
  DEFAULT_USER_ID,
  useAnalyzeDebrief,
  useCreateDebrief,
  useDebriefs,
  type Debrief,
} from '../hooks/queries'
import {
  Button,
  EmptyState,
  ErrorState,
  Field,
  Pill,
  SectionHeading,
  Skeleton,
  Surface,
  TextArea,
  TextInput,
} from '../components/ui'

interface DebriefAnalysisView {
  weaknesses: string[]
  strengths: string[]
  recommendations: string[]
  competency_hints: string[]
}

export function DebriefPage() {
  const debriefs = useDebriefs(DEFAULT_USER_ID)
  const createDebrief = useCreateDebrief()
  const analyzeDebrief = useAnalyzeDebrief()

  const [company, setCompany] = useState('')
  const [role, setRole] = useState('')
  const [round, setRound] = useState('')
  const [questions, setQuestions] = useState('')
  const [feedback, setFeedback] = useState('')
  const [result, setResult] = useState('')
  const [error, setError] = useState<string | null>(null)

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
      setCompany('')
      setRole('')
      setRound('')
      setQuestions('')
      setFeedback('')
      setResult('')
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
      setCompany('')
      setRole('')
      setRound('')
      setQuestions('')
      setFeedback('')
      setResult('')
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

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Debriefs</h1>
        <p className="mt-1 text-sm text-fg-2">
          Record real interviews you have had elsewhere, then get a structured analysis mapped to
          your competencies.
        </p>
      </header>

      {error ? <ErrorState title="That didn't work" body={error} /> : null}

      <Surface className="p-6">
        <SectionHeading>New debrief</SectionHeading>
        <div className="mt-3 grid gap-4 sm:grid-cols-2">
          <Field label="Company *">
            <TextInput value={company} onChange={(e) => setCompany(e.target.value)} placeholder="Acme Corp" />
          </Field>
          <Field label="Role">
            <TextInput value={role} onChange={(e) => setRole(e.target.value)} placeholder="Senior Engineer" />
          </Field>
          <Field label="Round">
            <TextInput value={round} onChange={(e) => setRound(e.target.value)} placeholder="HR / Technical / On-site" />
          </Field>
          <Field label="Result">
            <TextInput value={result} onChange={(e) => setResult(e.target.value)} placeholder="Offer / Rejected / Awaiting" />
          </Field>
        </div>
        <Field label="Questions asked (one per line)">
          <div className="mt-1">
          <TextArea
            className="min-h-24"
            value={questions}
            onChange={(e) => setQuestions(e.target.value)}
            placeholder={'System design: design a URL shortener\nBehavioral: tell me about a conflict'}
          />
          </div>
        </Field>
        <Field label="Feedback you received">
          <div className="mt-1">
          <TextArea
            className="min-h-20"
            value={feedback}
            onChange={(e) => setFeedback(e.target.value)}
            placeholder="What did the interviewer say you did well or could improve?"
          />
          </div>
        </Field>
        <div className="mt-4 flex flex-wrap gap-2">
          <Button
            variant="secondary"
            onClick={saveDebrief}
            disabled={createDebrief.isPending || !company.trim()}
          >
            Save debrief
          </Button>
          <Button
            onClick={analyzeDebriefForCurrent}
            disabled={analyzeDebrief.isPending || !company.trim()}
          >
            {analyzeDebrief.isPending ? 'Analyzing…' : 'Save + analyze'}
          </Button>
        </div>
      </Surface>

      <SectionHeading>Recorded debriefs</SectionHeading>
      {debriefs.isLoading ? (
        <div className="space-y-3">
          <Skeleton className="h-20" />
          <Skeleton className="h-20" />
        </div>
      ) : null}
      {debriefs.isError ? (
        <ErrorState
          title="Could not load debriefs"
          body={debriefs.error instanceof Error ? debriefs.error.message : undefined}
          onRetry={() => debriefs.refetch()}
        />
      ) : null}
      {debriefs.data && debriefs.data.length === 0 ? (
        <EmptyState
         
          title="No debriefs yet"
          body="After a real interview, record what happened here and analyze it."
        />
      ) : null}
      {debriefs.data && debriefs.data.length > 0 ? (
        <div className="space-y-3">
          {debriefs.data.map((d) => {
            const analysis = analysisOf(d)
            return (
              <Surface key={d.id} className="p-5">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-medium text-fg">{d.company}</span>
                  {d.role ? <Pill tone="accent">{d.role}</Pill> : null}
                  {d.round ? <Pill tone="neutral">{d.round}</Pill> : null}
                  {d.result ? <Pill tone="warn">{d.result}</Pill> : null}
                </div>
                {d.feedback ? <p className="mt-2 text-sm text-fg-2">{d.feedback}</p> : null}
                {analysis ? (
                  <div className="mt-3 grid gap-3 text-sm sm:grid-cols-2">
                    {analysis.strengths.length > 0 ? (
                      <div>
                        <p className="font-medium text-fg">Strengths</p>
                        <ul className="mt-1 list-disc pl-4 text-fg-2">
                          {analysis.strengths.map((s, i) => (
                            <li key={i}>{s}</li>
                          ))}
                        </ul>
                      </div>
                    ) : null}
                    {analysis.weaknesses.length > 0 ? (
                      <div>
                        <p className="font-medium text-fg">Weaknesses</p>
                        <ul className="mt-1 list-disc pl-4 text-fg-2">
                          {analysis.weaknesses.map((s, i) => (
                            <li key={i}>{s}</li>
                          ))}
                        </ul>
                      </div>
                    ) : null}
                    {analysis.recommendations.length > 0 ? (
                      <div>
                        <p className="font-medium text-fg">Recommendations</p>
                        <ul className="mt-1 list-disc pl-4 text-fg-2">
                          {analysis.recommendations.map((s, i) => (
                            <li key={i}>{s}</li>
                          ))}
                        </ul>
                      </div>
                    ) : null}
                    {analysis.competency_hints.length > 0 ? (
                      <div>
                        <p className="font-medium text-fg">Competency hints</p>
                        <ul className="mt-1 list-disc pl-4 text-fg-2">
                          {analysis.competency_hints.map((s, i) => (
                            <li key={i}>{s}</li>
                          ))}
                        </ul>
                      </div>
                    ) : null}
                  </div>
                ) : null}
              </Surface>
            )
          })}
        </div>
      ) : null}
    </div>
  )
}
