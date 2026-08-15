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
import { Button, EmptyState, ErrorState, Spinner } from '../components/ui'
import { LevelCells, Sheet, SheetSection, StencilNum } from '../components/sheet'

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

// Text-mode session blurbs (session status is server-authoritative; the
// register is the stable state key, the blurb carries the instruction).
const SESSION_BLURB: Record<string, string> = {
  created: 'Preparing the session — the first question is on its way.',
  planning: 'Planning the interview — the first question is on its way.',
  questioning: 'Answer the question below — submit when ready.',
  paused: 'The interview is paused.',
  interrupted: 'The session was interrupted.',
  error: 'A problem occurred — see the error note below.',
}

// Fixed voice-state register — the stable state key for the field sheet.
// Cells mirror the authoritative server states; the active cell is lit,
// unreached cells are ghosts (absence drawn deliberately).
const VOICE_REGISTER: Array<{ key: VoiceState; label: string }> = [
  { key: 'idle', label: 'Ready' },
  { key: 'starting', label: 'Starting' },
  { key: 'thinking', label: 'Preparing' },
  { key: 'speaking', label: 'Speaking' },
  { key: 'listening', label: 'Listening' },
  { key: 'processing', label: 'Processing' },
  { key: 'paused', label: 'Paused' },
  { key: 'error', label: 'Error' },
]

const SESSION_REGISTER: Array<{ keys: string[]; label: string }> = [
  { keys: ['created', 'planning'], label: 'Preparing' },
  { keys: ['questioning'], label: 'Questioning' },
  { keys: ['paused'], label: 'Paused' },
  { keys: ['interrupted'], label: 'Interrupted' },
  { keys: ['error'], label: 'Error' },
]

// Session-cell status tone per sheet grammar: draft = live/measured,
// ink-2 = deliberate/quiet, redline = attention/failure.
const SESSION_CELL_TONE: Record<string, string> = {
  created: 'text-draft',
  planning: 'text-draft',
  questioning: 'text-draft',
  paused: 'text-ink-2',
  interrupted: 'text-redline',
  completed: 'text-draft',
  cancelled: 'text-ink-2',
  error: 'text-redline',
}

const HISTORY_TONE: Record<string, string> = {
  completed: 'text-draft',
  cancelled: 'text-ink-3',
  error: 'text-redline',
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

function pad2(n: number): string {
  return String(n).padStart(2, '0')
}

// --- Field-sheet primitives (interview-specific, page-local) -----------------

// Stencil status tag for pre-flight document readiness.
function DocStatusTag({ label, tone, text }: { label: string; tone: 'ok' | 'warn' | 'danger' | 'neutral'; text: string }) {
  const cls = tone === 'ok' ? 'text-draft' : tone === 'danger' ? 'text-redline' : 'text-ink-2'
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className="text-[10px] uppercase tracking-[0.12em] text-ink-3">{label}</span>
      <span className={`stencil text-[10px] uppercase tracking-[0.12em] ${cls}`}>{text}</span>
    </span>
  )
}

// Sheet-styled select — the sheet needs its own form linework (ink hairline,
// paper field); ui.Select carries the old token system.
function FieldSelect({
  label,
  hint,
  value,
  onChange,
  disabled,
  children,
}: {
  label: string
  hint?: string
  value: string
  onChange: (e: React.ChangeEvent<HTMLSelectElement>) => void
  disabled?: boolean
  children: React.ReactNode
}) {
  return (
    <label className="block text-sm">
      <span className="mb-1 block text-[10px] font-medium uppercase tracking-[0.12em] text-ink-2/70">{label}</span>
      <select
        value={value}
        onChange={onChange}
        disabled={disabled}
        className="h-9 w-full border border-ink/30 bg-sheet px-3 text-sm text-ink focus:border-draft focus:outline-none focus:shadow-[var(--focus-ring)] disabled:bg-sheet-shadow/30 disabled:text-ink-3"
      >
        {children}
      </select>
      {hint ? <span className="mt-1 block text-[11px] text-ink-3">{hint}</span> : null}
    </label>
  )
}

// Sheet-styled segmented control (duration / format presets).
function FieldSeg({
  label,
  value,
  options,
  onChange,
  ariaLabel,
}: {
  label: string
  value: string
  options: Array<{ value: string; label: string }>
  onChange: (value: string) => void
  ariaLabel: string
}) {
  return (
    <div>
      <p className="mb-1 text-[10px] font-medium uppercase tracking-[0.12em] text-ink-2/70">{label}</p>
      <div role="group" aria-label={ariaLabel} className="inline-flex h-9 border border-ink/30 p-0.5">
        {options.map((o) => (
          <button
            key={o.value}
            type="button"
            aria-pressed={value === o.value}
            onClick={() => onChange(o.value)}
            className={`grid h-8 place-items-center px-2.5 text-[11px] font-semibold uppercase tracking-[0.08em] transition-colors duration-[var(--dur-fast)] ${
              value === o.value ? 'bg-ink text-sheet' : 'text-ink-2 hover:text-ink'
            }`}
          >
            {o.label}
          </button>
        ))}
      </div>
    </div>
  )
}

