import { useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  useCreateInterview,
  useDocuments,
  useInterview,
  useInterviewAction,
  useInterviewContext,
  useInterviews,
  useResolvedProfile,
  useRoles,
  useSetPreferredDocument,
  DEFAULT_USER_ID,
} from '../hooks/queries'
import { useSSE } from '../hooks/useSSE'
import type { InterviewContext } from '../lib/types'
import { VoiceClient, type VoiceState } from '../lib/voice'
import { Button, Divider, EmptyState, ErrorState, Field, Pill, SectionHeading, Select, Spinner, StatusDot, Surface } from '../components/ui'
const KINDS = [
  { value: 'general', label: 'General' },
  { value: 'resume_deep_dive', label: 'Resume deep dive' },
  { value: 'job_description', label: 'JD interview' },
  { value: 'technical', label: 'Technical' },
  { value: 'behavioral', label: 'Behavioral' },
  { value: 'project_deep_dive', label: 'Project deep dive' },
  { value: 'system_design', label: 'System design (text)' },
  { value: 'coding_reasoning', label: 'Coding reasoning (verbal)' },
]

function statusOf(doc: InterviewContext['resume']): { label: string; tone: 'ok' | 'warn' | 'danger' | 'neutral' } {
  if (!doc) return { label: 'Missing', tone: 'danger' }
  if (doc.ready) return { label: 'Ready', tone: 'ok' }
  return { label: doc.status, tone: 'warn' }
}

function provenanceLabel(source: string | null | undefined, sourceRef: string | null | undefined): string | null {
  if (!source) return null
  if (source === 'followup') return `Follow-up: previous answer · ${sourceRef ?? 'this topic'}`
  if (source === 'weakness') return `Based on: prior feedback · ${sourceRef ?? ''}`
  const label = source.charAt(0).toUpperCase() + source.slice(1)
  return `Based on: ${label} · ${sourceRef ?? ''}`
}

