// Settings — workspace configuration record. Not a settings form: a
// controlled register of what this workspace is (app/runtime), how it
// appears, and the tools it runs. Theme persists instantly (no save
// model exists — one is not invented); analysis/demo tools keep their
// existing request/error semantics.

import { useState } from 'react'
import { api, ApiError, qs } from '../lib/api'
import { useHealth, useProfiles, useResolvedProfile, DEFAULT_USER_ID } from '../hooks/queries'
import { useTheme } from '../stores/theme'
import { Button, ErrorState, Skeleton, Spinner } from '../components/ui'
import { Sheet, SheetSection, StencilNum } from '../components/sheet'

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

function pad2(n: number): string {
  return String(n).padStart(2, '0')
}

// Spec row: SETTING · CURRENT VALUE (read-only configuration facts).
function SpecRow({ label, value, tone = 'text-ink' }: { label: string; value: React.ReactNode; tone?: string }) {
  return (
    <div className="grid grid-cols-[7.5rem_minmax(0,1fr)] items-baseline gap-x-4 border-t border-ink/10 py-2 first:border-t-0 first:pt-0 sm:grid-cols-[10rem_minmax(0,1fr)]">
      <dt className="stencil text-[10px] uppercase tracking-[0.12em] text-ink-3">{label}</dt>
      <dd className={`min-w-0 text-[13px] leading-relaxed ${tone}`}>{value}</dd>
    </div>
  )
}

