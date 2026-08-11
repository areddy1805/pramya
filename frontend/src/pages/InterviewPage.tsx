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
import { Badge, Button, Card, EmptyState, ErrorState, SectionTitle } from '../components/ui'

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

export function InterviewPage() {
  const [sessionId, setSessionId] = useState<number | null>(null)
  const [kind, setKind] = useState('general')
  const [duration, setDuration] = useState(30)
  const [answer, setAnswer] = useState('')
  const [lastHint, setLastHint] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [transcript, setTranscript] = useState<{ role: string; text: string }[]>([])
  const keyCounter = useRef(0)

  const create = useCreateInterview()
  const sessions = useInterviews(DEFAULT_USER_ID)
  const roles = useRoles(DEFAULT_USER_ID)
  const session = useInterview(sessionId ?? 0, DEFAULT_USER_ID)
  const actions = useInterviewAction(sessionId ?? 0)
  const [currentQuestion, setCurrentQuestion] = useState<{ id: number; text: string; difficulty: string; type: string } | null>(null)

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
      if (event.type === 'hint' && typeof event.data.hint === 'string') {
        setLastHint(event.data.hint)
      }
      if (event.type === 'session_status') {
        const status = String(event.data.status ?? '')
        if (status === 'completed' || status === 'cancelled') {
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
        duration_minutes: duration,
        focus_competency_ids: [],
        mode: 'text',
      })
      setSessionId(s.id)
      await actions.begin.mutateAsync(DEFAULT_USER_ID)
      await actions.nextQuestion.mutateAsync(DEFAULT_USER_ID)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'failed to start interview')
    }
  }

  async function submitAnswer() {
    if (!answer.trim() || !currentQuestion) return
    setError(null)
    const text = answer.trim()
    const key = `k-${sessionId}-${currentQuestion.id}-${++keyCounter.current}`
    await actions.answer.mutateAsync({
      userId: DEFAULT_USER_ID,
      questionId: currentQuestion.id,
      text,
      key,
    })
    setTranscript((t) => [...t, { role: 'candidate', text }])
    setAnswer('')
    // Next question (evaluation handled server-side; follow-ups stream via SSE).
    await actions.nextQuestion.mutateAsync(DEFAULT_USER_ID)
  }

  async function requestHint() {
    if (!currentQuestion) return
    const res = await actions.hint.mutateAsync({
      userId: DEFAULT_USER_ID,
      questionId: currentQuestion.id,
    })
    setLastHint(res.hint)
  }

  const status = session.data?.status
  const inSession = sessionId != null && status !== 'completed' && status !== 'cancelled'

  return (
    <div className="space-y-6">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">Practice Interview</h1>
          <p className="mt-1 text-sm text-slate-600">Adaptive text interview · evidence-backed evaluation</p>
        </div>
        {status ? <Badge tone={status === 'questioning' ? 'green' : status === 'paused' ? 'amber' : 'blue'}>{status}</Badge> : null}
      </header>

      {error ? <ErrorState message={error} /> : null}

      {!inSession ? (
        <div className="grid gap-6 lg:grid-cols-2">
          <Card>
            <SectionTitle>New interview</SectionTitle>
            <label className="block text-sm">
              <span className="text-slate-600">Mode</span>
              <select className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" value={kind} onChange={(e) => setKind(e.target.value)}>
                {KINDS.map((k) => (
                  <option key={k.value} value={k.value}>{k.label}</option>
                ))}
              </select>
            </label>
            <label className="mt-3 block text-sm">
              <span className="text-slate-600">Duration (minutes)</span>
              <input
                type="number"
                min={5}
                max={120}
                className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                value={duration}
                onChange={(e) => setDuration(Number(e.target.value))}
              />
            </label>
            <div className="mt-4">
              <Button onClick={() => void startInterview()} disabled={create.isPending || actions.begin.isPending}>
                {create.isPending ? 'Creating…' : 'Start interview'}
              </Button>
            </div>
          </Card>

          <Card>
            <SectionTitle>Past sessions</SectionTitle>
            {!sessions.data?.length ? (
              <EmptyState title="No sessions yet" hint="Start your first practice interview." />
            ) : (
              <ul className="divide-y divide-slate-100">
                {sessions.data.slice(0, 10).map((s) => (
                  <li key={s.id} className="flex items-center justify-between py-2 text-sm">
                    <span className="text-slate-700">{s.kind} · {s.status}</span>
                    <Link className="text-blue-700 hover:underline" to={`/interview/${s.id}/report`}>
                      Report →
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </div>
      ) : (
        <div className="grid gap-6 lg:grid-cols-3">
          <div className="space-y-4 lg:col-span-2">
            <Card>
              <SectionTitle>Current question</SectionTitle>
              {currentQuestion ? (
                <>
                  <p className="text-lg font-medium text-slate-900">{currentQuestion.text}</p>
                  <div className="mt-2 flex gap-2">
                    <Badge tone="blue">{currentQuestion.difficulty}</Badge>
                    <Badge>{currentQuestion.type}</Badge>
                  </div>
                </>
              ) : (
                <p className="text-sm text-slate-500">Waiting for question…</p>
              )}
            </Card>

            <Card>
              <SectionTitle>Your answer</SectionTitle>
              <textarea
                className="min-h-32 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                placeholder="Type your answer…"
                value={answer}
                onChange={(e) => setAnswer(e.target.value)}
              />
              <div className="mt-3 flex flex-wrap gap-2">
                <Button onClick={() => void submitAnswer()} disabled={!answer.trim() || actions.answer.isPending}>
                  {actions.answer.isPending ? 'Evaluating…' : 'Submit answer'}
                </Button>
                <Button variant="secondary" onClick={() => void requestHint()} disabled={!currentQuestion || actions.hint.isPending}>
                  Request hint
                </Button>
                <Button variant="ghost" onClick={() => void actions.pause.mutateAsync(DEFAULT_USER_ID)} disabled={status !== 'questioning'}>
                  Pause
                </Button>
                {status === 'paused' ? (
                  <Button variant="ghost" onClick={() => void actions.resume.mutateAsync(DEFAULT_USER_ID)}>
                    Resume
                  </Button>
                ) : null}
                <Button variant="danger" onClick={() => void actions.stop.mutateAsync(DEFAULT_USER_ID)}>
                  End interview
                </Button>
              </div>
              {lastHint ? (
                <p className="mt-3 rounded-lg bg-amber-50 p-3 text-sm text-amber-900">💡 Hint: {lastHint}</p>
              ) : null}
            </Card>

            <Card>
              <SectionTitle>Transcript</SectionTitle>
              {!transcript.length ? (
                <p className="text-sm text-slate-500">The live transcript will appear here.</p>
              ) : (
                <div className="space-y-2">
                  {transcript.map((line, i) => (
                    <p key={i} className={`text-sm ${line.role === 'interviewer' ? 'text-slate-700' : 'text-slate-900'}`}>
                      <span className="font-semibold">{line.role === 'interviewer' ? 'Interviewer' : 'You'}:</span>{' '}
                      {line.text}
                    </p>
                  ))}
                </div>
              )}
            </Card>
          </div>

          <Card>
            <SectionTitle>Session</SectionTitle>
            <dl className="space-y-2 text-sm">
              <div className="flex justify-between"><dt className="text-slate-500">Status</dt><dd>{status}</dd></div>
              <div className="flex justify-between"><dt className="text-slate-500">Mode</dt><dd>{String(session.data?.config?.mode ?? 'text')}</dd></div>
              <div className="flex justify-between"><dt className="text-slate-500">Duration</dt><dd>{String(session.data?.config?.duration_minutes ?? 30)} min</dd></div>
            </dl>
            <div className="mt-4">
              <Button variant="secondary" onClick={() => void actions.cancel.mutateAsync(DEFAULT_USER_ID)}>
                Cancel session
              </Button>
            </div>
          </Card>
        </div>
      )}
    </div>
  )
}
