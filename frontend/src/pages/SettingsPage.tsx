import { useState } from 'react'
import { api, ApiError, qs } from '../lib/api'
import { useHealth, DEFAULT_USER_ID } from '../hooks/queries'
import { useTheme } from '../stores/theme'
import { Button, ErrorState, KeyValue, Pill, SectionHeading, Spinner, Surface, TextArea } from '../components/ui'

type ThemeMode = 'dark' | 'light' | 'system'

const THEME_OPTIONS: { value: ThemeMode; label: string; hint: string }[] = [
  { value: 'dark', label: 'Dark', hint: "Pramya's signature theme" },
  { value: 'light', label: 'Light', hint: 'Bright, luminous surfaces' },
  { value: 'system', label: 'System', hint: 'Follow your OS preference' },
]

interface TranscriptResult {
  questions: string[]
  answers: string[]
  follow_ups: string[]
  weaknesses: string[]
  strengths: string[]
}

interface DemoSetupResult {
  profile: string
  roles: { key: string; chunks: number; evidence_count: number; competencies: number }[]
  readiness: number
  critical_gaps: number
  preparation_items: number
}

export function SettingsPage() {
  const health = useHealth()
  const theme = useTheme()
  const [transcriptText, setTranscriptText] = useState('')
  const [result, setResult] = useState<TranscriptResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [analyzing, setAnalyzing] = useState(false)
  const [demo, setDemo] = useState<DemoSetupResult | null>(null)
  const [demoBusy, setDemoBusy] = useState(false)

  async function loadDemoData() {
    setError(null)
    setDemoBusy(true)
    try {
      const res = await api.post<DemoSetupResult>(`/api/v1/demo/setup${qs({ user_id: DEFAULT_USER_ID })}`)
      setDemo(res)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Demo setup failed')
    } finally {
      setDemoBusy(false)
    }
  }

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
        <p className="mt-1 text-sm text-fg-2">Application status and analysis tools.</p>
      </header>

      {error ? <ErrorState title="That didn't work" body={error} /> : null}

      <Surface className="p-6">
        <SectionHeading>Appearance</SectionHeading>
        <p className="mb-4 text-sm text-fg-2">Choose how Pramya looks. Changes apply instantly and persist.</p>
        <div className="grid gap-3 sm:grid-cols-3" role="radiogroup" aria-label="Theme">
          {THEME_OPTIONS.map((option) => {
            const selected = theme.mode === option.value
            return (
              <button
                key={option.value}
                role="radio"
                aria-checked={selected}
                onClick={() => theme.setMode(option.value)}
                className={`rounded-xl border p-4 text-left transition-all duration-[var(--dur-fast)] ${
                  selected
                    ? 'border-accent-line bg-accent-soft shadow-[var(--shadow-1)]'
                    : 'border-line bg-surface hover:border-fg-3'
                }`}
              >
                <span className="flex items-center justify-between">
                  <span className={`text-sm font-semibold ${selected ? 'text-accent' : 'text-fg'}`}>
                    {option.label}
                  </span>
                  {selected ? <span aria-hidden className="h-2 w-2 rounded-full bg-accent" /> : null}
                </span>
                <span className="mt-1 block text-xs text-fg-3">{option.hint}</span>
              </button>
            )
          })}
        </div>
      </Surface>

      <div className="grid gap-6 lg:grid-cols-2">
        <Surface className="p-6">
          <SectionHeading>Application</SectionHeading>
          <dl className="mt-2">
            <KeyValue k="App" v={`${health.data?.app ?? 'pramya'} v${health.data?.version ?? ''}`} />
            <KeyValue k="Environment" v={health.data?.env ?? '—'} />
            <KeyValue k="Status" v={<Pill tone={health.data?.status === 'ok' ? 'ok' : 'danger'}>{health.data?.status ?? 'unknown'}</Pill>} />
          </dl>
          <p className="mt-4 text-xs leading-relaxed text-fg-3">
            Candidate data stays on your machine. Runtime and model health live under <span className="font-medium">Runtime</span>.
          </p>
        </Surface>

        <Surface className="p-6">
          <SectionHeading>Demo data</SectionHeading>
          <p className="mb-3 text-sm text-fg-2">
            Populate a fresh install with four bundled demo roles (resumes, evidence, readiness, preparation) —
            idempotent, safe to re-run.
          </p>
          <Button variant="secondary" onClick={loadDemoData} disabled={demoBusy}>
            {demoBusy ? 'Loading demo data…' : 'Load demo data'}
          </Button>
          {demo ? (
            <dl className="mt-4">
              <KeyValue k="Roles" v={`${demo.roles.length} (${demo.roles.map((r) => r.key).join(', ')})`} />
              <KeyValue k="Chunks indexed" v={demo.roles.reduce((n, r) => n + r.chunks, 0).toString()} />
              <KeyValue k="Evidence" v={demo.roles.reduce((n, r) => n + r.evidence_count, 0).toString()} />
              <KeyValue k="Readiness" v={`${demo.readiness}/10`} />
              <KeyValue k="Critical gaps" v={demo.critical_gaps.toString()} />
              <KeyValue k="Preparation items" v={demo.preparation_items.toString()} />
            </dl>
          ) : null}
        </Surface>

        <Surface className="p-6">
          <SectionHeading>Transcript analysis</SectionHeading>
          <p className="mb-3 text-sm text-fg-2">
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
              <p className="font-medium text-fg">
                {result.questions.length} questions · {result.answers.length} answers
                {result.follow_ups.length ? ` · ${result.follow_ups.length} follow-ups` : ''}
              </p>
              {result.weaknesses.length ? (
                <div className="rounded-lg border border-line bg-danger-soft p-3">
                  <p className="text-xs font-semibold uppercase tracking-wide text-danger">Weaknesses</p>
                  <ul className="mt-1 list-inside list-disc text-danger/90">
                    {result.weaknesses.map((w, i) => <li key={i}>{w}</li>)}
                  </ul>
                </div>
              ) : null}
              {result.strengths.length ? (
                <div className="rounded-lg border border-line bg-ok-soft p-3">
                  <p className="text-xs font-semibold uppercase tracking-wide text-ok">Strengths</p>
                  <ul className="mt-1 list-inside list-disc text-ok/90">
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