function InterviewContextPanel({
  ctx,
  loading,
  resumes = [],
  jds = [],
  onSelect,
}: {
  ctx: InterviewContext | null
  loading: boolean
  resumes?: Array<{ id: number; filename: string; status: string }>
  jds?: Array<{ id: number; filename: string; status: string }>
  onSelect?: (kind: 'resume' | 'jd', documentId: number | null) => void
}) {
  return (
    <div className="mb-5 rounded-xl border border-line bg-surface/60 p-4 text-sm">
      <div className="mb-3 flex items-center justify-between">
        <p className="text-xs font-semibold uppercase tracking-wider text-fg-3">Interview context</p>
        {loading ? (
          <span aria-hidden className="inline-block h-3.5 w-3.5 animate-spin rounded-full border-2 border-track border-t-accent" />
        ) : null}
      </div>
      {!ctx && !loading ? (
        <p className="text-xs leading-relaxed text-fg-3">
          Select a career profile to see what this interview will be grounded in.
        </p>
      ) : null}
      {ctx ? (
        <div className="space-y-3.5">
          <div>
            <p className="text-[11px] font-medium uppercase tracking-wide text-fg-3">Profile</p>
            <p className="font-medium text-fg">{ctx.profile?.name ?? '—'}</p>
            {ctx.profile?.positioning ? <p className="text-xs text-fg-3">{ctx.profile.positioning}</p> : null}
          </div>
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <p className="text-[11px] font-medium uppercase tracking-wide text-fg-3">Resume</p>
              <p className="truncate font-medium text-fg">{ctx.resume?.filename ?? 'No resume'}</p>
            </div>
            <Pill tone={statusOf(ctx.resume).tone}>{statusOf(ctx.resume).label}</Pill>
          </div>
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <p className="text-[11px] font-medium uppercase tracking-wide text-fg-3">Job description</p>
              <p className="truncate font-medium text-fg">{ctx.jd?.filename ?? 'None — resume-only interview'}</p>
            </div>
            {ctx.jd ? (
              <Pill tone={statusOf(ctx.jd).tone}>{statusOf(ctx.jd).label}</Pill>
            ) : (
              <Pill tone="neutral">optional</Pill>
            )}
          </div>
          <div>
            <p className="text-[11px] font-medium uppercase tracking-wide text-fg-3">Target roles</p>
            {ctx.target_roles.length ? (
              <div className="mt-1 flex flex-wrap gap-1.5">
                {ctx.target_roles.slice(0, 4).map((r) => (
                  <Pill key={r.id} tone="neutral">{r.title}</Pill>
                ))}
                {ctx.target_roles.length > 4 ? <Pill tone="neutral">+{ctx.target_roles.length - 4} more</Pill> : null}
              </div>
            ) : (
              <p className="text-xs text-fg-3">No analyzed roles yet</p>
            )}
          </div>
          <div>
            <p className="text-[11px] font-medium uppercase tracking-wide text-fg-3">Interview documents</p>
            <div className="mt-1.5 grid gap-2">
              <Select
                aria-label="Resume for this interview"
                value={String(ctx.resume?.document_id ?? '')}
                onChange={(e) => onSelect?.('resume', e.target.value ? Number(e.target.value) : null)}
                disabled={resumes.length === 0}
              >
                {resumes.length === 0 ? (
                  <option value="">No resumes on this profile</option>
                ) : null}
                {resumes.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.filename} ({d.status})
                  </option>
                ))}
              </Select>
              <Select
                aria-label="Job description for this interview"
                value={String(ctx.jd?.document_id ?? '')}
                onChange={(e) => onSelect?.('jd', e.target.value ? Number(e.target.value) : null)}
              >
                <option value="">No JD — resume-only interview</option>
                {jds.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.filename} ({d.status})
                  </option>
                ))}
              </Select>
            </div>
          </div>
          <div>
            <p className="text-[11px] font-medium uppercase tracking-wide text-fg-3">Grounded from</p>
            <div className="mt-1 flex flex-wrap gap-1.5">
              {(['profile', 'resume', 'jd', 'evidence'] as const).map((k) => (
                <Pill key={k} tone={ctx.grounding[k] ? 'ok' : 'neutral'}>
                  {k}
                </Pill>
              ))}
            </div>
          </div>
          {ctx.missing.includes('resume') ? (
            <div className="rounded-lg border border-line bg-warn-soft px-3 py-2 text-xs leading-relaxed text-warn">
              This profile has no processed resume. Upload one in Profile &amp; Role before starting an interview.
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  )
}

// Interviewer personas — mirror backend INTERVIEW_STYLES (coverage.py).
const STYLES = [
  { value: 'structured', label: 'Structured', hint: 'Methodical, one clear question at a time' },
  { value: 'curious', label: 'Curious', hint: 'Exploratory, eager to hear your reasoning' },
  { value: 'time_pressured', label: 'Time-pressured', hint: 'Rapid cadence — think on your feet' },
  { value: 'technical_expert', label: 'Technical expert', hint: 'Precise, implementation-level, jargon fine' },
  { value: 'conversational', label: 'Conversational', hint: 'Warm, natural, like a colleague' },
  { value: 'skeptical', label: 'Skeptical', hint: 'Stress-tests claims; asks for evidence and numbers' },
  { value: 'screening', label: 'Screening', hint: 'Efficient, comparable, must-have signals' },
]

const DURATION_PRESETS = [15, 30, 45, 60]

const STATE_META: Record<string, { label: string; tone: 'ok' | 'warn' | 'danger' | 'neutral' | 'active' }> = {
  created: { label: 'Created', tone: 'neutral' },
  planning: { label: 'Planning', tone: 'active' },
  questioning: { label: 'Live', tone: 'active' },
  paused: { label: 'Paused', tone: 'warn' },
  interrupted: { label: 'Interrupted', tone: 'warn' },
  completed: { label: 'Completed', tone: 'ok' },
  cancelled: { label: 'Cancelled', tone: 'neutral' },
  error: { label: 'Error', tone: 'danger' },
}