// Operating annotation per authoritative voice state — the instrument face
// label and its one concise operational note.
const VOICE_OPERATION: Record<string, { label: string; note: string }> = {
  idle: { label: 'READY', note: 'No session running — connect your microphone to begin.' },
  starting: { label: 'STARTING', note: 'Connect your microphone to begin.' },
  thinking: { label: 'PREPARING', note: 'The interviewer is preparing the next question — hold on.' },
  speaking: { label: 'INTERVIEWER SPEAKING', note: 'Listen — you can interrupt at any time.' },
  listening: { label: 'YOUR RESPONSE', note: 'Speak naturally; the transcript appears live.' },
  processing: { label: 'PROCESSING ANSWER', note: 'Reading your answer and deciding what to ask next.' },
  paused: { label: 'INTERVIEW PAUSED', note: 'The interview is paused.' },
  interrupted: { label: 'INTERRUPTED — YOUR TURN', note: 'Stopped mid-sentence. Your turn.' },
  reconnecting: { label: 'RECONNECTING', note: 'Connection lost. Reconnecting — this can take a few seconds.' },
  cancelled: { label: 'CANCELLED', note: 'Session cancelled.' },
  completed: { label: 'COMPLETED', note: 'Interview complete.' },
  error: { label: 'ERROR', note: 'A voice problem occurred.' },
}

const VOICE_OP_TONE: Record<string, string> = {
  idle: 'text-ink-2',
  starting: 'text-draft',
  thinking: 'text-draft',
  speaking: 'text-draft',
  listening: 'text-draft',
  processing: 'text-draft',
  paused: 'text-ink-2',
  interrupted: 'text-redline',
  reconnecting: 'text-redline',
  cancelled: 'text-ink-2',
  completed: 'text-draft',
  error: 'text-redline',
}

// One cell of the state register: lit when the server state is here,
// dashed ghost when not (the stable state key + ghost-cells raise). The
// active cell carries a registration tick — the instrument points here.
function RegisterCell({ label, active, danger = false }: { label: string; active: boolean; danger?: boolean }) {
  return (
    <span
      aria-hidden
      className={`relative grid h-7 shrink-0 place-items-center border px-2.5 text-[10px] uppercase leading-none tracking-[0.14em] ${
        active
          ? danger
            ? 'border-redline bg-redline text-sheet'
            : 'border-draft bg-draft-soft text-draft-2'
          : 'border-dashed border-ink/35 text-ink-3'
      }`}
    >
      {label}
      {active ? (
        <span
          className={`absolute -bottom-[5px] left-1/2 h-1.5 w-1.5 -translate-x-1/2 rotate-45 border-b border-r ${
            danger ? 'border-redline bg-redline' : 'border-draft bg-draft'
          }`}
        />
      ) : null}
    </span>
  )
}

// Turn indicator — a fixed two-end register (interviewer ⇄ candidate) with
// a static marker at the active end. The measured answer to "who holds the
// turn?" — drafting grammar, never an animation.
function TurnLine({ state }: { state: string }) {
  const speaking = state === 'speaking'
  const candidate = state === 'listening' || state === 'interrupted'
  const interrupted = state === 'interrupted'
  const pos = speaking ? 0 : candidate ? 100 : 50
  const marker =
    state === 'error' || interrupted ? 'bg-redline' : speaking || state === 'listening' ? 'bg-draft' : 'bg-ink/50'
  return (
    <div className="flex w-full items-center gap-3" aria-hidden>
      <span className={`stencil shrink-0 text-[10px] uppercase tracking-[0.14em] ${speaking ? 'text-draft' : 'text-ink-3'}`}>
        Interviewer
      </span>
      <span className="relative h-2.5 flex-1">
        <span className="absolute inset-x-0 top-1/2 border-t border-ink/40" />
        <span className="absolute left-0 top-1/2 h-2 w-px -translate-y-1/2 bg-ink/50" />
        <span className="absolute right-0 top-1/2 h-2 w-px -translate-y-1/2 bg-ink/50" />
        <span className={`absolute top-1/2 h-2 w-2 -translate-x-1/2 -translate-y-1/2 ${marker}`} style={{ left: `${pos}%` }} />
      </span>
      <span className={`stencil shrink-0 text-[10px] uppercase tracking-[0.14em] ${state === 'listening' ? 'text-draft' : interrupted ? 'text-redline' : 'text-ink-3'}`}>
        Candidate
      </span>
    </div>
  )
}

// Transient state tag (reconnecting / interrupted / terminal) — redline
// annotation beside the register, never a cell of its own.
function RegisterTag({ label, tone }: { label: string; tone: 'redline' | 'draft' | 'ink-2' }) {
  const cls = tone === 'redline' ? 'border-redline/70 text-redline' : tone === 'draft' ? 'border-draft/70 text-draft' : 'border-ink/40 text-ink-2'
  return (
    <span className={`stencil grid h-7 shrink-0 place-items-center border px-2.5 text-[10px] uppercase leading-none tracking-[0.14em] ${cls}`}>
      {label}
    </span>
  )
}

