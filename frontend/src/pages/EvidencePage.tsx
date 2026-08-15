import { useEffect, useState } from 'react'
import { useEvidence, usePatchEvidence, useProfiles, useReadiness, useResolvedProfile, DEFAULT_USER_ID } from '../hooks/queries'
import { ErrorState, Spinner } from '../components/ui'
import { CoverageHatch, DimensionLine, LevelCells, Sheet, SheetSection, StencilNum, type Provenance } from '../components/sheet'

// Evidence-state meta in sheet grammar: demonstrated = drafting blue
// (strongest), observed = lighter draft, claimed = ink (asserted, not yet
// verified — redline in the detail), inferred/unknown = graphite.
const STATUS_STENCIL: Record<string, { label: string; tone: string; blurb: string }> = {
  demonstrated: { label: 'Demonstrated', tone: 'text-draft', blurb: 'Shown under assessment — strongest signal.' },
  observed: { label: 'Observed', tone: 'text-draft-2', blurb: 'Directly observed during practice.' },
  claimed: { label: 'Claimed', tone: 'text-ink-2', blurb: 'Candidate states this; not yet verified.' },
  inferred: { label: 'Inferred', tone: 'text-ink-3', blurb: 'Derived from other evidence — treat with care.' },
  unknown: { label: 'Unknown', tone: 'text-ink-3', blurb: 'No signal either way.' },
}

// Provenance source kinds that exist in the application (EvidenceSourceKind).
const SOURCE_LABEL: Record<string, string> = {
  resume: 'Resume',
  jd: 'Job description',
  answer: 'Interview answer',
  debrief: 'Debrief',
  correction: 'Manual correction',
  observation: 'Observation',
}

const FILTERS = ['all', 'demonstrated', 'observed', 'claimed', 'inferred', 'unknown']

// The backend evidence list endpoint returns at most this many records
// (repository limit) — the visible count is scoped to it, never presented
// as an authoritative total.
const VIEW_CAP = 200

// Registered ledger columns (desktop) — the dense evidence register.
const ROW_GRID = 'grid-cols-[2rem_minmax(0,1fr)] md:grid-cols-[2.25rem_7rem_minmax(0,1fr)_6.5rem_6rem]'

const ORDER: Array<keyof typeof STATUS_STENCIL> = ['demonstrated', 'observed', 'claimed', 'inferred', 'unknown']

function pad2(n: number): string {
  return String(n).padStart(2, '0')
}

function fmtDate(iso: string | null | undefined): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })
}

// Provenance mapping for the record line: the evidence ladder in line style.
function provenanceOf(status: string): Provenance {
  if (status === 'demonstrated') return 'demonstrated'
  if (status === 'observed') return 'observed'
  return 'claimed'
}

