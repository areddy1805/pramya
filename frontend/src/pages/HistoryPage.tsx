// History — the workspace audit record: every practice session, in order,
// with its state and where its record lives. An engineering log, not an
// activity feed. The backend exposes interview sessions only (newest first,
// capped); nothing else is invented.

import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { DEFAULT_USER_ID, useInterviews, useInterviewsCount, useProfiles, useResolvedProfile } from '../hooks/queries'
import { ErrorState, Skeleton } from '../components/ui'
import { Sheet, SheetSection, StencilNum } from '../components/sheet'
import type { InterviewSession } from '../lib/types'

// Page size for the session ledger — the backend list endpoint defaults to
// this per page; older records are reachable via offset pagination.
const VIEW_CAP = 50

// Client-side scope groups map to server-side status filters, so scoping
// applies across ALL history, never just the loaded page.
const SCOPE: Array<{ key: string; label: string; statuses: string[] | null }> = [
  { key: 'all', label: 'All statuses', statuses: null },
  { key: 'completed', label: 'Completed', statuses: ['completed'] },
  { key: 'live', label: 'Live', statuses: ['questioning', 'planning', 'created'] },
  { key: 'paused', label: 'Paused · interrupted', statuses: ['paused', 'interrupted'] },
  { key: 'cancelled', label: 'Cancelled', statuses: ['cancelled'] },
  { key: 'error', label: 'Error', statuses: ['error'] },
]

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
  const [scope, setScope] = useState('all')
  const [offset, setOffset] = useState(0)
  const [pages, setPages] = useState<InterviewSession[]>([])

  const statuses = SCOPE.find((g) => g.key === scope)?.statuses ?? null
  const pageQuery = useInterviews(DEFAULT_USER_ID, activeId, {
    limit: VIEW_CAP,
    offset,
    statuses: statuses ?? undefined,
  })
  const countQuery = useInterviewsCount(DEFAULT_USER_ID, activeId, statuses ?? undefined)

  // Reset pagination when the workspace or scope changes.
  useEffect(() => {
    setPages([])
    setOffset(0)
  }, [scope, activeId])

  // Append each fetched page, deduped by id (newest-first, pages are
  // contiguous desc). Stale rows from a previous scope are filtered on
  // render, never trusted.
  useEffect(() => {
    const page = pageQuery.data ?? []
    setPages((prev) => {
      const seen = new Set(prev.map((s) => s.id))
      return [...prev, ...page.filter((s) => !seen.has(s.id))]
    })
  }, [pageQuery.data])

  const rows = useMemo(
    () => (statuses ? pages.filter((s) => statuses.includes(s.status)) : pages),
    [pages, statuses],
  )
  const total = countQuery.data?.total ?? null
  const lastPageFull = (pageQuery.data?.length ?? 0) === VIEW_CAP
  const hasMore = total != null ? rows.length < total : lastPageFull
  const initialLoading = pageQuery.isLoading && rows.length === 0
  const loadingMore = pageQuery.isFetching && rows.length > 0
  const all = rows
  const profileName = profiles.data?.find((p) => p.id === activeId)?.name ?? null
  const firstDate = all.length ? all[all.length - 1].started_at : null
  const lastDate = all.length ? all[0].started_at : null
  const shownLabel =
    total != null ? `1–${all.length} of ${total}` : all.length ? `${all.length} shown · more available` : '0 shown'

  return (
    <Sheet aria-label="History record">
      {/* Title block */}
      <div className="flex flex-wrap items-start justify-between gap-x-8 gap-y-4 border-b border-ink/25 px-6 pb-4 pt-5">
        <div className="min-w-0">
          <p className="text-[10px] font-medium uppercase tracking-[0.12em] text-ink-2/70">Pramya · History · Record</p>
          <h1 className="mt-1.5 text-xl font-semibold tracking-tight text-ink">History</h1>
          <p className="mt-1 max-w-xl text-[13px] leading-relaxed text-ink-2">
            Every practice interview you have run — reports and transcripts stay available here.
          </p>
        </div>
        <div className="w-full border border-ink/30 bg-sheet-lit/45 px-4 py-3 sm:w-[17rem]">
          <div className="flex items-baseline justify-between gap-3">
            <p className="text-[10px] font-medium uppercase tracking-[0.12em] text-ink-2/70">Record state</p>
            <span className={`stencil text-[10px] uppercase tracking-[0.16em] ${all.length ? 'text-draft' : 'text-ink-3'}`}>
              {all.length ? 'On record' : 'Empty'}
            </span>
          </div>
          <dl className="mt-2">
            {[
              ['Profile', profileName ?? '—'],
              ['Events', total != null ? `${total} on record` : all.length ? `${all.length} shown` : '—'],
              ['Span', firstDate && lastDate ? `${fmtDate(firstDate)} → ${fmtDate(lastDate)}` : '—'],
              ['Order', all.length ? 'newest first' : '—'],
            ].map(([label, value]) => (
              <div key={label} className="flex items-baseline justify-between gap-3 border-t border-ink/10 pt-1.5">
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
          {shownLabel} · view cap {VIEW_CAP}
          {scope !== 'all' ? ` · ${SCOPE.find((g) => g.key === scope)?.label.toLowerCase() ?? scope}` : ''}
        </p>
      </div>

      {initialLoading ? (
        <div className="space-y-2 px-6 py-8">
          <Skeleton className="h-12" />
          <Skeleton className="h-12" />
          <Skeleton className="h-12" />
        </div>
      ) : null}

      {pageQuery.isError || countQuery.isError ? (
        <div className="px-6 py-6">
          <ErrorState
            title="Could not load history"
            body={
              (pageQuery.error instanceof Error ? pageQuery.error.message : undefined) ??
              (countQuery.error instanceof Error ? countQuery.error.message : undefined)
            }
            onRetry={() => {
              void pageQuery.refetch()
              void countQuery.refetch()
            }}
          />
        </div>
      ) : null}

      {/* Event ledger */}
      {!initialLoading && !pageQuery.isError && !countQuery.isError ? (
        rows.length ? (
          <SheetSection
            title="Event ledger"
            aside={<span className="stencil text-[10px] uppercase tracking-[0.14em] text-ink-2">report + transcript links per record</span>}
          >
            <div className={`stencil hidden items-center gap-x-3 border-b border-ink/15 px-3 pb-2 pt-1 text-[10px] uppercase leading-none tracking-[0.12em] text-ink-2 md:grid ${ROW_GRID}`}>
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
                    <div className={`group grid w-full items-center gap-x-3 border-b border-ink/5 px-3 py-2 transition-colors hover:bg-draft-soft/20 ${ROW_GRID}`}>
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
            {/* Pagination footer */}
            <div className="mt-3 flex flex-wrap items-center justify-between gap-x-6 gap-y-2 border-t border-ink/10 pt-3">
              <span className="stencil text-[10px] uppercase tracking-[0.1em] text-ink-3">
                {hasMore ? 'more history available' : 'end of history — no older records'}
              </span>
              <div className="flex items-center gap-2">
                {loadingMore ? <Skeleton className="h-4 w-24" /> : null}
                {hasMore ? (
                  <button
                    type="button"
                    onClick={() => setOffset((o) => o + VIEW_CAP)}
                    disabled={loadingMore}
                    className="stencil flex h-8 items-center justify-between gap-3 border border-draft bg-draft-soft/40 px-3 text-[10px] font-semibold uppercase tracking-[0.14em] text-draft-2 transition-colors hover:bg-draft-soft/70 focus-visible:outline-none focus-visible:shadow-[var(--focus-ring)] disabled:cursor-not-allowed disabled:opacity-45"
                  >
                    <span>Load older</span>
                    <span aria-hidden>↓</span>
                  </button>
                ) : null}
              </div>
            </div>
          </SheetSection>
        ) : (
          /* Empty record */
          <SheetSection title="Event ledger" aside={<span className="stencil text-[10px] uppercase tracking-[0.14em] text-ink-3">no events</span>}>
            <div className="border border-dashed border-ink/25 px-6 py-10 text-center">
              <p className="stencil text-[12px] uppercase tracking-[0.2em] text-ink-3">
                {scope !== 'all' ? 'No sessions match this scope' : 'No history recorded'}
              </p>
              <div className={`${ROW_GRID} mx-auto mt-6 w-full max-w-2xl gap-x-3 border-b border-dashed border-ink/15 px-3 py-2.5`} aria-hidden>
                <span className="h-2.5 w-5 border border-dashed border-ink/30" />
                <span className="h-2.5 w-16 border border-dashed border-ink/30" />
                <span className="h-2.5 w-40 border border-dashed border-ink/30" />
                <span className="hidden h-2.5 w-14 border border-dashed border-ink/30 md:block" />
                <span className="hidden h-2.5 w-10 border border-dashed border-ink/30 md:block" />
                <span className="hidden h-2.5 w-12 border border-dashed border-ink/30 md:block" />
              </div>
              <p className="mx-auto mt-4 max-w-md text-[13px] leading-relaxed text-ink-2">
                {scope !== 'all'
                  ? 'Try a wider scope — no sessions carry this status on record.'
                  : 'Start a practice interview from the Practice screen and it will appear here.'}
              </p>
            </div>
          </SheetSection>
        )
      ) : null}

      {/* Revision strip */}
      <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-2 border-t border-ink/25 px-6 pb-4 pt-3">
        <p className="stencil text-[10px] uppercase leading-relaxed tracking-[0.1em] text-ink-2">
          profile {profileName ?? '—'} · {total != null ? `${total} on record` : `${all.length} shown`} · {shownLabel} · newest first
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