// Compact session cell for the field title block: status stencil, elapsed
// numeral, session facts. Quieter than the dashboard verdict by design —
// one numeral step below the prep stamp, two below the readiness verdict.
function SessionCell({
  status,
  elapsed,
  duration,
  kindLabel,
  mode,
  date,
}: {
  status: string
  elapsed: string | null
  duration: number
  kindLabel: string
  mode: string
  date: string
}) {
  const label = STATE_META[status]?.label ?? STATE_META.created.label
  const tone = SESSION_CELL_TONE[status] ?? 'text-ink-2'
  return (
    <div className="w-full border border-ink/30 bg-sheet-lit/45 px-4 py-3 sm:w-[17rem]">
      <div className="flex items-baseline justify-between gap-3">
        <p className="text-[10px] font-medium uppercase tracking-[0.12em] text-ink-2/70">Session</p>
        <span className={`stencil text-[10px] uppercase tracking-[0.16em] ${tone}`}>{label}</span>
      </div>
      <div className="mt-1.5 flex items-baseline gap-1.5">
        <span className={`stencil text-3xl leading-none ${elapsed ? 'text-ink' : 'text-ink-3'}`}>{elapsed ?? '--:--'}</span>
        <span className="text-[10px] uppercase tracking-[0.08em] text-ink-2">elapsed · {duration} min planned</span>
      </div>
      <p className="stencil mt-2.5 border-t border-ink/15 pt-2 text-[10px] uppercase leading-relaxed tracking-[0.08em] text-ink-2">
        {kindLabel} · {mode} mode
        <br />
        drawn {date}
      </p>
    </div>
  )
}

// Session specification cell — the interview's spec block in the title
// block: target profile, source document state, interview positioning.
function SessionSpec({
  profileName,
  resumeLabel,
  resumeTone,
  positioning,
}: {
  profileName: string
  resumeLabel: string
  resumeTone: 'ok' | 'warn' | 'danger' | 'neutral'
  positioning: string
}) {
  const srcTone = resumeTone === 'ok' ? 'text-draft' : resumeTone === 'danger' ? 'text-redline' : 'text-ink-2'
  return (
    <div className="w-full border border-ink/30 bg-sheet-lit/45 px-4 py-3 sm:w-[17rem]">
      <p className="text-[10px] font-medium uppercase tracking-[0.12em] text-ink-2/70">Session specification</p>
      <dl className="mt-2">
        <div className="flex items-baseline justify-between gap-3 border-t border-ink/10 pt-1.5">
          <dt className="stencil text-[10px] uppercase tracking-[0.12em] text-ink-3">Target</dt>
          <dd className="stencil truncate text-[10px] uppercase tracking-[0.12em] text-ink">{profileName}</dd>
        </div>
        <div className="mt-1.5 flex items-baseline justify-between gap-3 border-t border-ink/10 pt-1.5">
          <dt className="stencil text-[10px] uppercase tracking-[0.12em] text-ink-3">Source</dt>
          <dd className={`stencil text-[10px] uppercase tracking-[0.12em] ${srcTone}`}>{resumeLabel}</dd>
        </div>
        <div className="mt-1.5 flex items-baseline justify-between gap-3 border-t border-ink/10 pt-1.5">
          <dt className="stencil text-[10px] uppercase tracking-[0.12em] text-ink-3">Positioning</dt>
          <dd className="stencil truncate text-[10px] uppercase tracking-[0.12em] text-ink">{positioning}</dd>
        </div>
      </dl>
    </div>
  )
}

// One numbered step of the pre-flight procedure. Numerals carry real
// sequence information here (target → source → configuration → issue).
function PreflightStep({
  index,
  title,
  aside,
  children,
}: {
  index: string
  title: string
  aside?: React.ReactNode
  children: React.ReactNode
}) {
  return (
    <section className="border-t border-ink/10 px-6">
      <header className="flex items-baseline gap-3 pt-4">
        <StencilNum className="text-lg leading-none text-draft">{index}</StencilNum>
        <h2 className="text-[10px] font-medium uppercase tracking-[0.12em] text-ink-2/70">{title}</h2>
        {aside ? <span className="flex-1" /> : null}
        {aside ? <span className="stencil text-[10px] uppercase tracking-[0.12em] text-ink-3">{aside}</span> : null}
      </header>
      <div className="pb-5 pl-9">{children}</div>
    </section>
  )
}