export function SettingsPage() {
  const health = useHealth()
  const theme = useTheme()
  const { activeId } = useResolvedProfile(DEFAULT_USER_ID)
  const profiles = useProfiles(DEFAULT_USER_ID)
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

  const profileName = profiles.data?.find((p) => p.id === activeId)?.name ?? null
  const themeLabel = THEME_OPTIONS.find((o) => o.value === theme.mode)?.label ?? theme.mode

  return (
    <Sheet aria-label="Workspace configuration">
      {/* Title block */}
      <div className="flex flex-wrap items-start justify-between gap-x-8 gap-y-4 border-b border-ink/25 px-6 pb-4 pt-5">
        <div className="min-w-0">
          <p className="text-[10px] font-medium uppercase tracking-[0.12em] text-ink-2/70">Pramya · Settings · Configuration</p>
          <h1 className="mt-1.5 text-xl font-semibold tracking-tight text-ink">Settings</h1>
          <p className="mt-1 max-w-xl text-[13px] leading-relaxed text-ink-2">Application status and analysis tools.</p>
        </div>
        <div className="w-full border border-ink/30 bg-sheet-lit/45 px-4 py-3 sm:w-[17rem]">
          <div className="flex items-baseline justify-between gap-3">
            <p className="text-[10px] font-medium uppercase tracking-[0.12em] text-ink-2/70">Configuration state</p>
            <span className={`stencil text-[10px] uppercase tracking-[0.16em] ${health.data?.status === 'ok' ? 'text-draft' : 'text-redline'}`}>
              {health.data?.status === 'ok' ? 'Operational' : 'Unknown'}
            </span>
          </div>
          <dl className="mt-2">
            {[
              ['App', health.data ? `${health.data.app} v${health.data.version}` : '—'],
              ['Env', health.data?.env ?? '—'],
              ['Workspace', 'Global — all profiles'],
              ['Active profile', profileName ?? '—'],
              ['Theme', themeLabel],
              ['Persistence', 'Instant — applies immediately'],
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

      {/* 01 · APPEARANCE */}
      <SheetSection
        title="Appearance"
        tone="lit"
        aside={<span className="stencil text-[10px] uppercase tracking-[0.14em] text-ink-2">applies instantly · persists</span>}
      >
        <p className="py-1 text-[12px] leading-relaxed text-ink-2">Choose how Pramya looks. Changes apply instantly and persist.</p>
        <div className="grid gap-1.5 py-1 sm:grid-cols-3" role="radiogroup" aria-label="Theme">
          {THEME_OPTIONS.map((option) => {
            const selected = theme.mode === option.value
            return (
              <button
                key={option.value}
                type="button"
                role="radio"
                aria-checked={selected}
                onClick={() => theme.setMode(option.value)}
                className={`flex h-16 flex-col justify-center gap-1 border px-3 text-left transition-colors focus-visible:outline-none focus-visible:shadow-[var(--focus-ring)] ${
                  selected ? 'border-draft bg-draft-soft/50' : 'border-ink/30 hover:border-draft/60'
                }`}
              >
                <span className={`stencil flex items-center justify-between text-[10px] font-semibold uppercase tracking-[0.14em] ${selected ? 'text-draft-2' : 'text-ink-2'}`}>
                  {option.label}
                  {selected ? <span aria-hidden className="h-1.5 w-1.5 rotate-45 border border-draft bg-draft" /> : null}
                </span>
                <span className={`text-[11px] leading-relaxed ${selected ? 'text-ink-2' : 'text-ink-3'}`}>{option.hint}</span>
              </button>
            )
          })}
        </div>
      </SheetSection>

      {/* 02 · APPLICATION */}
      <SheetSection title="Application" aside={<span className="stencil text-[10px] uppercase tracking-[0.14em] text-ink-2">read-only</span>}>
        {health.isLoading ? (
          <div className="space-y-2 py-2">
            <Skeleton className="h-8" />
            <Skeleton className="h-8" />
            <Skeleton className="h-8" />
          </div>
        ) : health.isError ? (
          <div className="py-2">
            <p className="stencil text-[10px] uppercase tracking-[0.14em] text-redline">Status unavailable</p>
            <p className="mt-1 text-[12px] text-ink-2">The backend health endpoint could not be reached.</p>
          </div>
        ) : (
          <dl className="py-1">
            <SpecRow label="App" value={health.data ? `${health.data.app} v${health.data.version}` : '—'} />
            <SpecRow label="Environment" value={health.data?.env ?? '—'} />
            <SpecRow
              label="Status"
              value={<span className={`stencil text-[10px] uppercase tracking-[0.12em] ${health.data?.status === 'ok' ? 'text-draft' : 'text-redline'}`}>{health.data?.status ?? 'unknown'}</span>}
            />
          </dl>
        )}
        <p className="mt-3 border-t border-ink/10 pt-2.5 text-[12px] leading-relaxed text-ink-3">
          Candidate data stays on your machine. Runtime and model health live under <span className="font-medium text-ink-2">Runtime</span>.
        </p>
      </SheetSection>

      <div className="grid lg:grid-cols-12">
        {/* 03 · ANALYSIS */}
        <SheetSection
          title="Analysis · transcript"
          className="lg:col-span-7 lg:border-r"
          aside={<span className="stencil text-[10px] uppercase tracking-[0.14em] text-ink-2">workspace tool</span>}
        >
          <p className="py-1 text-[12px] leading-relaxed text-ink-2">
            Paste a real interview transcript (TXT/MD) to extract questions, answers, weaknesses, and strengths for your own review.
          </p>
          <textarea
            aria-label="Transcript text"
            className="mt-2 min-h-44 w-full resize-y border border-ink/30 bg-sheet px-3 py-2.5 text-sm leading-relaxed text-ink placeholder:text-ink-3 focus:border-draft focus:outline-none focus:shadow-[var(--focus-ring)]"
            placeholder="Paste transcript…"
            value={transcriptText}
            onChange={(e) => setTranscriptText(e.target.value)}
          />
          <div className="mt-3 flex items-center gap-2">
            <Button onClick={() => void analyzeTranscript()} disabled={transcriptText.trim().length < 20 || analyzing}>
              {analyzing ? 'Analyzing…' : 'Analyze transcript'}
            </Button>
            {analyzing ? <Spinner label="Analyzing transcript…" subtle /> : null}
          </div>
          {result ? (
            <div className="mt-4 border-t border-ink/10 pt-3">
              <p className="stencil text-[10px] uppercase tracking-[0.12em] text-ink-2">
                {result.questions.length} questions · {result.answers.length} answers
                {result.follow_ups.length ? ` · ${result.follow_ups.length} follow-ups` : ''}
              </p>
              {result.weaknesses.length ? (
                <div className="mt-3">
                  <p className="stencil text-[10px] uppercase tracking-[0.12em] text-redline">Weaknesses</p>
                  <ol className="mt-1">
                    {result.weaknesses.map((w, i) => (
                      <li key={i} className="flex items-baseline gap-2 border-b border-ink/5 py-1.5">
                        <StencilNum className="text-[10px] leading-none text-ink-3">{pad2(i + 1)}</StencilNum>
                        <span className="text-[12px] leading-relaxed text-ink">{w}</span>
                      </li>
                    ))}
                  </ol>
                </div>
              ) : null}
              {result.strengths.length ? (
                <div className="mt-3">
                  <p className="stencil text-[10px] uppercase tracking-[0.12em] text-draft">Strengths</p>
                  <ol className="mt-1">
                    {result.strengths.map((s, i) => (
                      <li key={i} className="flex items-baseline gap-2 border-b border-ink/5 py-1.5">
                        <StencilNum className="text-[10px] leading-none text-ink-3">{pad2(i + 1)}</StencilNum>
                        <span className="text-[12px] leading-relaxed text-ink">{s}</span>
                      </li>
                    ))}
                  </ol>
                </div>
              ) : null}
            </div>
          ) : null}
        </SheetSection>

        {/* 04 · WORKSPACE · DEMO DATA */}
        <SheetSection
          title="Workspace · demo data"
          tone="shadow"
          className="lg:col-span-5"
          aside={<span className="stencil text-[10px] uppercase tracking-[0.14em] text-ink-2">idempotent</span>}
        >
          <p className="py-1 text-[12px] leading-relaxed text-ink-2">
            Populate a fresh install with four bundled demo roles (resumes, evidence, readiness, preparation) — idempotent, safe to re-run.
          </p>
          <div className="mt-2 flex items-center gap-2">
            <Button variant="secondary" onClick={loadDemoData} disabled={demoBusy}>
              {demoBusy ? 'Loading demo data…' : 'Load demo data'}
            </Button>
            {demoBusy ? <Spinner label="Loading demo data…" subtle /> : null}
          </div>
          {demo ? (
            <dl className="mt-4 border-t border-ink/10 pt-2">
              <SpecRow label="Roles" value={`${demo.roles.length} (${demo.roles.map((r) => r.key).join(', ')})`} />
              <SpecRow label="Chunks indexed" value={demo.roles.reduce((n, r) => n + r.chunks, 0).toString()} />
              <SpecRow label="Evidence" value={demo.roles.reduce((n, r) => n + r.evidence_count, 0).toString()} />
              <SpecRow label="Readiness" value={`${demo.readiness}/10`} />
              <SpecRow label="Critical gaps" value={demo.critical_gaps.toString()} />
              <SpecRow label="Preparation items" value={demo.preparation_items.toString()} />
            </dl>
          ) : null}
        </SheetSection>
      </div>

      {/* Revision strip */}
      <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-2 border-t border-ink/25 px-6 pb-4 pt-3">
        <p className="stencil text-[10px] uppercase leading-relaxed tracking-[0.1em] text-ink-2">
          workspace {DEFAULT_USER_ID} · profile {profileName ?? '—'} · env {health.data?.env ?? '—'}
          <br />
          drawn {new Date().toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })}
        </p>
        <p className="stencil text-[10px] uppercase leading-relaxed tracking-[0.1em] text-ink-3">
          configuration is global — profile-specific settings live on Profile and the interview pre-flight.
        </p>
      </div>
    </Sheet>
  )
}
