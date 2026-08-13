import { useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  useCreateInterview,
  useInterview,
  useInterviewAction,
  useInterviews,
  useRoles,
  DEFAULT_USER_ID,
} from '../hooks/queries'
import { useSSE } from '../hooks/useSSE'
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
  const [mode, setMode] = useState<'text' | 'voice'>('voice')
  const [voiceState, setVoiceState] = useState<VoiceState>('idle')
  const [evaluation, setEvaluation] = useState<number | null>(null)
  const [answer, setAnswer] = useState('')
  const [lastHint, setLastHint] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [transcript, setTranscript] = useState<TranscriptLine[]>([])
  const [currentQuestion, setCurrentQuestion] = useState<{ id: number; text: string; difficulty: string; type: string; rationale: string | null } | null>(null)
  const keyCounter = useRef(0)
  const voiceRef = useRef<VoiceClient | null>(null)
  const transcriptEndRef = useRef<HTMLDivElement>(null)

  const create = useCreateInterview()
  const sessions = useInterviews(DEFAULT_USER_ID)
  const roles = useRoles(DEFAULT_USER_ID)
  const session = useInterview(sessionId ?? 0, DEFAULT_USER_ID)
  const actions = useInterviewAction()

  useSSE(sessionId ? `/api/v1/interviews/${sessionId}/events?user_id=${DEFAULT_USER_ID}` : '', {
    enabled: sessionId != null,
    onEvent: (event) => {
      if (event.type === 'question' && typeof event.data.text === 'string') {
        setCurrentQuestion({
          id: Number(event.data.question_id),
          text: event.data.text,
          difficulty: String(event.data.difficulty ?? ''),
          type: String(event.data.type ?? ''),
          rationale: typeof event.data.rationale === 'string' ? event.data.rationale : null,
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
        if (status === 'completed' || status === 'cancelled') setSessionId(null)
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
        duration_minutes: duration,
        focus_competency_ids: [],
        mode: 'text',
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
        duration_minutes: duration,
        focus_competency_ids: [],
        mode: 'voice',
      })
      setSessionId(s.id)
      const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
      const url = `${proto}://${window.location.host}/api/v1/ws/voice/${s.id}?user_id=${DEFAULT_USER_ID}`
      const client = new VoiceClient(url, {
        onState: (st) => setVoiceState(st),
        onQuestion: (q) => {
          setCurrentQuestion({ id: q.id, text: q.text, difficulty: q.difficulty, type: '', rationale: null })
          setLastHint(null)
          setTranscript((t) => [...t, { role: 'interviewer', text: q.text }])
        },
        onResume: (q) => {
          // Phase H: reconnect resync — restore the active question from
          // the server's authoritative state without duplicating it.
          if (q && q.text) {
            setCurrentQuestion({ id: q.id, text: q.text, difficulty: q.difficulty, type: '', rationale: null })
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
              <Field label="Duration" hint="The interviewer adapts pacing to fit.">
                <input
                  type="number"
                  min={5}
                  max={120}
                  className="w-full rounded-lg border border-line bg-surface px-3 py-2 text-sm focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent/20"
                  value={duration}
                  onChange={(e) => setDuration(Number(e.target.value))}
                />
              </Field>
              {mode === 'voice' ? (
                <Button size="lg" className="w-full" onClick={() => void startVoiceInterview()} disabled={create.isPending}>
                  {create.isPending ? 'Connecting…' : '🎙 Start Live Voice Interview'}
                </Button>
              ) : (
                <Button size="lg" className="w-full" onClick={() => void startInterview()} disabled={create.isPending || actions.begin.isPending}>
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