const VOICE_STATE_META: Record<string, { label: string; tone: 'ok' | 'warn' | 'danger' | 'neutral' | 'active'; blurb: string }> = {
  idle: { label: 'Ready', tone: 'neutral', blurb: 'Connect your microphone to begin.' },
  thinking: { label: 'Interviewer thinking', tone: 'active', blurb: 'Preparing the next question…' },
  speaking: { label: 'Interviewer speaking', tone: 'active', blurb: 'Listen — you can interrupt at any time.' },
  listening: { label: 'Listening', tone: 'ok', blurb: 'Your turn. Speak naturally; the transcript appears live.' },
  processing: { label: 'Thinking', tone: 'active', blurb: 'Evaluating your answer and deciding what to ask next.' },
  paused: { label: 'Paused', tone: 'warn', blurb: 'The interview is paused.' },
  interrupted: { label: 'Interrupted', tone: 'warn', blurb: 'Stopped mid-sentence. Your turn.' },
  reconnecting: { label: 'Reconnecting…', tone: 'warn', blurb: 'Connection lost. Reconnecting to the interview — this can take a few seconds.' },
  cancelled: { label: 'Cancelled', tone: 'neutral', blurb: 'Session cancelled.' },
  completed: { label: 'Completed', tone: 'ok', blurb: 'Interview complete.' },
  error: { label: 'Voice error', tone: 'danger', blurb: 'A voice problem occurred.' },
}

interface TranscriptLine {
  role: 'interviewer' | 'candidate'
  text: string
  partial?: boolean
}

