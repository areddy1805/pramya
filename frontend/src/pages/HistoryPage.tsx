// History — the workspace audit record: every practice session, in order,
// with its state and where its record lives. An engineering log, not an
// activity feed. The backend exposes interview sessions only (newest first,
// capped); nothing else is invented.

import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { DEFAULT_USER_ID, useInterviews, useProfiles, useResolvedProfile } from '../hooks/queries'
import { ErrorState, Skeleton } from '../components/ui'
import { Sheet, SheetSection, StencilNum } from '../components/sheet'

// The backend session list endpoint returns at most this many records.
const VIEW_CAP = 50

const KIND_LABELS: Record<string, string> = {
  general: 'General mock',
  resume_deep_dive: 'Resume deep dive',
  job_description: 'JD interview',
  technical: 'Technical',
  behavioral: 'Behavioral',
  project_deep_dive: 'Project deep dive',
  system_design: 'System design',
  coding_reasoning: 'Coding (verbal)',
}

const STATUS_STENCIL: Record<string, { label: string; tone: string }> = {
  completed: { label: 'Completed', tone: 'text-draft' },
  questioning: { label: 'Live', tone: 'text-draft-2' },
  planning: { label: 'Planning', tone: 'text-ink-2' },
  created: { label: 'Created', tone: 'text-ink-2' },
  paused: { label: 'Paused', tone: 'text-ink-2' },
  interrupted: { label: 'Interrupted', tone: 'text-redline' },
  cancelled: { label: 'Cancelled', tone: 'text-ink-3' },
  error: { label: 'Error', tone: 'text-redline' },
}

// Client-side scope groups — derived from the loaded sessions, no backend change.
const SCOPE: Array<{ key: string; label: string; match: (status: string) => boolean }> = [
  { key: 'all', label: 'All statuses', match: () => true },
  { key: 'completed', label: 'Completed', match: (s) => s === 'completed' },
  { key: 'live', label: 'Live', match: (s) => s === 'questioning' || s === 'planning' || s === 'created' },
  { key: 'paused', label: 'Paused · interrupted', match: (s) => s === 'paused' || s === 'interrupted' },
  { key: 'cancelled', label: 'Cancelled', match: (s) => s === 'cancelled' },
  { key: 'error', label: 'Error', match: (s) => s === 'error' },
]

const ROW_GRID = 'grid-cols-[2rem_minmax(0,1fr)] md:grid-cols-[2.25rem_7.5rem_minmax(0,1fr)_6rem_4.5rem_auto]'

function pad2(n: number): string {
  return String(n).padStart(2, '0')
}

function fmtDate(iso: string | null | undefined): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })
}

function fmtTime(iso: string | null | undefined): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })
}

// Elapsed time computed from real started/ended timestamps — never invented.
function fmtDuration(started: string | null | undefined, ended: string | null | undefined): string | null {
  if (!started || !ended) return null
  const s = Math.max(0, Math.floor((new Date(ended).getTime() - new Date(started).getTime()) / 1000))
  if (s < 60) return `${s}s`
  const m = Math.floor(s / 60)
  const r = s % 60
  return `${m}m ${pad2(r)}s`
}