export function EvidencePage() {
  const { activeId } = useResolvedProfile(DEFAULT_USER_ID)
  const profiles = useProfiles(DEFAULT_USER_ID)
  const readiness = useReadiness(DEFAULT_USER_ID, activeId)
  const [status, setStatus] = useState('all')
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const evidence = useEvidence(DEFAULT_USER_ID, activeId, status === 'all' ? undefined : status)
  const counts = useEvidence(DEFAULT_USER_ID, activeId, undefined)
  const patch = usePatchEvidence(DEFAULT_USER_ID, activeId)

  const items = evidence.data ?? []
  const allItems = counts.data ?? []
  const selected = items.find((e) => e.id === selectedId) ?? null

  // Auto-select the first record so the detail region is never an empty void.
  useEffect(() => {
    const list = evidence.data ?? []
    if (list.length > 0 && !list.some((e) => e.id === selectedId)) {
      setSelectedId(list[0].id)
    }
    if (list.length === 0) setSelectedId(null)
  }, [evidence.data, selectedId])

  const profileName = profiles.data?.find((p) => p.id === activeId)?.name ?? null
  const totals = ORDER.map((k) => allItems.filter((e) => e.status === k).length)
  const total = allItems.length
  const cov = readiness.data?.evidence_coverage ?? null
  const conf = readiness.data?.confidence ?? null

  return (
    <Sheet aria-label="Evidence ledger">
      {/* Title block */}
      <div className="flex flex-wrap items-start justify-between gap-x-8 gap-y-4 border-b border-ink/25 px-6 pb-4 pt-5">
        <div className="min-w-0">
          <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-ink-2">Pramya · Evidence · Ledger</p>
          <h1 className="mt-1.5 text-xl font-semibold tracking-tight text-ink">Evidence ledger</h1>
          <p className="mt-1 max-w-xl text-[13px] leading-relaxed text-ink-2">
            Everything the system knows about you, and how it knows it — claims, observations, and demonstrated signals.
          </p>
        </div>
        <div className="w-full border border-ink/30 bg-sheet-lit/45 px-4 py-3 sm:w-[17rem]">
          <div className="flex items-baseline justify-between gap-3">
            <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-ink-2">Ledger state</p>
            <span className={`stencil text-[10px] uppercase tracking-[0.16em] ${total ? 'text-draft' : 'text-ink-3'}`}>
              {total ? 'Recorded' : 'Not assessed'}
            </span>
          </div>
          <dl className="mt-2">
            {ORDER.map((k, i) => (
              <div key={k} className="flex items-baseline justify-between gap-3 border-t border-ink/15 pt-1.5">
                <dt className={`stencil text-[10px] uppercase tracking-[0.12em] ${i === 0 ? 'text-ink-3' : 'text-ink-3'}`}>{STATUS_STENCIL[k].label}</dt>
                <dd className={`stencil text-[10px] uppercase tracking-[0.12em] ${
                  total ? (k === 'claimed' && totals[i] > 0 ? 'text-redline' : STATUS_STENCIL[k].tone) : 'text-ink-3'
                }`}>
                  {total ? totals[i] : '—'}
                </dd>
              </div>
            ))}
          </dl>
          <p className="stencil mt-2.5 border-t border-ink/20 pt-2 text-[10px] uppercase leading-relaxed tracking-[0.08em] text-ink-2">
            cov {cov != null ? `${Math.round(cov * 100)}%` : '—'} · conf {conf != null ? `${Math.round(conf * 100)}%` : '—'}
          </p>
        </div>
      </div>

      {/* Filter strip */}
      <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-2 border-b border-ink/15 px-6 py-3">
        <div className="flex flex-wrap items-center gap-3">
          <p className="stencil text-[10px] uppercase tracking-[0.14em] text-ink-2">Filter</p>
          <select
            aria-label="Filter by evidence status"
            value={status}
            onChange={(e) => setStatus(e.target.value)}
            className="h-9 border border-ink/30 bg-sheet px-3 text-sm text-ink focus:border-draft focus:outline-none focus:shadow-[var(--focus-ring)]"
          >
            {FILTERS.map((f) => (
              <option key={f} value={f}>
                {f === 'all' ? 'All statuses' : STATUS_STENCIL[f].label}
              </option>
            ))}
          </select>
        </div>
        <p className="stencil text-[10px] uppercase tracking-[0.1em] text-ink-2">
          {items.length} visible · view cap {VIEW_CAP}
        </p>
      </div>

      {evidence.isLoading ? (
        <div className="px-6 py-8">
          <Spinner label="Loading evidence…" subtle />
        </div>
      ) : null}
      {evidence.isError ? (
        <div className="px-6 py-6">
          <ErrorState title="Could not load evidence" body={evidence.error instanceof Error ? evidence.error.message : undefined} onRetry={() => evidence.refetch()} />
        </div>
      ) : null}

      {/* Ledger — primary surface */}
      {!evidence.isLoading && !evidence.isError ? (
        items.length ? (
          <SheetSection
            title="Evidence register"
            aside={<span className="stencil text-[10px] uppercase tracking-[0.14em] text-ink-2">select a record for detail</span>}
          >
            <div className={ROW_GRID + ' stencil grid items-center gap-x-3 border-b border-ink/20 px-3 pb-2 pt-1 text-[10px] uppercase leading-none tracking-[0.12em] text-ink-2'}>
              <span>Item</span>
              <span className="hidden md:block">State</span>
              <span>Claim / source</span>
              <span className="hidden md:block">Strength</span>
              <span className="hidden md:block text-right">Date</span>
            </div>
            <ol className="thin-scroll max-h-[26rem] overflow-y-auto">
              {items.map((item, i) => {
                const meta = STATUS_STENCIL[item.status] ?? STATUS_STENCIL.unknown
                const isSel = selected?.id === item.id
                const strength = item.strength
                const src = SOURCE_LABEL[item.source_kind] ?? item.source_kind
                return (
                  <li key={item.id}>
                    <button
                      type="button"
                      aria-current={isSel ? 'true' : undefined}
                      aria-label={`Record ${pad2(i + 1)} — ${meta.label}: ${item.claim.slice(0, 80)}`}
                      onClick={() => setSelectedId(item.id)}
                      className={`group grid w-full ${ROW_GRID} items-center gap-x-3 border-b border-ink/10 px-3 py-2 text-left transition-colors hover:bg-draft-soft/30 focus-visible:outline-none focus-visible:shadow-[var(--focus-ring)] ${
                        isSel ? 'bg-sheet-lit/60' : ''
                      }`}
                    >
                      <StencilNum className="text-[11px] leading-none text-ink-3">{pad2(i + 1)}</StencilNum>
                      <span className={`stencil hidden text-[10px] uppercase leading-none tracking-[0.12em] md:block ${meta.tone}`}>{meta.label}</span>
                      <div className="min-w-0">
                        <div className="flex items-baseline gap-2 md:hidden">
                          <span className={`stencil text-[10px] uppercase leading-none tracking-[0.12em] ${meta.tone}`}>{meta.label}</span>
                          <span className="text-[10px] uppercase tracking-[0.1em] text-ink-3">{src}</span>
                        </div>
                        <p className="truncate text-[13px] text-ink">{item.claim}</p>
                        <p className="truncate text-[11px] text-ink-3">
                          source · {src} · {item.source_ref ?? '—'}
                        </p>
                        <p className="mt-0.5 text-[10px] uppercase tracking-[0.08em] text-ink-3 md:hidden">
                          strength {strength != null ? strength.toFixed(2) : '—'} · {fmtDate(item.created_at)}
                        </p>
                      </div>
                      <span className="hidden md:flex md:items-center">
                        {strength != null ? <CoverageHatch value={strength} /> : <span className="stencil text-[10px] uppercase tracking-[0.12em] text-ink-3">—</span>}
                      </span>
                      <span className="hidden items-center justify-end gap-2 md:flex">
                        <span className="stencil text-[10px] uppercase tracking-[0.1em] text-ink-2">{fmtDate(item.created_at)}</span>
                        <span className="stencil text-[10px] uppercase tracking-[0.1em] text-draft opacity-0 transition-opacity group-hover:opacity-100 group-focus-visible:opacity-100">
                          → detail
                        </span>
                      </span>
                    </button>
                  </li>
                )
              })}
            </ol>
          </SheetSection>
        ) : (
          /* Empty ledger — legitimate absence, ghost-drawn */
          <SheetSection title="Evidence register" aside={<span className="stencil text-[10px] uppercase tracking-[0.14em] text-ink-3">no records</span>}>
            <div className="border border-dashed border-ink/25">
              <div className={ROW_GRID + ' stencil grid items-center gap-x-3 border-b border-dashed border-ink/15 px-3 py-2.5 text-[10px] uppercase leading-none tracking-[0.12em] text-ink-3'}>
                <span>Item</span>
                <span className="hidden md:block">State</span>
                <span>Claim / source</span>
                <span className="hidden md:block">Strength</span>
                <span className="hidden md:block text-right">Date</span>
              </div>
              <div className="px-6 py-10 text-center">
                <p className="stencil text-[12px] uppercase tracking-[0.2em] text-ink-3">No evidence recorded</p>
                <LevelCells level={0} className="mx-auto mt-4 w-64" />
                <p className="mx-auto mt-4 max-w-md text-[13px] leading-relaxed text-ink-2">
                  Upload a resume and run extraction in Profile &amp; Role to seed the ledger with the candidate&apos;s claims. Practice
                  interviews add observed and demonstrated signals.
                </p>
              </div>
            </div>
          </SheetSection>
        )
      ) : null}

      {/* Selected record — subordinate detail */}
      <SheetSection
        title="Selected record"
        tone="shadow"
        aside={
          selected ? (
            <span className={`stencil text-[10px] uppercase tracking-[0.14em] ${STATUS_STENCIL[selected.status]?.tone ?? 'text-ink-2'}`}>
              {STATUS_STENCIL[selected.status]?.label ?? selected.status}
            </span>
          ) : undefined
        }
      >
        {selected ? (
          <div className="grid gap-x-8 gap-y-4 lg:grid-cols-12">
            <div className="min-w-0 lg:col-span-7">
              <div className="flex items-baseline gap-3">
                <StencilNum className="text-[11px] leading-none text-ink-3">
                  {pad2(items.findIndex((e) => e.id === selected.id) + 1)}
                </StencilNum>
                <p className="text-[14px] font-medium leading-relaxed text-ink">{selected.claim}</p>
              </div>
              <div className="mt-3">
                <DimensionLine style={provenanceOf(selected.status)} />
                <p className="stencil mt-1 text-[10px] uppercase tracking-[0.12em] text-ink-2">
                  {provenanceOf(selected.status) === 'demonstrated' ? 'Demonstrated — shown under assessment' : provenanceOf(selected.status) === 'observed' ? 'Observed — directly seen during practice' : 'Claimed — asserted, not yet verified'}
                </p>
              </div>
              {selected.status === 'claimed' || selected.status === 'inferred' || selected.status === 'unknown' ? (
                <div className="mt-3 border border-dashed border-redline/50 bg-redline-soft/30 px-3 py-2.5">
                  <p className="stencil text-[10px] uppercase tracking-[0.14em] text-redline">Not yet demonstrated</p>
                  <div className="mt-2 flex items-center gap-3">
                    <LevelCells level={0} className="w-40" />
                    <p className="min-w-0 text-[12px] leading-relaxed text-ink-2">
                      {STATUS_STENCIL[selected.status]?.blurb ?? 'No signal either way.'}
                    </p>
                  </div>
                </div>
              ) : null}
            </div>
            <div className="min-w-0 lg:col-span-5">
              <dl className="stencil text-[10px] uppercase tracking-[0.1em]">
                <div className="flex items-baseline justify-between gap-4 border-t border-ink/15 pt-1.5">
                  <dt className="text-ink-3">Source</dt>
                  <dd className="truncate text-ink-2">
                    {SOURCE_LABEL[selected.source_kind] ?? selected.source_kind} · {selected.source_ref ?? '—'}
                  </dd>
                </div>
                <div className="mt-1.5 flex items-baseline justify-between gap-4 border-t border-ink/15 pt-1.5">
                  <dt className="text-ink-3">Competency</dt>
                  <dd className="text-ink-2">{selected.competency_id ?? '—'}</dd>
                </div>
                <div className="mt-1.5 flex items-baseline justify-between gap-4 border-t border-ink/15 pt-1.5">
                  <dt className="text-ink-3">Strength</dt>
                  <dd className="text-ink-2">{selected.strength != null ? `${selected.strength.toFixed(2)} / 1.00` : '—'}</dd>
                </div>
                <div className="mt-1.5 flex items-baseline justify-between gap-4 border-t border-ink/15 pt-1.5">
                  <dt className="text-ink-3">Recorded</dt>
                  <dd className="text-ink-2">{fmtDate(selected.created_at)}</dd>
                </div>
                <div className="mt-1.5 flex items-baseline justify-between gap-4 border-t border-ink/15 pt-1.5">
                  <dt className="text-ink-3">Notes</dt>
                  <dd className="text-ink-2">{selected.notes ?? '—'}</dd>
                </div>
              </dl>
              {selected.status !== 'demonstrated' ? (
                <div className="mt-3 border-t border-ink/15 pt-2.5">
                  <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-ink-2">Correction · manual override</p>
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {(['demonstrated', 'observed', 'claimed', 'inferred'] as const).map((target) => (
                      <button
                        key={target}
                        type="button"
                        disabled={patch.isPending || selected.status === target}
                        onClick={() => patch.mutate({ evidenceId: selected.id, patch: { status: target } })}
                        className={`stencil border px-2.5 py-1 text-[10px] uppercase tracking-[0.12em] transition-colors disabled:cursor-not-allowed disabled:opacity-40 ${
                          selected.status === target
                            ? 'border-draft bg-draft text-sheet'
                            : 'border-ink/30 text-ink-2 hover:border-draft hover:text-draft'
                        }`}
                      >
                        {STATUS_STENCIL[target].label}
                      </button>
                    ))}
                  </div>
                  <p className="mt-2 text-[11px] leading-relaxed text-ink-3">
                    Corrections are recorded under the &quot;correction&quot; source kind and flow into readiness on the next computation.
                  </p>
                </div>
              ) : null}
            </div>
          </div>
        ) : (
          <div className="py-2">
            <p className="text-[13px] text-ink-3">{items.length ? 'Select a ledger record to inspect it.' : 'No record selected.'}</p>
          </div>
        )}
      </SheetSection>

      {/* Revision strip */}
      <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-2 border-t border-ink/25 px-6 pb-4 pt-3">
        <p className="stencil text-[10px] uppercase leading-relaxed tracking-[0.1em] text-ink-2">
          profile {profileName ?? '—'} · {total} visible · view cap {VIEW_CAP} · filter {status}
          <br />
          drawn {new Date().toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })}
        </p>
        <p className="stencil text-[10px] uppercase leading-relaxed tracking-[0.1em] text-ink-3">
          claimed rows are assertions — practice moves them toward observed.
        </p>
      </div>
    </Sheet>
  )
}
