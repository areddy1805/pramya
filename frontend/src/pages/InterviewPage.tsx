import { useEffect, useRef, useState } from 'react'
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
import {
  Button,
  Divider,
  EmptyState,
  ErrorState,
  Field,
  Micro,
  Pill,
  Seg,
  Select,
  Spinner,
  StatusDot,
  Surface,
  Tag,
} from '../components/ui'

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
  listening: { label: 'Your turn', tone: 'ok', blurb: 'Speak naturally; the transcript appears live.' },
  processing: { label: 'Evaluating', tone: 'active', blurb: 'Reading your answer and deciding what to ask next.' },
  paused: { label: 'Paused', tone: 'warn', blurb: 'The interview is paused.' },
  interrupted: { label: 'Interrupted', tone: 'warn', blurb: 'Stopped mid-sentence. Your turn.' },
  reconnecting: { label: 'Reconnecting…', tone: 'warn', blurb: 'Connection lost. Reconnecting — this can take a few seconds.' },
  cancelled: { label: 'Cancelled', tone: 'neutral', blurb: 'Session cancelled.' },
  completed: { label: 'Completed', tone: 'ok', blurb: 'Interview complete.' },
  error: { label: 'Voice error', tone: 'danger', blurb: 'A voice problem occurred.' },
}

interface TranscriptLine {
  role: 'interviewer' | 'candidate'
  text: string
  partial?: boolean
  source?: string | null
  sourceRef?: string | null
}

interface CurrentQuestion {
  id: number
  text: string
  difficulty: string
  type: string
  rationale: string | null
  source?: string | null
  sourceRef?: string | null
}

function statusOf(doc: InterviewContext['resume']): { label: string; tone: 'ok' | 'warn' | 'danger' | 'neutral' } {
  if (!doc) return { label: 'Missing', tone: 'danger' }
  if (doc.ready) return { label: 'Ready', tone: 'ok' }
  return { label: doc.status, tone: 'warn' }
}

function provenanceLabel(source: string | null | undefined, sourceRef: string | null | undefined): string | null {
  if (!source) return null
  if (source === 'followup') return `Follow-up on your answer · ${sourceRef ?? 'this topic'}`
  if (source === 'weakness') return `Revisits prior feedback · ${sourceRef ?? ''}`
  const label = source.charAt(0).toUpperCase() + source.slice(1)
  return `Based on: ${label} · ${sourceRef ?? ''}`
}

