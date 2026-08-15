// Transcript — the interview source record. Every turn in order, with the
// question, the answer, and the evaluation where one exists. An engineering
// log of what was actually said — nothing is reconstructed.

import { Link, useParams } from 'react-router-dom'
import { DEFAULT_USER_ID, useTranscript } from '../hooks/queries'
import { ErrorState, Skeleton } from '../components/ui'
import { Sheet, SheetSection, StencilNum } from '../components/sheet'

// Transcript scoring thresholds (7 / 4) — the transcript's own semantics.
function scoreTone(score: number): string {
  if (score >= 7) return 'text-draft'
  if (score >= 4) return 'text-ink-2'
  return 'text-redline'
}

function pad2(n: number): string {
  return String(n).padStart(2, '0')
}

export function TranscriptPage() {
  const { id } = useParams<{ id: string }>()
  const interviewId = Number(id)
  const transcript = useTranscript(interviewId, DEFAULT_USER_ID, !Number.isNaN(interviewId))

  const turns = transcript.data?.turns ?? null
  const evaluated = turns?.filter((t) => typeof t.evaluation_overall === 'number' && t.evaluation_overall !== null).length ?? 0

  return (
    <Sheet aria-label="Interview transcript record">
      {/* Title block */}
      <div className="flex flex-wrap items-start justify-between gap-x-8 gap-y-4 border-b border-ink/25 px-6 pb-4 pt-5">
        <div className="min-w-0">
          <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-ink-2">Pramya · Interview · Transcript</p>
          <h1 className="mt-1.5 text-xl font-semibold tracking-tight text-ink">Interview record</h1>
          <p className="mt-1 max-w-xl text-[13px] leading-relaxed text-ink-2">
            The durable memory of the session — every question, answer, and evaluation in order.
          </p>
        </div>
        <div className="w-full border border-ink/30 bg-sheet-lit/45 px-4 py-3 sm:w-[17rem]">
          <div className="flex items-baseline justify-between gap-3">
            <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-ink-2">Record state</p>
            <span className={`stencil text-[10px] uppercase tracking-[0.16em] ${turns && turns.length ? 'text-draft' : 'text-ink-3'}`}>
              {turns && turns.length ? 'On record' : 'Empty'}
            </span>
          </div>
          <dl className="mt-2">
            {[
              ['Interview', interviewId != null && !Number.isNaN(interviewId) ? `#${interviewId}` : '—'],
              ['Turns', turns ? `${turns.length} on record` : '—'],
              ['Evaluated', evaluated ? `${evaluated} scored` : '—'],
              ['Order', turns && turns.length ? 'as spoken' : '—'],
            ].map(([label, value]) => (
              <div key={label} className="flex items-baseline justify-between gap-3 border-t border-ink/15 pt-1.5">
                <dt className="stencil text-[10px] uppercase tracking-[0.12em] text-ink-3">{label}</dt>
                <dd className={`stencil truncate text-[10px] uppercase tracking-[0.12em] ${value === '—' ? 'text-ink-3' : 'text-ink-2'}`}>{value}</dd>
              </div>
            ))}
          </dl>
        </div>
      </div>

      {transcript.isLoading ? (
        <div className="space-y-2 px-6 py-8">
          <Skeleton className="h-16" />
          <Skeleton className="h-16" />
          <Skeleton className="h-16" />
        </div>
      ) : null}

      {transcript.isError ? (
        <div className="px-6 py-6">
          <ErrorState
            title="Could not load the transcript"
            body={transcript.error instanceof Error ? transcript.error.message : undefined}
            onRetry={() => transcript.refetch()}
          />
        </div>
      ) : null}

      {!transcript.isLoading && !transcript.isError && turns && turns.length === 0 ? (
        <SheetSection title="Turn record" aside={<span className="stencil text-[10px] uppercase tracking-[0.14em] text-ink-3">no turns</span>}>
          <div className="border border-dashed border-ink/25 px-6 py-10 text-center">
            <p className="stencil text-[12px] uppercase tracking-[0.2em] text-ink-3">Nothing recorded yet</p>
            <div className="mx-auto mt-6 w-full max-w-2xl space-y-2.5" aria-hidden>
              <span className="block h-2.5 w-full border border-dashed border-ink/30" />
              <span className="block h-2.5 w-5/6 border border-dashed border-ink/30" />
              <span className="block h-2.5 w-2/3 border border-dashed border-ink/30" />
            </div>
            <p className="mx-auto mt-4 max-w-md text-[13px] leading-relaxed text-ink-2">
              This session has no turns. Run an interview to build its record.
            </p>
            <Link className="stencil mt-5 inline-block text-[10px] uppercase tracking-[0.1em] text-draft underline underline-offset-2 hover:text-draft-2" to="/history">
              ← History
            </Link>
          </div>
        </SheetSection>
      ) : null}

      {turns && turns.length > 0 ? (
        <SheetSection
          title="Turn record"
          aside={<span className="stencil text-[10px] uppercase tracking-[0.14em] text-ink-2">as recorded · {turns.length} turns</span>}
        >
          <ol>
            {turns.map((turn) => {
              const scored = typeof turn.evaluation_overall === 'number' && turn.evaluation_overall !== null
              return (
                <li key={turn.seq} className="border-b border-ink/10 py-4 last:border-b-0">
                  <div className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1">
                    <p className="stencil flex items-baseline gap-2 text-[10px] uppercase tracking-[0.14em] text-ink-3">
                      <StencilNum className="text-[11px] leading-none text-ink-3">{pad2(turn.seq)}</StencilNum>
                      <span>Turn {turn.seq} · {turn.kind}</span>
                      {turn.hints_used ? (
                        <span className="text-[9px] uppercase tracking-[0.14em] text-ink-3">· {turn.hints_used} hint{turn.hints_used > 1 ? 's' : ''} used</span>
                      ) : null}
                    </p>
                    {scored ? (
                      <StencilNum className={`text-[13px] leading-none ${scoreTone(turn.evaluation_overall as number)}`}>
                        {(turn.evaluation_overall as number).toFixed(1)} / 10
                      </StencilNum>
                    ) : null}
                  </div>
                  {turn.question ? (
                    <p className="mt-2 border-l-2 border-draft/60 pl-3 text-[15px] font-medium leading-relaxed text-ink">{turn.question}</p>
                  ) : null}
                  {turn.answer ? (
                    <div className="mt-2 pl-3">
                      <p className="stencil text-[10px] uppercase tracking-[0.12em] text-ink-3">Your answer</p>
                      <p className="mt-0.5 text-[13px] leading-relaxed text-ink-2">{turn.answer}</p>
                    </div>
                  ) : null}
                </li>
              )
            })}
          </ol>
        </SheetSection>
      ) : null}

      {/* Revision strip */}
      <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-2 border-t border-ink/25 px-6 pb-4 pt-3">
        <p className="stencil text-[10px] uppercase leading-relaxed tracking-[0.1em] text-ink-2">
          interview {interviewId != null && !Number.isNaN(interviewId) ? `#${interviewId}` : '—'} · {turns?.length ?? 0} turns · {evaluated} evaluated
          <br />
          drawn {new Date().toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })}
        </p>
        <p className="stencil text-[10px] uppercase leading-relaxed tracking-[0.1em] text-ink-3">
          source record — the durable memory of the session, in order.
        </p>
      </div>
    </Sheet>
  )
}