// The issued-operation control: drafting blue, stencil typography, precise
// border, restrained fill. An engineering control, not a SaaS CTA.
function IssueControl({ label, disabled, onClick }: { label: string; disabled: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className="stencil flex w-full items-center justify-between gap-3 border border-draft bg-draft-soft/40 px-4 py-3 text-[12px] font-semibold uppercase tracking-[0.14em] text-draft-2 transition-colors duration-[var(--dur-fast)] hover:bg-draft-soft/70 focus-visible:outline-none focus-visible:shadow-[var(--focus-ring)] disabled:cursor-not-allowed disabled:opacity-45"
    >
      <span>{label}</span>
      <span aria-hidden className="text-draft">→</span>
    </button>
  )
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
  const [elapsed, setElapsed] = useState<string | null>(null)
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

  // Elapsed time is computed from the server-authoritative started_at —
  // a real measurement, never a fabricated counter.
  const startedAt = session.data?.started_at ?? null
  useEffect(() => {
    if (!live || !startedAt) {
      setElapsed(null)
      return
    }
    const started = new Date(startedAt).getTime()
    const fmt = () => {
      const s = Math.max(0, Math.floor((Date.now() - started) / 1000))
      const h = Math.floor(s / 3600)
      const m = Math.floor((s % 3600) / 60)
      const r = s % 60
      return h > 0 ? `${pad2(h)}:${pad2(m)}:${pad2(r)}` : `${pad2(m)}:${pad2(r)}`
    }
    setElapsed(fmt())
    const t = setInterval(() => setElapsed(fmt()), 1000)
    return () => clearInterval(t)
  }, [live, startedAt])

  const answering = actions.answer.isPending
  const resumeDocs = (docs.data ?? []).filter((d) => d.kind === 'resume')
  const jdDocs = (docs.data ?? []).filter((d) => d.kind === 'jd')
  const activeProfile = ctx.data?.profile

  // Question ordinal = interviewer turns actually recorded in the transcript.
  const questionOrdinal = transcript.filter((l) => l.role === 'interviewer').length
  const candidateTurns = transcript.filter((l) => l.role === 'candidate' && !l.partial).length
  const interviewerTurns = questionOrdinal

  const kindLabel = String(session.data?.config?.kind ?? kind).replace(/_/g, ' ')
  const styleLabel = String(session.data?.config?.style ?? style).replace(/_/g, ' ')
  const sessionDuration = Number(session.data?.config?.duration_minutes ?? duration)
  const startedDate = session.data?.started_at
    ? new Date(session.data.started_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })
    : '—'
  const startedTime = session.data?.started_at
    ? new Date(session.data.started_at).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })
    : '—'

  return (
    <Sheet aria-label={ended ? 'Session summary' : live ? 'Live interview field sheet' : 'Interview pre-flight briefing'}>
      {ended ? (
        /* ---------- Completion sheet ---------- */
        <div className="px-6 pb-10 pt-8 sm:px-10">
          <p className="text-[10px] font-medium uppercase tracking-[0.12em] text-ink-2/70">Pramya · Practice · Session {status}</p>
          <div className="mt-4 grid gap-8 lg:grid-cols-[minmax(0,1fr)_auto]">
            <div>
              <h1 className="text-2xl font-semibold tracking-tight text-ink">
                {status === 'completed' ? 'Interview complete' : 'Interview ended'}
              </h1>
              <p className="mt-2 max-w-md text-sm leading-relaxed text-ink-2">
                {status === 'completed'
                  ? 'Every answer was evaluated. Your report connects each question to what you said, what was missing, and what to prepare.'
                  : 'You can start again any time — context is saved per session.'}
              </p>
              <div className="mt-6 flex flex-wrap items-center gap-3">
                {status === 'completed' ? (
                  <Link to={`/interview/${sessionId}/report`}>
                    <Button size="lg">View report →</Button>
                  </Link>
                ) : null}
                <Button variant="secondary" size="lg" onClick={() => setSessionId(null)}>
                  {status === 'completed' ? 'Start another interview' : 'Back to practice'}
                </Button>
              </div>
            </div>
            <div className="w-full border border-ink/30 bg-sheet-lit/45 px-5 py-4 sm:w-72">
              <div className="flex items-baseline justify-between gap-3">
                <p className="text-[10px] font-medium uppercase tracking-[0.12em] text-ink-2/70">Session record</p>
                <span className={`stencil text-[10px] uppercase tracking-[0.16em] ${status === 'completed' ? 'text-draft' : 'text-ink-2'}`}>
                  {status === 'completed' ? 'complete' : 'ended'}
                </span>
              </div>
              <p className="stencil mt-3 border-t border-ink/15 pt-2.5 text-[10px] uppercase leading-relaxed tracking-[0.08em] text-ink-2">
                {kindLabel} · {styleLabel} · {sessionDuration} min
                <br />
                started {startedTime} · drawn {startedDate}
              </p>
            </div>
          </div>
        </div>
      ) : !live ? (
        /* ---------- Pre-flight briefing ---------- */
        <>
          <div className="flex flex-wrap items-start justify-between gap-x-8 gap-y-4 border-b border-ink/25 px-6 pb-4 pt-5">
            <div className="min-w-0">
              <p className="text-[10px] font-medium uppercase tracking-[0.12em] text-ink-2/70">Pramya · Practice · Pre-flight</p>
              <h1 className="mt-1.5 text-xl font-semibold tracking-tight text-ink">Prepare for an interview</h1>
              <p className="mt-1 max-w-xl text-[13px] leading-relaxed text-ink-2">
                Pramya asks you what you actually did, evaluates what you demonstrate, and adapts the next question to your answer.
              </p>
            </div>
            {ctx.data ? (
              <SessionSpec
                profileName={(activeProfile?.name ?? '—').toUpperCase()}
                resumeLabel={`RESUME ${statusOf(ctx.data.resume).label.toUpperCase()}`}
                resumeTone={statusOf(ctx.data.resume).tone}
                positioning={ctx.data.jd ? 'JD INTERVIEW' : 'RESUME-ONLY'}
              />
            ) : null}
          </div>

          {error ? <ErrorState title="Could not start" body={error} className="m-6" /> : null}

          {!ctx.data && !ctx.isLoading ? (
            <div className="px-6 py-6">
              <EmptyState title="Select a profile first" body="Create or choose a career profile — interviews are grounded in its resume and roles." />
            </div>
          ) : null}

          {ctx.data ? (
            <>
              {/* 01 · TARGET */}
              <PreflightStep index="01" title="Target">
                <div className="flex items-start justify-between gap-4 pt-2">
                  <div className="min-w-0">
                    <p className="text-lg font-semibold tracking-tight text-ink">{activeProfile?.name ?? '—'}</p>
                    <p className="mt-0.5 text-[13px] text-ink-2">
                      {[activeProfile?.headline, activeProfile?.seniority_target ? `seniority target · ${activeProfile.seniority_target}` : null]
                        .filter(Boolean)
                        .join(' · ') || 'no profile details'}
                    </p>
                    {activeProfile?.positioning ? <p className="mt-1 text-[12px] text-ink-3">{activeProfile.positioning}</p> : null}
                  </div>
                  {ctx.isLoading ? <Spinner label="Loading" subtle /> : null}
                </div>
              </PreflightStep>

              {/* 02 · SOURCE / POSITIONING */}
              <PreflightStep index="02" title="Source · positioning">
                <div className="grid gap-x-8 gap-y-5 pt-2 sm:grid-cols-2">
                  <div className="min-w-0">
                    <div className="flex items-baseline justify-between gap-3">
                      <p className="text-[10px] font-medium uppercase tracking-[0.12em] text-ink-2/70">Using</p>
                      <DocStatusTag label="status" tone={statusOf(ctx.data.resume).tone} text={statusOf(ctx.data.resume).label} />
                    </div>
                    <p className="mt-1 truncate text-sm font-medium text-ink">{ctx.data.resume?.filename ?? 'No resume'}</p>
                    <p className="text-[11px] text-ink-3">your current resume — what the interviewer knows about you</p>
                    <FieldSelect
                      label="Resume for this interview"
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
                    </FieldSelect>
                  </div>
                  <div className="min-w-0">
                    <div className="flex items-baseline justify-between gap-3">
                      <p className="text-[10px] font-medium uppercase tracking-[0.12em] text-ink-2/70">Against</p>
                      {ctx.data.jd ? (
                        <DocStatusTag label="status" tone={statusOf(ctx.data.jd).tone} text={statusOf(ctx.data.jd).label} />
                      ) : (
                        <DocStatusTag label="status" tone="neutral" text="optional" />
                      )}
                    </div>
                    <p className="mt-1 truncate text-sm font-medium text-ink">{ctx.data.jd?.filename ?? 'Resume-only mode'}</p>
                    <p className="text-[11px] text-ink-3">
                      {ctx.data.jd ? 'the role you are targeting' : 'no JD — questions stay grounded in your resume'}
                    </p>
                    <FieldSelect
                      label="Job description for this interview"
                      value={String(ctx.data.jd?.document_id ?? '')}
                      onChange={(e) => onSelectPreferred('jd', e.target.value ? Number(e.target.value) : null)}
                    >
                      <option value="">No JD — resume-only interview</option>
                      {jdDocs.map((d) => (
                        <option key={d.id} value={d.id}>
                          {d.filename} ({d.status})
                        </option>
                      ))}
                    </FieldSelect>
                  </div>
                </div>
                {ctx.data.missing.includes('resume') ? (
                  <div className="mt-5 border border-redline/40 bg-redline-soft/40 px-3 py-2 text-[12px] leading-relaxed text-redline">
                    This profile has no processed resume. Upload one on the Profile page before starting.
                  </div>
                ) : null}
              </PreflightStep>

              {/* 03 · INTERVIEW CONFIGURATION */}
              <PreflightStep index="03" title="Interview configuration">
                <div className="grid gap-x-8 gap-y-5 pt-2 sm:grid-cols-2">
                  <FieldSelect label="Interview type" value={kind} onChange={(e) => setKind(e.target.value)}>
                    {KINDS.map((k) => (
                      <option key={k.value} value={k.value}>
                        {k.label}
                      </option>
                    ))}
                  </FieldSelect>
                  <FieldSelect
                    label="Interviewer style"
                    value={style}
                    onChange={(e) => setStyle(e.target.value)}
                    hint={STYLES.find((s) => s.value === style)?.hint}
                  >
                    {STYLES.map((s) => (
                      <option key={s.value} value={s.value}>
                        {s.label}
                      </option>
                    ))}
                  </FieldSelect>
                  <FieldSeg
                    label="Duration"
                    ariaLabel="Interview duration"
                    value={String(duration)}
                    onChange={(v) => setDuration(Number(v))}
                    options={DURATION_PRESETS.map((d) => ({ value: String(d), label: `${d} min` }))}
                  />
                  <FieldSeg
                    label="Format"
                    ariaLabel="Interview format"
                    value={mode}
                    onChange={(v) => setMode(v as 'text' | 'voice')}
                    options={[
                      { value: 'voice', label: 'Live voice' },
                      { value: 'text', label: 'Typed' },
                    ]}
                  />
                </div>
              </PreflightStep>

              {/* 04 · ISSUE */}
              <PreflightStep index="04" title="Issue" aside="issued session">
                <p className="stencil pt-2 text-[10px] uppercase tracking-[0.12em] text-ink-2">
                  to be issued · {kind.replace(/_/g, ' ')} · {style.replace(/_/g, ' ')} · {duration} min · {mode === 'voice' ? 'live voice' : 'typed'}
                </p>
                <div className="pt-3">
                  <IssueControl
                    label={create.isPending ? 'Starting…' : mode === 'voice' ? 'Start live voice interview' : 'Start typed interview'}
                    disabled={create.isPending || actions.begin.isPending || !ctxReady}
                    onClick={() => void (mode === 'voice' ? startVoiceInterview() : startInterview())}
                  />
                  <p className="mt-2.5 text-center text-[11px] leading-relaxed text-ink-3">
                    {mode === 'voice'
                      ? 'You hear the interviewer and speak aloud. Interrupt any time; the transcript captures every turn.'
                      : 'Questions adapt to your demonstrated evidence and are evaluated on 13 dimensions.'}
                  </p>
                </div>
              </PreflightStep>
            </>
          ) : (
            <div className="flex items-center gap-2 px-6 py-6">
              <Spinner label="Loading interview context…" subtle />
            </div>
          )}

          {/* Session history — reference ledger (secondary) */}
          <SheetSection
            title="Session history — reference"
            aside={<span className="stencil text-[10px] uppercase tracking-[0.14em] text-ink-2">{sessions.data?.length ?? 0} prior sessions</span>}
          >
            {!sessions.data?.length ? (
              <p className="py-2 text-[13px] text-ink-2">Your past practice interviews will appear here with links to their reports.</p>
            ) : (
              <ol className="thin-scroll max-h-56 overflow-y-auto">
                {sessions.data.slice(0, 10).map((s, i) => (
                  <li key={s.id} className="grid grid-cols-[2rem_minmax(0,1fr)_auto] items-center gap-x-3 border-b border-ink/5 py-1.5">
                    <StencilNum className="text-[11px] leading-none text-ink-3">{pad2(i + 1)}</StencilNum>
                    <div className="flex min-w-0 items-baseline gap-2">
                      <span className="truncate text-[12px] text-ink">{s.kind.replace(/_/g, ' ')}</span>
                      <span className="shrink-0 text-[11px] text-ink-3">
                        {s.started_at ? new Date(s.started_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric' }) : '—'}
                      </span>
                      <span className={`stencil shrink-0 text-[10px] uppercase tracking-[0.1em] ${HISTORY_TONE[s.status] ?? 'text-ink-2'}`}>
                        {s.status}
                      </span>
                    </div>
                    {s.status === 'completed' ? (
                      <Link
                        className="stencil text-[10px] uppercase tracking-[0.1em] text-draft underline underline-offset-2 hover:text-draft-2"
                        to={`/interview/${s.id}/report`}
                      >
                        Report →
                      </Link>
                    ) : null}
                  </li>
                ))}
              </ol>
            )}
          </SheetSection>

          <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-2 border-t border-ink/25 px-6 pb-4 pt-3">
            <p className="stencil text-[10px] uppercase leading-relaxed tracking-[0.1em] text-ink-2">
              profile {activeProfile?.name ?? '—'} · resume {ctx.data ? statusOf(ctx.data.resume).label : '—'} · jd{' '}
              {ctx.data?.jd ? statusOf(ctx.data.jd).label : 'optional'}
              <br />
              drawn {new Date().toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })}
            </p>
          </div>
        </>
      ) : (
        /* ---------- Live field sheet ---------- */
        <>
          {/* Title block — quiet instrument strip */}
          <div className="flex flex-wrap items-start justify-between gap-x-8 gap-y-4 border-b border-ink/25 px-6 pb-4 pt-5">
            <div className="min-w-0">
              <p className="text-[10px] font-medium uppercase tracking-[0.12em] text-ink-2/70">Pramya · Practice · Field sheet</p>
              <h1 className="mt-1.5 text-xl font-semibold tracking-tight text-ink">{kindLabel} interview</h1>
              <p className="mt-1 text-[13px] text-ink-2">
                {activeProfile?.name ?? 'Profile'} · started {startedTime}
              </p>
            </div>
            <SessionCell
              status={status ?? 'created'}
              elapsed={elapsed}
              duration={sessionDuration}
              kindLabel={kindLabel}
              mode={mode}
              date={startedDate}
            />
          </div>

          {error ? <ErrorState title="That didn't work" body={error} className="m-6" /> : null}

          {/* Primary field — the current question */}
          <SheetSection
            title="Current question"
            tone="lit"
            aside={
              currentQuestion ? (
                <span className="stencil flex items-center gap-2 text-[10px] uppercase tracking-[0.14em] text-ink-2">
                  {currentQuestion.difficulty}
                  {currentQuestion.type ? <span className="border border-ink/30 px-1.5 py-0.5">{currentQuestion.type}</span> : null}
                </span>
              ) : undefined
            }
          >
            {currentQuestion ? (
              <div className="max-w-3xl py-2 sm:py-4">
                <div className="flex items-baseline gap-4 sm:gap-5">
                  <StencilNum className="shrink-0 text-4xl leading-none text-draft sm:text-5xl">Q {pad2(questionOrdinal)}</StencilNum>
                  <p className="text-[22px] font-medium leading-[1.6] tracking-[-0.01em] text-ink sm:text-[26px]">{currentQuestion.text}</p>
                </div>
                {provenanceLabel(currentQuestion.source, currentQuestion.sourceRef) ? (
                  <p className="mt-4 text-[12px] text-ink-2">{provenanceLabel(currentQuestion.source, currentQuestion.sourceRef)}</p>
                ) : null}
                {currentQuestion.rationale ? (
                  <details className="mt-3">
                    <summary className="stencil cursor-pointer text-[10px] uppercase tracking-[0.12em] text-ink-3 transition-colors hover:text-ink-2">
                      Why this question
                    </summary>
                    <p className="mt-1.5 max-w-2xl text-[13px] leading-relaxed text-ink-2">{currentQuestion.rationale}</p>
                  </details>
                ) : null}
              </div>
            ) : (
              <div className="flex max-w-3xl flex-col items-start gap-4 py-4">
                <div className="flex items-center gap-3">
                  <StencilNum className="text-4xl leading-none text-ink-3">Q —</StencilNum>
                  <span className="stencil text-[10px] uppercase tracking-[0.14em] text-draft-2">Preparing next question</span>
                </div>
                <LevelCells level={0} className="w-64" />
                <p className="text-[13px] text-ink-2">The interviewer is preparing the next question — hold on.</p>
              </div>
            )}
          </SheetSection>

          {/* Voice / session state instrument */}
          {mode === 'voice' ? (
            <SheetSection
              title="Voice instrument — session state"
              aside={<span className="stencil text-[10px] uppercase tracking-[0.14em] text-ink-2">voice · {kindLabel}</span>}
            >
              <div className="flex flex-wrap items-center gap-1.5 pb-1">
                {VOICE_REGISTER.map((cell) => (
                  <RegisterCell
                    key={cell.key}
                    label={cell.label}
                    active={voiceState === cell.key || (voiceState === 'interrupted' && cell.key === 'listening')}
                    danger={voiceState === 'error' && cell.key === 'error'}
                  />
                ))}
                {voiceState === 'interrupted' ? <RegisterTag label="interrupted" tone="redline" /> : null}
                {voiceState === 'reconnecting' ? <RegisterTag label="reconnecting" tone="redline" /> : null}
                {voiceState === 'cancelled' ? <RegisterTag label="cancelled" tone="ink-2" /> : null}
                {voiceState === 'completed' ? <RegisterTag label="completed" tone="draft" /> : null}
              </div>
              {/* Operating face: turn line, operation label, controls */}
              <div className="mt-3 border border-ink/25 bg-sheet-lit/30 px-4 py-3">
                <TurnLine state={voiceState} />
                <div className="mt-3 flex flex-wrap items-start justify-between gap-x-6 gap-y-3">
                  <div className="min-w-0">
                    <p className={`stencil text-[13px] uppercase leading-none tracking-[0.18em] ${VOICE_OP_TONE[voiceState] ?? 'text-ink-2'}`}>
                      {VOICE_OPERATION[voiceState]?.label ?? 'READY'}
                    </p>
                    <p className="mt-1.5 text-[12px] leading-relaxed text-ink-2">
                      {VOICE_OPERATION[voiceState]?.note ?? VOICE_STATE_META[voiceState]?.blurb ?? 'Connect your microphone to begin.'}
                    </p>
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    {voiceState === 'speaking' ? (
                      <Button variant="danger" size="sm" onClick={() => voiceRef.current?.interrupt()}>
                        Interrupt
                      </Button>
                    ) : null}
                    {voiceState === 'listening' ? (
                      <Button size="sm" onClick={() => voiceRef.current?.doneSpeaking()}>
                        Done speaking
                      </Button>
                    ) : null}
                    {voiceState === 'listening' || voiceState === 'processing' || voiceState === 'speaking' ? (
                      <Button variant="ghost" size="sm" onClick={() => voiceRef.current?.pause()}>
                        Pause
                      </Button>
                    ) : null}
                    {voiceState === 'paused' ? (
                      <Button size="sm" onClick={() => voiceRef.current?.resume()}>
                        Resume
                      </Button>
                    ) : null}
                    {voiceState !== 'cancelled' && voiceState !== 'completed' ? (
                      <Button variant="ghost" size="sm" onClick={() => void endVoice()}>
                        End interview
                      </Button>
                    ) : null}
                  </div>
                </div>
              </div>
            </SheetSection>
          ) : (
            <SheetSection title="Session state" aside={<span className="stencil text-[10px] uppercase tracking-[0.14em] text-ink-2">typed · {kindLabel}</span>}>
              <div className="flex flex-wrap items-center gap-1.5">
                {SESSION_REGISTER.map((cell) => (
                  <RegisterCell key={cell.label} label={cell.label} active={cell.keys.includes(status ?? 'created')} danger={status === 'error'} />
                ))}
              </div>
              <p className="mt-3 text-[13px] leading-relaxed text-ink-2">{SESSION_BLURB[status ?? 'created'] ?? STATE_META[status ?? 'created']?.label}</p>
            </SheetSection>
          )}

          {/* Answer (typed mode) */}
          {mode === 'text' ? (
            <div className="border-b border-ink/15 px-6 pb-5 pt-4">
              <p className="text-[10px] font-medium uppercase tracking-[0.12em] text-ink-2/70">Your answer</p>
              <textarea
                ref={answerRef}
                aria-label="Your answer"
                className="mt-2 min-h-32 w-full resize-y border border-ink/30 bg-sheet px-3 py-2.5 text-sm leading-relaxed text-ink placeholder:text-ink-3 focus:border-draft focus:outline-none focus:shadow-[var(--focus-ring)]"
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
                  <Button variant="ghost" onClick={() => void actions.pause.mutateAsync({ interviewId: sessionId ?? 0, userId: DEFAULT_USER_ID })}>
                    Pause
                  </Button>
                ) : null}
                {status === 'paused' ? (
                  <Button variant="ghost" onClick={() => void actions.resume.mutateAsync({ interviewId: sessionId ?? 0, userId: DEFAULT_USER_ID })}>
                    Resume
                  </Button>
                ) : null}
              </div>
            </div>
          ) : null}

          {/* Record row: transcript (primary record) + run measure */}
          <div className="grid lg:grid-cols-12">
            <SheetSection
              title="Transcript — the interview record"
              tone="flat"
              className="lg:col-span-8 lg:border-r"
              aside={<span className="stencil text-[10px] uppercase tracking-[0.14em] text-ink-2">{candidateTurns} answers · {interviewerTurns} questions</span>}
            >
              {!transcript.length ? (
                <p className="py-2 text-[13px] text-ink-2">The live transcript appears here as the interview unfolds.</p>
              ) : (
                <ol className="thin-scroll max-h-[22rem] overflow-y-auto">
                  {transcript.map((line, i) => {
                    const ghost = line.role === 'candidate' && line.partial
                    return (
                      <li
                        key={i}
                        className={`grid grid-cols-[2.25rem_minmax(0,1fr)_auto] items-baseline gap-x-3 border-b border-ink/5 py-2.5 ${
                          ghost ? 'border-l-2 border-dashed border-draft/60 pl-2.5' : 'border-l-2 border-transparent pl-2.5'
                        }`}
                      >
                        <StencilNum className="text-[11px] leading-none text-ink-3">{pad2(i + 1)}</StencilNum>
                        <div className="min-w-0">
                          <p className={`stencil text-[10px] uppercase tracking-[0.14em] ${line.role === 'interviewer' ? 'text-draft' : ghost ? 'text-ink-3' : 'text-ink-2'}`}>
                            {line.role === 'interviewer' ? 'Interviewer' : 'You'}
                            {ghost ? ' · speaking…' : ''}
                          </p>
                          <p className={`mt-0.5 text-[13px] leading-relaxed ${ghost ? 'italic text-ink-3' : 'text-ink'}`}>{line.text}</p>
                        </div>
                        <span className="hidden shrink-0 text-[10px] uppercase tracking-[0.08em] text-ink-3 sm:block">
                          {line.role === 'interviewer' ? (questionMeta(transcript, i) || 'question') : ghost ? '' : 'recorded'}
                        </span>
                      </li>
                    )
                  })}
                  <div ref={transcriptEndRef} />
                </ol>
              )}
            </SheetSection>

            <SheetSection title="Run measure" tone="shadow" className="lg:col-span-4">
              <div className="border border-ink/30 bg-sheet-lit/45 px-4 py-3">
                <p className="stencil text-[10px] uppercase tracking-[0.14em] text-ink-2">Overall · last answer</p>
                {evaluation != null ? (
                  <>
                    <div className="mt-1.5 flex items-baseline gap-1.5">
                      <span className={`stencil text-4xl leading-none ${evaluation >= 7 ? 'text-draft' : evaluation >= 4 ? 'text-ink' : 'text-redline'}`}>
                        {evaluation.toFixed(1)}
                      </span>
                      <span className="text-xs text-ink-2">/ 10</span>
                    </div>
                    <p className="mt-2 text-[11px] leading-relaxed text-ink-2">the next question adapts to this answer.</p>
                  </>
                ) : (
                  <>
                    <span className="stencil text-4xl leading-none text-ink-3">—</span>
                    <p className="mt-2 text-[11px] leading-relaxed text-ink-2">no measurement yet — each answer is evaluated as you give it.</p>
                  </>
                )}
              </div>
              {lastHint ? (
                <div className="mt-4 border border-dashed border-redline/60 bg-redline-soft/30 px-4 py-3">
                  <p className="stencil text-[10px] uppercase tracking-[0.14em] text-redline">Hint</p>
                  <p className="mt-1.5 text-[13px] leading-relaxed text-ink">{lastHint}</p>
                </div>
              ) : null}
              <p className="stencil mt-4 border-t border-ink/10 pt-2.5 text-[10px] uppercase leading-relaxed tracking-[0.1em] text-ink-2">
                captured · {candidateTurns} answers · {interviewerTurns} questions
                {mode === 'voice' ? <br /> : null}
                {mode === 'voice' ? `mic ${voiceState === 'listening' ? 'open' : 'armed'}` : null}
              </p>
            </SheetSection>
          </div>

          {/* Revision strip */}
          <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-2 border-t border-ink/25 px-6 pb-4 pt-3">
            <p className="stencil text-[10px] uppercase leading-relaxed tracking-[0.1em] text-ink-2">
              drawn {startedDate} · {kindLabel} · {styleLabel} · {sessionDuration} min · {mode}
            </p>
            <div className="flex items-center gap-2">
              <Button
                variant="secondary"
                size="sm"
                onClick={() => void actions.stop.mutateAsync({ interviewId: sessionId ?? 0, userId: DEFAULT_USER_ID })}
              >
                End session
              </Button>
            </div>
          </div>
        </>
      )}
    </Sheet>
  )

  function onSelectPreferred(kind: 'resume' | 'jd', documentId: number | null) {
    if (activeId != null) void setPreferred.mutateAsync({ kind, documentId })
  }
}
