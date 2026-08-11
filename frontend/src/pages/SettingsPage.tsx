import { useState } from 'react'
import { api, ApiError } from '../lib/api'
import { useHealth, DEFAULT_USER_ID } from '../hooks/queries'
import { Badge, Button, Card, ErrorState, SectionTitle } from '../components/ui'

export function SettingsPage() {
  const health = useHealth()
  const [jdText, setJdText] = useState('')
  const [transcriptResult, setTranscriptResult] = useState<Record<string, string[]> | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [analyzing, setAnalyzing] = useState(false)

  async function analyzeTranscript() {
    if (jdText.trim().length < 20) return
    setError(null)
    setAnalyzing(true)
    try {
      const res = await api.post<Record<string, string[]>>('/api/v1/transcripts/analyze', {
        user_id: DEFAULT_USER_ID,
        transcript_text: jdText,
      })
      setTranscriptResult(res)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'analysis failed')
    } finally {
      setAnalyzing(false)
    }
  }

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold text-slate-900">Settings</h1>
        <p className="mt-1 text-sm text-slate-600">Runtime status · transcript analysis</p>
      </header>

      {error ? <ErrorState message={error} /> : null}

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <SectionTitle>Application</SectionTitle>
          <dl className="space-y-2 text-sm">
            <div className="flex justify-between">
              <dt className="text-slate-500">App</dt>
              <dd>{health.data?.app} v{health.data?.version}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-slate-500">Environment</dt>
              <dd>{health.data?.env}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-slate-500">Status</dt>
              <dd><Badge tone={health.data?.status === 'ok' ? 'green' : 'red'}>{health.data?.status ?? 'unknown'}</Badge></dd>
            </div>
          </dl>
          <p className="mt-4 text-xs text-slate-400">
            Candidate data stays local. See Model Status for AI runtime health.
          </p>
        </Card>

        <Card>
          <SectionTitle>Transcript analysis</SectionTitle>
          <p className="mb-2 text-sm text-slate-600">
            Paste a real interview transcript to extract questions, answers, weaknesses, and strengths.
          </p>
          <textarea
            className="min-h-40 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
            placeholder="Paste transcript (TXT/MD)…"
            value={jdText}
            onChange={(e) => setJdText(e.target.value)}
          />
          <div className="mt-3">
            <Button onClick={() => void analyzeTranscript()} disabled={jdText.trim().length < 20 || analyzing}>
              {analyzing ? 'Analyzing…' : 'Analyze transcript'}
            </Button>
          </div>
          {transcriptResult ? (
            <div className="mt-4 space-y-2 text-sm">
              <p className="font-medium text-slate-700">
                {transcriptResult.questions?.length ?? 0} questions · {transcriptResult.answers?.length ?? 0} answers
              </p>
              {transcriptResult.weaknesses?.length ? (
                <p className="text-red-800"><span className="font-semibold">Weaknesses:</span> {transcriptResult.weaknesses.join(' · ')}</p>
              ) : null}
              {transcriptResult.strengths?.length ? (
                <p className="text-green-800"><span className="font-semibold">Strengths:</span> {transcriptResult.strengths.join(' · ')}</p>
              ) : null}
            </div>
          ) : null}
        </Card>
      </div>
    </div>
  )
}
