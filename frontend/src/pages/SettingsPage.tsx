import { useState } from 'react'
import { api, ApiError } from '../lib/api'
import { useHealth, DEFAULT_USER_ID } from '../hooks/queries'
import { Button, ErrorState, KeyValue, Pill, SectionHeading, Spinner, Surface, TextArea } from '../components/ui'

interface TranscriptResult {
  questions: string[]
  answers: string[]
  follow_ups: string[]
  weaknesses: string[]
  strengths: string[]
}

export function SettingsPage() {
  const health = useHealth()
  const [transcriptText, setTranscriptText] = useState('')
  const [result, setResult] = useState<TranscriptResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [analyzing, setAnalyzing] = useState(false)

  async function analyzeTranscript() {
    if (transcriptText.trim().length < 20) return
    setError(null)
    setAnalyzing(true)
    try {
      const res = await api.post<TranscriptResult>('/api/v1/transcripts/analyze', {
        user_id: DEFAULT_USER_ID,
        transcript_text: transcriptText,
      })
      setResult(res)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Analysis failed')
    } finally {
      setAnalyzing(false)
    }
  }

  return (
    <div className="space-y-8">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Settings</h1>
        <p className="mt-1 text-sm text-ink-500">Application status and analysis tools.</p>
      </header>

      {error ? <ErrorState title="That didn't work" body={error} /> : null}

      <div className="grid gap-6 lg:grid-cols-2">
        <Surface className="p-6">
          <SectionHeading>Application</SectionHeading>
          <dl className="mt-2">
            <KeyValue k="App" v={`${health.data?.app ?? 'pramya'} v${health.data?.version ?? ''}`} />
            <KeyValue k="Environment" v={health.data?.env ?? '—'} />
            <KeyValue k="Status" v={<Pill tone={health.data?.status === 'ok' ? 'ok' : 'danger'}>{health.data?.status ?? 'unknown'}</Pill>} />
          </dl>
          <p className="mt-4 text-xs leading-relaxed text-ink-400">
            Candidate data stays on your machine. Runtime and model health live under <span className="font-medium">Runtime</span>.
          </p>
        </Surface>

        <Surface className="p-6">
          <SectionHeading>Transcript analysis</SectionHeading>
          <p className="mb-3 text-sm text-ink-500">
            Paste a real interview transcript (TXT/MD) to extract questions, answers, weaknesses, and strengths for your own review.
          </p>
          <TextArea
            className="min-h-44"
            placeholder="Paste transcript…"
            value={transcriptText}
            onChange={(e) => setTranscriptText(e.target.value)}
          />
          <div className="mt-3">
            <Button onClick={() => void analyzeTranscript()} disabled={transcriptText.trim().length < 20 || analyzing}>
              {analyzing ? 'Analyzing…' : 'Analyze transcript'}
            </Button>
          </div>
          {analyzing ? <div className="mt-3"><Spinner label="Analyzing transcript…" /></div> : null}
          {result ? (
            <div className="mt-4 space-y-3 text-sm">
              <p className="font-medium text-ink-800">
                {result.questions.length} questions · {result.answers.length} answers
                {result.follow_ups.length ? ` · ${result.follow_ups.length} follow-ups` : ''}
              </p>
              {result.weaknesses.length ? (
                <div className="rounded-lg border border-danger-100 bg-danger-50 p-3">
                  <p className="text-xs font-semibold uppercase tracking-wide text-danger-700">Weaknesses</p>
                  <ul className="mt-1 list-inside list-disc text-danger-700/90">
                    {result.weaknesses.map((w, i) => <li key={i}>{w}</li>)}
                  </ul>
                </div>
              ) : null}
              {result.strengths.length ? (
                <div className="rounded-lg border border-ok-100 bg-ok-50 p-3">
                  <p className="text-xs font-semibold uppercase tracking-wide text-ok-700">Strengths</p>
                  <ul className="mt-1 list-inside list-disc text-ok-700/90">
                    {result.strengths.map((s, i) => <li key={i}>{s}</li>)}
                  </ul>
                </div>
              ) : null}
            </div>
          ) : null}
        </Surface>
      </div>
    </div>
  )
}
