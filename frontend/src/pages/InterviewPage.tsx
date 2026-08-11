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

interface TranscriptLine {
  role: 'interviewer' | 'candidate'
  text: string
}

export function InterviewPage() {
  const [sessionId, setSessionId] = useState<number | null>(null)
  const [kind, setKind] = useState('general')
  const [duration, setDuration] = useState(30)
  const [answer, setAnswer] = useState('')
  const [lastHint, setLastHint] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [transcript, setTranscript] = useState<TranscriptLine[]>([])
  const [currentQuestion, setCurrentQuestion] = useState<{ id: number; text: string; difficulty: string; type: string } | null>(null)
  const keyCounter = useRef(0)
  const transcriptEndRef = useRef<HTMLDivElement>(null)

  const create = useCreateInterview()
  const sessions = useInterviews(DEFAULT_USER_ID)
  const roles = useRoles(DEFAULT_USER_ID)
  const session = useInterview(sessionId ?? 0, DEFAULT_USER_ID)
  const actions = useInterviewAction(sessionId ?? 0)

  useSSE(sessionId ? `/api/v1/interviews/${sessionId}/events?user_id=${DEFAULT_USER_ID}` : '', {
    enabled: sessionId != null,
    onEvent: (event) => {
      if (event.type === 'question' && typeof event.data.text === 'string') {
        setCurrentQuestion({
          id: Number(event.data.question_id),
          text: event.data.text,
          difficulty: String(event.data.difficulty ?? ''),
          type: String(event.data.type ?? ''),
        })
        setLastHint(null)
        setAnswer('')
        setTranscript((t) => [...t, { role: 'interviewer', text: String(event.data.text) }])
      }
      if (event.type === 'hint' && typeof event.data.hint === 'string') setLastHint(event.data.hint)
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
      await actions.begin.mutateAsync(DEFAULT_USER_ID)
      await actions.nextQuestion.mutateAsync(DEFAULT_USER_ID)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start interview')
      setSessionId(null)
    }
  }

  async function submitAnswer() {
    if (!answer.trim() || !currentQuestion) return
    setError(null)
    const text = answer.trim()
    const key = `k-${sessionId}-${currentQuestion.id}-${++keyCounter.current}`
    try {
      await actions.answer.mutateAsync({ userId: DEFAULT_USER_ID, questionId: currentQuestion.id, text, key })
      setTranscript((t) => [...t, { role: 'candidate', text }])
      setAnswer('')
      await actions.nextQuestion.mutateAsync(DEFAULT_USER_ID)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Answer submission failed')
    }
  }

  async function requestHint() {
    if (!currentQuestion) return
    try {
      const res = await actions.hint.mutateAsync({ userId: DEFAULT_USER_ID, questionId: currentQuestion.id })
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
              <Button size="lg" className="w-full" onClick={() => void startInterview()} disabled={create.isPending || actions.begin.isPending}>
                {create.isPending ? 'Creating…' : 'Start interview'}
              </Button>
              <p className="text-xs leading-relaxed text-fg-3">
                Questions adapt to your demonstrated evidence. Answers are evaluated against 13 dimensions and update your readiness.
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
                </>
              ) : (
                <Spinner label="Preparing the next question…" />
              )}
            </Surface>

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
                  <Button variant="ghost" onClick={() => void actions.pause.mutateAsync(DEFAULT_USER_ID)}>Pause</Button>
                ) : null}
                {status === 'paused' ? (
                  <Button variant="ghost" onClick={() => void actions.resume.mutateAsync(DEFAULT_USER_ID)}>Resume</Button>
                ) : null}
                <Button variant="danger" onClick={() => void actions.stop.mutateAsync(DEFAULT_USER_ID)}>End</Button>
              </div>
              {lastHint ? (
                <div className="mt-4 rounded-lg border border-line bg-warn-soft p-3.5">
                  <p className="text-xs font-semibold uppercase tracking-wide text-warn">Hint</p>
                  <p className="mt-1 text-sm text-warn">{lastHint}</p>
                </div>
              ) : null}
            </Surface>

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
            <Button variant="secondary" className="w-full" onClick={() => void actions.cancel.mutateAsync(DEFAULT_USER_ID)}>
              Cancel session
            </Button>
          </Surface>
        </div>
      )}
    </div>
  )
}