export function HistoryPage() {
  const { activeId } = useResolvedProfile(DEFAULT_USER_ID)
  const profiles = useProfiles(DEFAULT_USER_ID)
  const interviews = useInterviews(DEFAULT_USER_ID, activeId)
  const [scope, setScope] = useState('all')

  const all = interviews.data ?? []
  const rows = useMemo(() => {
    const list = interviews.data ?? []
    return scope === 'all' ? list : list.filter((s) => SCOPE.find((g) => g.key === scope)?.match(s.status) ?? true)
  }, [interviews.data, scope])
  const profileName = profiles.data?.find((p) => p.id === activeId)?.name ?? null
  const firstDate = all.length ? all[all.length - 1].started_at : null
  const lastDate = all.length ? all[0].started_at : null

  return (
    <Sheet aria-label="History record">
      {/* Title block */}
      <div className="flex flex-wrap items-start justify-between gap-x-8 gap-y-4 border-b border-ink/25 px-6 pb-4 pt-5">
        <div className="min-w-0">
          <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-ink-2">Pramya · History · Record</p>
          <h1 className="mt-1.5 text-xl font-semibold tracking-tight text-ink">History</h1>
          <p className="mt-1 max-w-xl text-[13px] leading-relaxed text-ink-2">
            Every practice interview you have run — reports and transcripts stay available here.
          </p>
        </div>
        <div className="w-full border border-ink/30 bg-sheet-lit/45 px-4 py-3 sm:w-[17rem]">
          <div className="flex items-baseline justify-between gap-3">
            <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-ink-2">Record state</p>
            <span className={`stencil text-[10px] uppercase tracking-[0.16em] ${all.length ? 'text-draft' : 'text-ink-3'}`}>
              {all.length ? 'On record' : 'Empty'}
            </span>
          </div>
          <dl className="mt-2">
            {[
              ['Profile', profileName ?? '—'],
              ['Events', all.length ? `${all.length} visible · cap ${VIEW_CAP}` : '—'],
              ['Span', firstDate && lastDate ? `${fmtDate(firstDate)} → ${fmtDate(lastDate)}` : '—'],
              ['Order', all.length ? 'newest first' : '—'],
            ].map(([label, value]) => (
              <div key={label} className="flex items-baseline justify-between gap-3 border-t border-ink/15 pt-1.5">
                <dt className="stencil text-[10px] uppercase tracking-[0.12em] text-ink-3">{label}</dt>
                <dd className={`stencil truncate text-[10px] uppercase tracking-[0.12em] ${value === '—' ? 'text-ink-3' : 'text-ink-2'}`}>{value}</dd>
              </div>
            ))}
          </dl>
        </div>
      </div>

      {/* Scope strip */}
      <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-2 border-b border-ink/15 px-6 py-3">
        <div className="flex flex-wrap items-center gap-3">
          <p className="stencil text-[10px] uppercase tracking-[0.14em] text-ink-2">Scope</p>
          <select
            aria-label="Filter by session status"
            value={scope}
            onChange={(e) => setScope(e.target.value)}
            className="h-9 border border-ink/30 bg-sheet px-3 text-sm text-ink focus:border-draft focus:outline-none focus:shadow-[var(--focus-ring)]"
          >
            {SCOPE.map((g) => (
              <option key={g.key} value={g.key}>
                {g.label}
              </option>
            ))}
          </select>
        </div>
        <p className="stencil text-[10px] uppercase tracking-[0.1em] text-ink-2">
          {rows.length} visible · view cap {VIEW_CAP}
          {scope !== 'all' ? ` · of ${all.length}` : ''}
        </p>
      </div>

      {interviews.isLoading ? (
        <div className="space-y-2 px-6 py-8">
          <Skeleton className="h-12" />
          <Skeleton className="h-12" />
          <Skeleton className="h-12" />
        </div>
      ) : null}

      {interviews.isError ? (
        <div className="px-6 py-6">
          <ErrorState
            title="Could not load history"
            body={interviews.error instanceof Error ? interviews.error.message : undefined}
            onRetry={() => interviews.refetch()}
          />
        </div>
      ) : null}

      {/* Event ledger */}
      {!interviews.isLoading && !interviews.isError ? (
        rows.length ? (
          <SheetSection
            title="Event ledger"
            aside={<span className="stencil text-[10px] uppercase tracking-[0.14em] text-ink-2">report + transcript links per record</span>}
          >
            <div className={`stencil hidden items-center gap-x-3 border-b border-ink/20 px-3 pb-2 pt-1 text-[10px] uppercase leading-none tracking-[0.12em] text-ink-2 md:grid ${ROW_GRID}`}>
              <span>Item</span>
              <span>Date</span>
              <span>Event</span>
              <span>State</span>
              <span>Elapsed</span>
              <span className="text-right">Record</span>
            </div>
            <ol>
              {rows.map((s, i) => {
                const meta = STATUS_STENCIL[s.status] ?? { label: s.status, tone: 'text-ink-2' }
                const kind = KIND_LABELS[s.kind] ?? s.kind
                const mode = typeof s.config?.mode === 'string' ? s.config.mode : null
                const duration = fmtDuration(s.started_at, s.ended_at)
                return (
                  <li key={s.id}>
                    <div className={`group grid w-full items-center gap-x-3 border-b border-ink/10 px-3 py-2 transition-colors hover:bg-draft-soft/20 ${ROW_GRID}`}>
                      <StencilNum className="text-[11px] leading-none text-ink-3">{pad2(i + 1)}</StencilNum>
                      {/* main wrapper: mobile record + desktop event cell */}
                      <div className="min-w-0">
                        <div className="flex items-baseline gap-2 md:hidden">
                          <p className="text-[12px] leading-none text-ink-2">{fmtDate(s.started_at)}</p>
                          <p className="text-[10px] uppercase tracking-[0.08em] text-ink-3">{fmtTime(s.started_at)}</p>
                        </div>
                        <div className="mt-0.5 flex items-center gap-2 md:mt-0">
                          <p className="truncate text-[13px] text-ink">{kind}</p>
                          {mode ? <span className="stencil shrink-0 text-[9px] uppercase tracking-[0.14em] text-ink-3">{mode}</span> : null}
                        </div>
                        <p className="mt-0.5 text-[11px] text-ink-3">session #{s.id}</p>
                        <div className="mt-1 flex items-center gap-2 md:hidden">
                          <span className={`stencil text-[10px] uppercase leading-none tracking-[0.12em] ${meta.tone}`}>{meta.label}</span>
                          {duration ? <span className="text-[10px] text-ink-3">· {duration}</span> : null}
                        </div>
                        <div className="mt-1.5 flex items-center gap-3 md:hidden">
                          {s.status === 'completed' ? (
                            <Link className="stencil text-[10px] uppercase tracking-[0.1em] text-draft underline underline-offset-2 hover:text-draft-2" to={`/interview/${s.id}/report`}>
                              Report
                            </Link>
                          ) : null}
                          <Link className="stencil text-[10px] uppercase tracking-[0.1em] text-draft underline underline-offset-2 hover:text-draft-2" to={`/interview/${s.id}/transcript`}>
                            Transcript
                          </Link>
                        </div>
                      </div>
                      <span className="hidden text-[12px] leading-none text-ink-2 md:block">{fmtDate(s.started_at)}</span>
                      <span className={`stencil hidden text-[10px] uppercase leading-none tracking-[0.12em] md:block ${meta.tone}`}>{meta.label}</span>
                      <span className="hidden text-[11px] leading-none text-ink-2 md:block">{duration ?? '—'}</span>
                      <span className="hidden items-center justify-end gap-3 md:flex">
                        {s.status === 'completed' ? (
                          <Link className="stencil text-[10px] uppercase tracking-[0.1em] text-draft underline underline-offset-2 hover:text-draft-2" to={`/interview/${s.id}/report`}>
                            Report
                          </Link>
                        ) : (
                          <span className="text-[10px] uppercase tracking-[0.1em] text-ink-3">—</span>
                        )}
                        <Link className="stencil text-[10px] uppercase tracking-[0.1em] text-draft underline underline-offset-2 hover:text-draft-2" to={`/interview/${s.id}/transcript`}>
                          Transcript
                        </Link>
                      </span>
                    </div>
                  </li>
                )
              })}
            </ol>
          </SheetSection>
        ) : (
          /* Empty record */
          <SheetSection title="Event ledger" aside={<span className="stencil text-[10px] uppercase tracking-[0.14em] text-ink-3">no events</span>}>
            <div className="border border-dashed border-ink/25 px-6 py-10 text-center">
              <p className="stencil text-[12px] uppercase tracking-[0.2em] text-ink-3">No history recorded</p>
              <div className={`${ROW_GRID} mx-auto mt-6 w-full max-w-2xl gap-x-3 border-b border-dashed border-ink/15 px-3 py-2.5`} aria-hidden>
                <span className="h-2.5 w-5 border border-dashed border-ink/30" />
                <span className="h-2.5 w-16 border border-dashed border-ink/30" />
                <span className="h-2.5 w-40 border border-dashed border-ink/30" />
                <span className="hidden h-2.5 w-14 border border-dashed border-ink/30 md:block" />
                <span className="hidden h-2.5 w-10 border border-dashed border-ink/30 md:block" />
                <span className="hidden h-2.5 w-12 border border-dashed border-ink/30 md:block" />
              </div>
              <p className="mx-auto mt-4 max-w-md text-[13px] leading-relaxed text-ink-2">
                Start a practice interview from the Practice screen and it will appear here.
              </p>
            </div>
          </SheetSection>
        )
      ) : null}

      {/* Revision strip */}
      <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-2 border-t border-ink/25 px-6 pb-4 pt-3">
        <p className="stencil text-[10px] uppercase leading-relaxed tracking-[0.1em] text-ink-2">
          profile {profileName ?? '—'} · {all.length} visible · cap {VIEW_CAP} · newest first
          <br />
          span {firstDate && lastDate ? `${fmtDate(firstDate)} → ${fmtDate(lastDate)}` : '—'} · drawn{' '}
          {new Date().toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })}
        </p>
        <p className="stencil text-[10px] uppercase leading-relaxed tracking-[0.1em] text-ink-3">
          every record is a real session — elapsed computed from started → ended.
        </p>
      </div>
    </Sheet>
  )
}