export function InterviewPage() {
  const [sessionId, setSessionId] = useState<number | null>(null)
  const [kind, setKind] = useState('general')
  const [duration, setDuration] = useState(30)
  const [style, setStyle] = useState('structured')
  const [mode, setMode] = useState<'text' | 'voice'>('voice')
  const [voiceState, setVoiceState] = useState<VoiceState>('idle')
  const [evaluation, setEvaluation] = useState<number | null>(null)
  const [answer, setAnswer] = useState('')
  const [lastHint, setLastHint] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [transcript, setTranscript] = useState<TranscriptLine[]>([])
  const [currentQuestion, setCurrentQuestion] = useState<{ id: number; text: string; difficulty: string; type: string; rationale: string | null; source?: string | null; sourceRef?: string | null } | null>(null)
  const keyCounter = useRef(0)
  const voiceRef = useRef<VoiceClient | null>(null)
  const modeRef = useRef<'text' | 'voice'>(mode)
  modeRef.current = mode
  const transcriptEndRef = useRef<HTMLDivElement>(null)

  const create = useCreateInterview()
  const { activeId } = useResolvedProfile(DEFAULT_USER_ID)
  const ctx = useInterviewContext(DEFAULT_USER_ID, activeId)
  const docs = useDocuments(DEFAULT_USER_ID, activeId)
  const setPreferred = useSetPreferredDocument(DEFAULT_USER_ID, activeId ?? 0)
  const sessions = useInterviews(DEFAULT_USER_ID, activeId)
  const roles = useRoles(DEFAULT_USER_ID, activeId)
  const session = useInterview(sessionId ?? 0, DEFAULT_USER_ID)
  const actions = useInterviewAction()

  useSSE(sessionId ? `/api/v1/interviews/${sessionId}/events?user_id=${DEFAULT_USER_ID}` : '', {
    enabled: sessionId != null,
    onEvent: (event) => {
      // Question ownership: in VOICE mode the WebSocket owns the question +
      // transcript (the server publishes to both SSE and WS). The SSE branch
      // must NOT append a second interviewer line for the same question.
      if (
        event.type === 'question' &&
        typeof event.data.text === 'string' &&
        modeRef.current !== 'voice'
      ) {
        setCurrentQuestion({
          id: Number(event.data.question_id),
          text: event.data.text,
          difficulty: String(event.data.difficulty ?? ''),
          type: String(event.data.type ?? ''),
          rationale: typeof event.data.rationale === 'string' ? event.data.rationale : null,
          source: typeof event.data.source === 'string' ? event.data.source : null,
          sourceRef: typeof event.data.source_ref === 'string' ? event.data.source_ref : null,
        })
        setLastHint(null)
        setAnswer('')
        setTranscript((t) => [...t, { role: 'interviewer', text: String(event.data.text) }])
      }
      if (event.type === 'hint' && typeof event.data.hint === 'string') setLastHint(event.data.hint)
      if (event.type === 'evaluation' && event.data.overall != null) {
        // Surface the live evaluation (submitAnswer already appends the
        // candidate transcript line + clears the answer box).
        setEvaluation(Number(event.data.overall))
      }
      if (event.type === 'session_status') {
        const status = String(event.data.status ?? '')
        if (status === 'completed' || status === 'cancelled') {
          // P0: the session ended via ANY path (HTTP stop/cancel, SSE, etc.)
          // — the active voice client must be torn down so interviewer TTS
          // cannot keep playing. The server state is authoritative; this
          // only stops local audio + the connection.
          void voiceRef.current?.disconnect()
          setSessionId(null)
        }
      }
    },
  })

  async function startInterview() {
    setError(null)
    try {
      const s = await create.mutateAsync({
        user_id: DEFAULT_USER_ID,
        kind,
        role_id: roles.data?.at(-1)?.id,
        profile_id: activeId ?? undefined,
        duration_minutes: duration,
        focus_competency_ids: [],
        mode: 'text',
        style,
      })
      setSessionId(s.id)
      await actions.begin.mutateAsync({ interviewId: s.id, userId: DEFAULT_USER_ID })
      await actions.nextQuestion.mutateAsync({ interviewId: s.id, userId: DEFAULT_USER_ID })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start interview')
      setSessionId(null)
    }
  }

  async function startVoiceInterview() {
    setError(null)
    setTranscript([])
    setEvaluation(null)
    setVoiceState('idle')
    try {
      const s = await create.mutateAsync({
        user_id: DEFAULT_USER_ID,
        kind,
        role_id: roles.data?.at(-1)?.id,
        profile_id: activeId ?? undefined,
        duration_minutes: duration,
        focus_competency_ids: [],
        mode: 'voice',
        style,
      })
      setSessionId(s.id)
      const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
      const url = `${proto}://${window.location.host}/api/v1/ws/voice/${s.id}?user_id=${DEFAULT_USER_ID}`
      const client = new VoiceClient(url, {
        onState: (st) => setVoiceState(st),
        onQuestion: (q) => {
          setCurrentQuestion({ id: q.id, text: q.text, difficulty: q.difficulty, type: '', rationale: null, source: q.source ?? null, sourceRef: q.source_ref ?? null })
          setLastHint(null)
          setTranscript((t) => [...t, { role: 'interviewer', text: q.text }])
        },
        onResume: (q) => {
          // Phase H: reconnect resync — restore the active question from
          // the server's authoritative state without duplicating it.
          if (q && q.text) {
            setCurrentQuestion({ id: q.id, text: q.text, difficulty: q.difficulty, type: '', rationale: null, source: q.source ?? null, sourceRef: q.source_ref ?? null })
          }
        },
        onPartial: (text) =>
          setTranscript((t) => {
            const base = t.filter((l) => !(l.role === 'candidate' && l.partial))
            return [...base, { role: 'candidate', text, partial: true }]
          }),
        onFinalTranscript: (text) => {
          // An empty final means the turn yielded no recognized speech — it
          // must not append an empty candidate line (no repeated "YOU" rows).
          if (!text) return
          setTranscript((t) => {
            const base = t.filter((l) => !(l.role === 'candidate' && l.partial))
            return [...base, { role: 'candidate', text }]
          })
        },
        onEvaluation: (overall) => setEvaluation(overall),
        onError: (code, message) => {
          if (code !== 'tts_unavailable' && code !== 'asr_failed') setError(message)
        },
      })
      voiceRef.current = client
      await client.start()
    } catch (err) {
      // H.9: micError payloads are {code, message}; keep them user-actionable.
      const code = typeof err === 'object' && err !== null && 'code' in err ? String(err.code) : 'unknown'
      const message = err instanceof Error ? err.message : 'Failed to start voice interview'
      setError(message)
      setSessionId(null)
      setVoiceState(code === 'permission_denied' ? 'error' : 'error')
    }
  }

  async function endVoice() {
    await voiceRef.current?.stop()
    voiceRef.current = null
    setSessionId(null)
  }

  async function cancelVoice() {
    await voiceRef.current?.cancel()
    voiceRef.current = null
    setSessionId(null)
  }

  async function submitAnswer() {
    if (!answer.trim() || !currentQuestion) return
    setError(null)
    const text = answer.trim()
    const key = `k-${sessionId}-${currentQuestion.id}-${++keyCounter.current}`
    try {
      await actions.answer.mutateAsync({ interviewId: sessionId ?? 0, userId: DEFAULT_USER_ID, questionId: currentQuestion.id, text, key })
      setTranscript((t) => [...t, { role: 'candidate', text }])
      setAnswer('')
      await actions.nextQuestion.mutateAsync({ interviewId: sessionId ?? 0, userId: DEFAULT_USER_ID })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Answer submission failed')
    }
  }

  async function requestHint() {
    if (!currentQuestion) return
    try {
      const res = await actions.hint.mutateAsync({ interviewId: sessionId ?? 0, userId: DEFAULT_USER_ID, questionId: currentQuestion.id })
      setLastHint(res.hint)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Hint request failed')
    }
  }

  const status = session.data?.status
  const inSession = sessionId != null && status !== 'completed' && status !== 'cancelled'
  const ctxReady = ctx.data?.grounding.resume ?? false
  const meta = STATE_META[status ?? 'created'] ?? STATE_META.created
  const answering = actions.answer.isPending

  return (
    <div className="space-y-8">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Practice interview</h1>
          <p className="mt-1 text-sm text-fg-2">Adaptive questioning, evidence-backed evaluation, no interruptions by the system.</p>
        </div>
        {status ? (
          <div className="flex items-center gap-2 rounded-full border border-line bg-surface px-3 py-1.5">
            <StatusDot tone={meta.tone} />
            <span className="text-xs font-semibold text-fg">{meta.label}</span>
          </div>
        ) : null}
      </header>

      {error ? <ErrorState title="That didn't work" body={error} /> : null}

      {!inSession ? (
        <div className="grid gap-6 lg:grid-cols-5">
          <Surface className="p-6 lg:col-span-2">
            <SectionHeading>New interview</SectionHeading>
            <InterviewContextPanel
              ctx={ctx.data ?? null}
              loading={ctx.isLoading}
              resumes={(docs.data ?? []).filter((d) => d.kind === 'resume').map((d) => ({ id: d.id, filename: d.filename, status: d.status }))}
              jds={(docs.data ?? []).filter((d) => d.kind === 'jd').map((d) => ({ id: d.id, filename: d.filename, status: d.status }))}
              onSelect={(kind, documentId) => {
                if (activeId != null) void setPreferred.mutateAsync({ kind, documentId })
              }}
            />
            <div className="space-y-4">
              <Field label="Mode">
                <Select value={mode} onChange={(e) => setMode(e.target.value as 'text' | 'voice')}>
                  <option value="voice">Live voice interview</option>
                  <option value="text">Typed interview</option>
                </Select>
              </Field>
              <Field label="Interview type">
                <Select value={kind} onChange={(e) => setKind(e.target.value)}>
                  {KINDS.map((k) => (
                    <option key={k.value} value={k.value}>{k.label}</option>
                  ))}
                </Select>
              </Field>
              <Field label="Interviewer style">
                <Select value={style} onChange={(e) => setStyle(e.target.value)}>
                  {STYLES.map((s) => (
                    <option key={s.value} value={s.value}>{s.label}</option>
                  ))}
                </Select>
                <p className="mt-1.5 text-xs leading-relaxed text-fg-3">
                  {STYLES.find((s) => s.value === style)?.hint} — the interviewer persona shapes every question.
                </p>
              </Field>
              <Field label="Duration" hint="The interviewer adapts pacing and coverage to fit.">
                <div className="flex items-center gap-2">
                  {DURATION_PRESETS.map((d) => (
                    <button
                      key={d}
                      type="button"
                      onClick={() => setDuration(d)}
                      className={`rounded-lg border px-3 py-1.5 text-sm font-medium transition-colors ${
                        duration === d
                          ? 'border-accent bg-accent-soft text-accent'
                          : 'border-line bg-surface text-fg-2 hover:border-accent/40'
                      }`}
                    >
                      {d} min
                    </button>
                  ))}
                </div>
              </Field>
              {mode === 'voice' ? (
                <Button size="lg" className="w-full" onClick={() => void startVoiceInterview()} disabled={create.isPending || !ctxReady}>
                  {create.isPending ? 'Connecting…' : '🎙 Start Live Voice Interview'}
                </Button>
              ) : (
                <Button size="lg" className="w-full" onClick={() => void startInterview()} disabled={create.isPending || actions.begin.isPending || !ctxReady}>
                  {create.isPending ? 'Creating…' : 'Start typed interview'}
                </Button>
              )}
              <p className="text-xs leading-relaxed text-fg-3">
                {mode === 'voice'
                  ? 'You hear the interviewer, speak your answers aloud, and the conversation adapts to what you demonstrate. Interrupt any time; stop whenever you are ready.'
                  : 'Questions adapt to your demonstrated evidence. Answers are evaluated against 13 dimensions and update your readiness.'}
              </p>
            </div>
          </Surface>

          <Surface className="p-6 lg:col-span-3">
            <SectionHeading>Past sessions</SectionHeading>
            {!sessions.data?.length ? (
              <EmptyState icon="🎙️" title="No sessions yet" body="Start a practice interview. Every answered question produces an evaluation and evidence." />
            ) : (
              <ul className="divide-y divide-line">
                {sessions.data.slice(0, 10).map((s) => (
                  <li key={s.id} className="flex items-center justify-between py-3">
                    <div>
                      <p className="text-sm font-medium text-fg">{s.kind}</p>
                      <p className="text-xs text-fg-3">
                        {s.started_at ? new Date(s.started_at).toLocaleDateString() : ''} · {s.status}
                      </p>
                    </div>
                    <Link className="text-sm font-medium text-accent hover:underline" to={`/interview/${s.id}/report`}>
                      Report →
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </Surface>
        </div>
      ) : (
        /* Focused interview workspace */
        <div className={`grid gap-6 lg:grid-cols-3 ${answering ? 'pramya-focus-lock' : ''}`}>
          <div className="space-y-5 lg:col-span-2">
            <Surface className="p-6">
              <SectionHeading>Current question</SectionHeading>
              {currentQuestion ? (
                <>
                  <p className="text-xl font-semibold leading-relaxed tracking-tight text-fg">{currentQuestion.text}</p>
                  <div className="mt-3 flex gap-2">
                    <Pill tone="accent">{currentQuestion.difficulty}</Pill>
                    <Pill>{currentQuestion.type}</Pill>
                  </div>
                  {provenanceLabel(currentQuestion.source, currentQuestion.sourceRef) ? (
                    <p className="mt-2 text-xs text-fg-3">
                      {provenanceLabel(currentQuestion.source, currentQuestion.sourceRef)}
                    </p>
                  ) : null}
                  {evaluation != null ? (
                    <div className="mt-4 rounded-lg border border-line bg-accent-soft p-3.5">
                      <p className="text-xs font-semibold uppercase tracking-wide text-accent">Answer evaluated</p>
                      <p className="mt-1 text-sm text-fg">Overall score: {evaluation.toFixed(1)} / 10 — the next question adapts to this answer.</p>
                    </div>
                  ) : null}
                  {currentQuestion.rationale ? (
                    <details className="mt-4 rounded-lg border border-line bg-surface-2 px-3 py-2.5 text-sm">
                      <summary className="cursor-pointer text-xs font-medium text-fg-3 hover:text-fg-2">
                        Why this question
                      </summary>
                      <p className="mt-2 leading-relaxed text-fg-2">{currentQuestion.rationale}</p>
                    </details>
                  ) : null}
                </>
              ) : (
                <Spinner label="Preparing the next question…" />
              )}
            </Surface>

            {mode === 'voice' ? (
              /* Voice instrument: state + controls (flagship workspace) */
              <Surface className={`p-6 transition-colors ${voiceState === 'speaking' || voiceState === 'processing' ? 'pramya-focus-lock' : ''}`}>
                <SectionHeading>Voice session</SectionHeading>
                <div className="flex items-center gap-3 rounded-xl border border-line bg-track/60 px-4 py-4">
                  <div className={`h-2.5 w-2.5 shrink-0 rounded-full ${voiceState === 'listening' ? 'bg-ok animate-pulse' : voiceState === 'speaking' ? 'bg-accent animate-pulse' : voiceState === 'processing' ? 'bg-warn animate-pulse' : voiceState === 'error' ? 'bg-danger' : 'bg-fg-3'}`} />
                  <div className="min-w-0">
                    <p className="text-sm font-semibold text-fg">
                      {VOICE_STATE_META[voiceState]?.label ?? 'Ready'}
                    </p>
                    <p className="mt-0.5 text-xs leading-relaxed text-fg-2">
                      {VOICE_STATE_META[voiceState]?.blurb ?? 'Connect your microphone to begin.'}
                    </p>
                  </div>
                </div>
                <div className="mt-4 flex flex-wrap items-center gap-2">
                  <Button variant="danger" onClick={() => voiceRef.current?.interrupt()} disabled={voiceState !== 'speaking'}>
                    Interrupt
                  </Button>
                  {voiceState === 'listening' ? (
                    <Button variant="primary" onClick={() => voiceRef.current?.doneSpeaking()}>
                      Done speaking
                    </Button>
                  ) : null}
                  {voiceState === 'listening' || voiceState === 'processing' || voiceState === 'speaking' ? (
                    <Button variant="ghost" onClick={() => voiceRef.current?.pause()}>Pause</Button>
                  ) : null}
                  {voiceState === 'paused' ? (
                    <Button variant="ghost" onClick={() => voiceRef.current?.resume()}>Resume</Button>
                  ) : null}
                  <span className="flex-1" />
                  <Button variant="secondary" onClick={() => void endVoice()}>End interview</Button>
                  <Button variant="ghost" onClick={() => void cancelVoice()}>Cancel</Button>
                </div>
                <p className="mt-4 text-xs leading-relaxed text-fg-3">
                  Partial transcripts appear live as you speak; they stabilize into your recorded answer. Interrupting the interviewer is fine — nothing is lost.
                </p>
              </Surface>
            ) : (
            <Surface className="p-6">
              <SectionHeading>Your answer</SectionHeading>
              <textarea
                aria-label="Your answer"
                className="min-h-36 w-full resize-y rounded-lg border border-line bg-surface px-3 py-2.5 text-sm leading-relaxed focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/20"
                placeholder="Answer as you would in a real interview — specifics, tradeoffs, examples…"
                value={answer}
                onChange={(e) => setAnswer(e.target.value)}
                onKeyDown={(e) => {
                  if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') void submitAnswer()
                }}
              />
              <div className="mt-3 flex flex-wrap items-center gap-2">
                <Button onClick={() => void submitAnswer()} disabled={!answer.trim() || answering}>
                  {answering ? 'Evaluating…' : 'Submit answer'}
                  <kbd className="ml-1 hidden rounded border border-white/30 px-1 text-[10px] opacity-70 sm:inline">⌘⏎</kbd>
                </Button>
                <Button variant="secondary" onClick={() => void requestHint()} disabled={!currentQuestion || actions.hint.isPending}>
                  Request hint
                </Button>
                <span className="flex-1" />
                {status === 'questioning' ? (
                  <Button variant="ghost" onClick={() => void actions.pause.mutateAsync({ interviewId: sessionId ?? 0, userId: DEFAULT_USER_ID })}>Pause</Button>
                ) : null}
                {status === 'paused' ? (
                  <Button variant="ghost" onClick={() => void actions.resume.mutateAsync({ interviewId: sessionId ?? 0, userId: DEFAULT_USER_ID })}>Resume</Button>
                ) : null}
                <Button variant="danger" onClick={() => void actions.stop.mutateAsync({ interviewId: sessionId ?? 0, userId: DEFAULT_USER_ID })}>End</Button>
              </div>
              {lastHint ? (
                <div className="mt-4 rounded-lg border border-line bg-warn-soft p-3.5">
                  <p className="text-xs font-semibold uppercase tracking-wide text-warn">Hint</p>
                  <p className="mt-1 text-sm text-warn">{lastHint}</p>
                </div>
              ) : null}
            </Surface>
            )}

            <Surface className="p-6">
              <SectionHeading>Transcript</SectionHeading>
              {!transcript.length ? (
                <p className="text-sm text-fg-3">The live transcript appears here as the interview unfolds.</p>
              ) : (
                <div className="max-h-72 space-y-3 overflow-y-auto pr-1">
                  {transcript.map((line, i) => (
                    <div key={i} className={`flex gap-3 ${line.role === 'candidate' ? 'justify-end' : ''}`}>
                      <div className={`max-w-[85%] rounded-lg px-3.5 py-2.5 ${line.role === 'interviewer' ? 'bg-track' : 'bg-accent-soft'}`}>
                        <p className="text-[11px] font-semibold uppercase tracking-wide text-fg-3">
                          {line.role === 'interviewer' ? 'Interviewer' : 'You'}
                        </p>
                        <p className="mt-0.5 text-sm leading-relaxed text-fg">{line.text}</p>
                      </div>
                    </div>
                  ))}
                  <div ref={transcriptEndRef} />
                </div>
              )}
            </Surface>
          </div>

          <Surface className="h-fit p-5 lg:sticky lg:top-20">
            <SectionHeading>Session</SectionHeading>
            <dl className="text-sm">
              <div className="flex justify-between py-1.5"><dt className="text-fg-2">Mode</dt><dd className="font-medium capitalize">{String(session.data?.config?.mode ?? 'text')}</dd></div>
              <div className="flex justify-between py-1.5"><dt className="text-fg-2">Style</dt><dd className="font-medium capitalize">{String(session.data?.config?.style ?? style)}</dd></div>
              <div className="flex justify-between py-1.5"><dt className="text-fg-2">Duration</dt><dd className="font-medium">{String(session.data?.config?.duration_minutes ?? duration)} min</dd></div>
              <div className="flex justify-between py-1.5"><dt className="text-fg-2">Status</dt><dd className="font-medium capitalize">{status}</dd></div>
            </dl>
            <Divider className="my-3" />
            <p className="text-xs leading-relaxed text-fg-3">
              Each answer is evaluated on 13 dimensions; evidence-backed claims update your ledger, and readiness reflects what you demonstrate — not what you claim.
            </p>
            <Divider className="my-3" />
            <Button variant="secondary" className="w-full" onClick={() => void actions.cancel.mutateAsync({ interviewId: sessionId ?? 0, userId: DEFAULT_USER_ID })}>
              Cancel session
            </Button>
          </Surface>
        </div>
      )}
    </div>
  )
}