function questionMeta(transcript: TranscriptLine[], index: number): string {
  const line = transcript[index]
  if (!line) return ''
  if (line.source === 'followup') return 'Follow-up'
  const src = line.source ?? ''
  return src.charAt(0).toUpperCase() + src.slice(1)
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
  const [currentQuestion, setCurrentQuestion] = useState<CurrentQuestion | null>(null)
  const keyCounter = useRef(0)
  const voiceRef = useRef<VoiceClient | null>(null)
  const modeRef = useRef<'text' | 'voice'>(mode)
  modeRef.current = mode
  const answerRef = useRef<HTMLTextAreaElement>(null)
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
      if (
        event.type === 'question' &&
        typeof event.data.text === 'string' &&
        modeRef.current !== 'voice'
      ) {
        const q: CurrentQuestion = {
          id: Number(event.data.question_id),
          text: event.data.text,
          difficulty: String(event.data.difficulty ?? ''),
          type: String(event.data.type ?? ''),
          rationale: typeof event.data.rationale === 'string' ? event.data.rationale : null,
          source: typeof event.data.source === 'string' ? event.data.source : null,
          sourceRef: typeof event.data.source_ref === 'string' ? event.data.source_ref : null,
        }
        setCurrentQuestion(q)
        setLastHint(null)
        setAnswer('')
        setTranscript((t) => [...t, { role: 'interviewer', text: q.text, source: q.source, sourceRef: q.sourceRef }])
      }
      if (event.type === 'hint' && typeof event.data.hint === 'string') setLastHint(event.data.hint)
      if (event.type === 'evaluation' && event.data.overall != null) {
        setEvaluation(Number(event.data.overall))
      }
      if (event.type === 'session_status') {
        const status = String(event.data.status ?? '')
        if (status === 'completed' || status === 'cancelled') {
          void voiceRef.current?.disconnect()
        }
      }
    },
  })

  // Keep the answer box focused while answering (text mode).
  useEffect(() => {
    if (sessionId && mode === 'text' && currentQuestion && !actions.answer.isPending) {
      answerRef.current?.focus()
    }
  }, [currentQuestion, sessionId, mode, actions.answer.isPending])

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
      setTranscript([])
      setEvaluation(null)
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
          const qq: CurrentQuestion = { id: q.id, text: q.text, difficulty: q.difficulty, type: '', rationale: null, source: q.source ?? null, sourceRef: q.source_ref ?? null }
          setCurrentQuestion(qq)
          setLastHint(null)
          setTranscript((t) => [...t, { role: 'interviewer', text: q.text, source: q.source ?? null, sourceRef: q.source_ref ?? null }])
        },
        onResume: (q) => {
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
  const live = sessionId != null && status !== 'completed' && status !== 'cancelled'
  const ended = sessionId != null && (status === 'completed' || status === 'cancelled')
  const ctxReady = ctx.data?.grounding.resume ?? false
  const meta = STATE_META[status ?? 'created'] ?? STATE_META.created
  const answering = actions.answer.isPending
  const resumeDocs = (docs.data ?? []).filter((d) => d.kind === 'resume')
  const jdDocs = (docs.data ?? []).filter((d) => d.kind === 'jd')
  const activeProfile = ctx.data?.profile

  return (
    <div className="space-y-6">
      {ended ? (
        /* ---------- Completion panel ---------- */
        <div className="mx-auto max-w-2xl space-y-4">
          <Surface tone="accent" className="px-6 py-8 text-center">
            <Micro className="mb-2">Session {status}</Micro>
            <p className="text-xl font-semibold tracking-tight text-fg">
              {status === 'completed' ? 'Interview complete' : 'Interview ended'}
            </p>
            <p className="mx-auto mt-2 max-w-md text-sm leading-relaxed text-fg-2">
              {status === 'completed'
                ? 'Every answer was evaluated. Your report connects each question to what you said, what was missing, and what to prepare.'
                : 'You can start again any time — context is saved per session.'}
            </p>
            <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
              {status === 'completed' ? (
                <Link to={`/interview/${sessionId}/report`}>
                  <Button size="lg">View report →</Button>
                </Link>
              ) : null}
              <Button variant="secondary" size="lg" onClick={() => setSessionId(null)}>
                {status === 'completed' ? 'Start another interview' : 'Back to practice'}
              </Button>
            </div>
          </Surface>
        </div>
      ) : !live ? (
        /* ---------- Pre-flight briefing ---------- */
        <div className="space-y-6">
          <header className="flex flex-wrap items-end justify-between gap-3">
            <div>
              <Micro>Practice</Micro>
              <h1 className="mt-1 text-xl font-semibold tracking-tight">Prepare for an interview</h1>
              <p className="mt-1 max-w-xl text-sm leading-relaxed text-fg-2">
                Pramya asks you what you actually did, evaluates what you demonstrate, and adapts the next question to your answer.
              </p>
            </div>
          </header>

          {error ? <ErrorState title="Could not start" body={error} /> : null}

          <div className="grid gap-6 lg:grid-cols-3">
            {/* Briefing — one coherent composition */}
            <Surface className="p-6 lg:col-span-2">
              <Micro className="mb-4">Pre-flight</Micro>

              {!ctx.data && !ctx.isLoading ? (
                <EmptyState title="Select a profile first" body="Create or choose a career profile — interviews are grounded in its resume and roles." />
              ) : null}

              {ctx.data ? (
                <div className="space-y-6">
                  {/* Identity */}
                  <div className="flex items-start justify-between gap-4">
                    <div className="min-w-0">
                      <p className="text-lg font-semibold tracking-tight text-fg">{activeProfile?.name ?? '—'}</p>
                      {activeProfile?.positioning ? <p className="mt-0.5 text-sm text-fg-2">{activeProfile.positioning}</p> : null}
                    </div>
                    {ctx.isLoading ? <Spinner label="Loading" subtle /> : null}
                  </div>

                  {/* Using / Against */}
                  <div className="grid gap-5 sm:grid-cols-2">
                    <div>
                      <Micro className="mb-2">Using</Micro>
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <p className="truncate text-sm font-medium text-fg">{ctx.data.resume?.filename ?? 'No resume'}</p>
                          <p className="text-xs text-fg-3">your current resume — what the interviewer knows about you</p>
                        </div>
                        <Pill tone={statusOf(ctx.data.resume).tone}>{statusOf(ctx.data.resume).label}</Pill>
                      </div>
                      <Select
                        aria-label="Resume for this interview"
                        className="mt-2"
                        value={String(ctx.data.resume?.document_id ?? '')}
                        onChange={(e) => onSelectPreferred('resume', e.target.value ? Number(e.target.value) : null)}
                        disabled={resumeDocs.length === 0}
                      >
                        {resumeDocs.length === 0 ? <option value="">No resumes on this profile</option> : null}
                        {resumeDocs.map((d) => (
                          <option key={d.id} value={d.id}>
                            {d.filename} ({d.status})
                          </option>
                        ))}
                      </Select>
                    </div>
                    <div>
                      <Micro className="mb-2">Against</Micro>
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <p className="truncate text-sm font-medium text-fg">{ctx.data.jd?.filename ?? 'Resume-only mode'}</p>
                          <p className="text-xs text-fg-3">
                            {ctx.data.jd ? 'the role you are targeting' : 'no JD — questions stay grounded in your resume'}
                          </p>
                        </div>
                        {ctx.data.jd ? <Pill tone={statusOf(ctx.data.jd).tone}>{statusOf(ctx.data.jd).label}</Pill> : <Tag>optional</Tag>}
                      </div>
                      <Select
                        aria-label="Job description for this interview"
                        className="mt-2"
                        value={String(ctx.data.jd?.document_id ?? '')}
                        onChange={(e) => onSelectPreferred('jd', e.target.value ? Number(e.target.value) : null)}
                      >
                        <option value="">No JD — resume-only interview</option>
                        {jdDocs.map((d) => (
                          <option key={d.id} value={d.id}>
                            {d.filename} ({d.status})
                          </option>
                        ))}
                      </Select>
                    </div>
                  </div>

                  <Divider />

                  {/* Interview configuration */}
                  <div className="grid gap-4 sm:grid-cols-2">
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
                      <span className="mt-1 block text-xs text-fg-3">
                        {STYLES.find((s) => s.value === style)?.hint}
                      </span>
                    </Field>
                    <Field label="Duration">
                      <Seg
                        ariaLabel="Interview duration"
                        value={String(duration)}
                        onChange={(v) => setDuration(Number(v))}
                        options={DURATION_PRESETS.map((d) => ({ value: String(d), label: `${d} min` }))}
                      />
                    </Field>
                    <Field label="Format">
                      <Seg
                        ariaLabel="Interview format"
                        value={mode}
                        onChange={(v) => setMode(v as 'text' | 'voice')}
                        options={[
                          { value: 'voice', label: 'Live voice' },
                          { value: 'text', label: 'Typed' },
                        ]}
                      />
                    </Field>
                  </div>

                  {ctx.data.missing.includes('resume') ? (
                    <div className="flex items-center gap-2 rounded-[var(--r-md)] border border-warn/25 bg-warn-soft px-3 py-2 text-xs leading-relaxed text-warn">
                      This profile has no processed resume. Upload one on the Profile page before starting.
                    </div>
                  ) : null}

                  <Button
                    size="lg"
                    className="w-full"
                    disabled={create.isPending || actions.begin.isPending || !ctxReady}
                    onClick={() => void (mode === 'voice' ? startVoiceInterview() : startInterview())}
                  >
                    {create.isPending ? 'Starting…' : mode === 'voice' ? 'Start live voice interview' : 'Start typed interview'}
                  </Button>
                  <p className="text-center text-xs leading-relaxed text-fg-3">
                    {mode === 'voice'
                      ? 'You hear the interviewer and speak aloud. Interrupt any time; the transcript captures every turn.'
                      : 'Questions adapt to your demonstrated evidence and are evaluated on 13 dimensions.'}
                  </p>
                </div>
              ) : (
                <Spinner label="Loading interview context…" />
              )}
            </Surface>

            {/* Session history */}
            <Surface className="p-5 lg:col-span-1">
              <Micro className="mb-3">Session history</Micro>
              {!sessions.data?.length ? (
                <EmptyState title="No sessions yet" body="Your past practice interviews will appear here with links to their reports." />
              ) : (
                <ul className="divide-y divide-line">
                  {sessions.data.slice(0, 10).map((s) => (
                    <li key={s.id} className="flex items-center justify-between gap-2 py-2.5">
                      <div className="min-w-0">
                        <p className="truncate text-sm font-medium text-fg">{s.kind.replace(/_/g, ' ')}</p>
                        <p className="text-xs text-fg-3">
                          {s.started_at ? new Date(s.started_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric' }) : ''} · {s.status}
                        </p>
                      </div>
                      {s.status === 'completed' ? (
                        <Link className="shrink-0 text-sm font-medium text-accent hover:underline" to={`/interview/${s.id}/report`}>
                          Report →
                        </Link>
                      ) : null}
                    </li>
                  ))}
                </ul>
              )}
            </Surface>
          </div>
        </div>
      ) : (
        /* ---------- Live interview workspace ---------- */
        <div className="mx-auto max-w-4xl">
          {/* Session strip */}
          <div className="mb-5 flex flex-wrap items-center justify-between gap-3 border-b border-line pb-4">
            <div className="flex items-center gap-3">
              <StatusDot tone={meta.tone} />
              <span className="text-sm font-semibold text-fg">{meta.label}</span>
              <span aria-hidden className="text-fg-3">·</span>
              <span className="text-[13px] text-fg-2 capitalize">{String(session.data?.config?.kind ?? kind).replace(/_/g, ' ')}</span>
              {mode === 'voice' ? <Tag>voice</Tag> : <Tag>typed</Tag>}
            </div>
            <div className="flex items-center gap-2">
              <span className="hidden text-xs text-fg-3 sm:inline">
                {String(session.data?.config?.style ?? style).replace(/_/g, ' ')} · {String(session.data?.config?.duration_minutes ?? duration)} min
              </span>
              {mode === 'voice' && (voiceState === 'listening' || voiceState === 'processing' || voiceState === 'speaking') ? (
                <Button variant="ghost" size="sm" onClick={() => voiceRef.current?.pause()}>Pause</Button>
              ) : null}
              {mode === 'voice' && voiceState === 'paused' ? (
                <Button variant="ghost" size="sm" onClick={() => voiceRef.current?.resume()}>Resume</Button>
              ) : null}
              <Button variant="secondary" size="sm" onClick={() => void actions.stop.mutateAsync({ interviewId: sessionId ?? 0, userId: DEFAULT_USER_ID })}>
                End
              </Button>
            </div>
          </div>

          {error ? <ErrorState title="That didn't work" body={error} className="mb-4" /> : null}

          {/* Voice instrument — restrained state + controls */}
          {mode === 'voice' ? (
            <Surface tone={voiceState === 'speaking' || voiceState === 'thinking' ? 'accent' : 'default'} className="mb-5 px-5 py-4">
              <div className="flex flex-wrap items-center gap-x-5 gap-y-3">
                <div className="flex items-center gap-2.5">
                  <StatusDot tone={VOICE_STATE_META[voiceState]?.tone ?? 'neutral'} />
                  <span className="text-sm font-semibold text-fg">{VOICE_STATE_META[voiceState]?.label ?? 'Ready'}</span>
                </div>
                <p className="min-w-0 flex-1 text-xs leading-relaxed text-fg-2">
                  {VOICE_STATE_META[voiceState]?.blurb ?? 'Connect your microphone to begin.'}
                </p>
                <div className="flex items-center gap-2">
                  <Button variant="danger" size="sm" onClick={() => voiceRef.current?.interrupt()} disabled={voiceState !== 'speaking'}>
                    Interrupt
                  </Button>
                  {voiceState === 'listening' ? (
                    <Button size="sm" onClick={() => voiceRef.current?.doneSpeaking()}>Done speaking</Button>
                  ) : null}
                  {voiceState === 'paused' ? (
                    <Button variant="secondary" size="sm" onClick={() => voiceRef.current?.resume()}>Resume</Button>
                  ) : null}
                  {voiceState !== 'paused' && voiceState !== 'cancelled' && voiceState !== 'completed' ? (
                    <Button variant="ghost" size="sm" onClick={() => void endVoice()}>End interview</Button>
                  ) : null}
                </div>
              </div>
            </Surface>
          ) : null}

          {/* Question */}
          <div className="mb-5">
            <div className="mb-2 flex items-center justify-between gap-3">
              <h2 className="text-[11px] font-semibold uppercase tracking-[0.09em] text-fg-3">Current question</h2>
              {currentQuestion ? (
                <div className="flex items-center gap-2">
                  <Tag>{currentQuestion.difficulty}</Tag>
                  {currentQuestion.type ? <Tag>{currentQuestion.type}</Tag> : null}
                </div>
              ) : null}
            </div>
            {currentQuestion ? (
              <>
                <p className="interview-question text-[17px] font-medium leading-[1.65] tracking-[-0.01em] text-fg">{currentQuestion.text}</p>
                {provenanceLabel(currentQuestion.source, currentQuestion.sourceRef) ? (
                  <p className="mt-2 text-xs text-fg-3">{provenanceLabel(currentQuestion.source, currentQuestion.sourceRef)}</p>
                ) : null}
                {evaluation != null ? (
                  <p className="mt-2 text-xs text-fg-2">
                    <span className="font-semibold text-accent">Overall score: {evaluation.toFixed(1)} / 10</span> — the next question adapts to this answer.
                  </p>
                ) : null}
                {currentQuestion.rationale ? (
                  <details className="mt-3">
                    <summary className="cursor-pointer text-xs font-medium text-fg-3 transition-colors hover:text-fg-2">
                      Why this question
                    </summary>
                    <p className="mt-1.5 max-w-2xl text-[13px] leading-relaxed text-fg-2">{currentQuestion.rationale}</p>
                  </details>
                ) : null}
              </>
            ) : (
              <div className="flex items-center gap-3 rounded-[var(--r-lg)] border border-line bg-surface-2 px-4 py-6">
                <Spinner label="Preparing the next question…" subtle />
              </div>
            )}
          </div>

          {/* Answer (typed mode) */}
          {mode === 'text' ? (
            <Surface className="mb-5 p-5">
              <Micro className="mb-3">Your answer</Micro>
              <textarea
                ref={answerRef}
                aria-label="Your answer"
                className="min-h-32 w-full resize-y rounded-[var(--r-md)] border border-line bg-surface px-3 py-2.5 text-sm leading-relaxed focus:border-accent focus:outline-none focus:shadow-[var(--focus-ring)]"
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
                  <kbd className="kbd">⌘⏎</kbd>
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
              </div>
              {lastHint ? (
                <div className="mt-4 rounded-[var(--r-md)] border border-warn/25 bg-warn-soft px-3.5 py-3">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.09em] text-warn">Hint</p>
                  <p className="mt-1 text-sm leading-relaxed text-warn">{lastHint}</p>
                </div>
              ) : null}
            </Surface>
          ) : null}

          {/* Transcript — the interview record */}
          <div className="mb-5">
            <Micro className="mb-3">Transcript</Micro>
            {!transcript.length ? (
              <p className="text-sm text-fg-3">The live transcript appears here as the interview unfolds.</p>
            ) : (
              <div className="thin-scroll max-h-[22rem] space-y-0 overflow-y-auto border-t border-line">
                {transcript.map((line, i) =>
                  line.role === 'interviewer' ? (
                    <div key={i} className="border-b border-hairline py-3 pr-2">
                      <p className="text-[10px] font-semibold uppercase tracking-[0.09em] text-fg-3">
                        {questionMeta(transcript, i)}
                      </p>
                      <p className="mt-1 text-sm leading-relaxed text-fg">{line.text}</p>
                    </div>
                  ) : (
                    <div key={i} className="border-b border-hairline py-3 pl-6 pr-2">
                      <p className="text-[10px] font-semibold uppercase tracking-[0.09em] text-accent">
                        You{line.partial ? ' · speaking…' : ''}
                      </p>
                      <p className={`mt-1 text-sm leading-relaxed ${line.partial ? 'text-fg-2 italic' : 'text-fg'}`}>{line.text}</p>
                    </div>
                  ),
                )}
                <div ref={transcriptEndRef} />
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )

  function onSelectPreferred(kind: 'resume' | 'jd', documentId: number | null) {
    if (activeId != null) void setPreferred.mutateAsync({ kind, documentId })
  }
}
