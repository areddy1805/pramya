import { useState } from 'react'
import { useEvidence, usePatchEvidence, useResolvedProfile, DEFAULT_USER_ID } from '../hooks/queries'
import { EmptyState, ErrorState, Pill, Select, Spinner, Surface } from '../components/ui'

const STATUS_META: Record<string, { label: string; tone: 'neutral' | 'ok' | 'warn' | 'danger' | 'accent'; blurb: string }> = {
  demonstrated: { label: 'Demonstrated', tone: 'ok', blurb: 'Shown under assessment — strongest signal.' },
  observed: { label: 'Observed', tone: 'accent', blurb: 'Directly observed during practice.' },
  claimed: { label: 'Claimed', tone: 'warn', blurb: 'Candidate states this; not yet verified.' },
  inferred: { label: 'Inferred', tone: 'neutral', blurb: 'Derived from other evidence — treat with care.' },
  unknown: { label: 'Unknown', tone: 'neutral', blurb: 'No signal either way.' },
}

const FILTERS = ['all', 'demonstrated', 'observed', 'claimed', 'inferred', 'unknown']

export function EvidencePage() {
  const { activeId } = useResolvedProfile(DEFAULT_USER_ID)
  const [status, setStatus] = useState('all')
  const evidence = useEvidence(DEFAULT_USER_ID, activeId, status === 'all' ? undefined : status)
  const patch = usePatchEvidence(DEFAULT_USER_ID, activeId)

  const items = evidence.data ?? []

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Evidence ledger</h1>
        <p className="mt-1 text-sm text-fg-2">
          Everything the system knows about you, and how it knows it — claims, observations, and demonstrated signals.
        </p>
      </header>

      <div className="flex flex-wrap items-center gap-3">
        <Select
          aria-label="Filter by evidence status"
          className="w-auto"
          value={status}
          onChange={(e) => setStatus(e.target.value)}
        >
          {FILTERS.map((f) => (
            <option key={f} value={f}>
              {f === 'all' ? 'All statuses' : STATUS_META[f].label}
            </option>
          ))}
        </Select>
        <p className="text-xs text-fg-3">{items.length} records</p>
      </div>

      {evidence.isLoading ? <Spinner label="Loading evidence…" /> : null}
      {evidence.isError ? (
        <ErrorState title="Could not load evidence" body={evidence.error instanceof Error ? evidence.error.message : undefined} onRetry={() => evidence.refetch()} />
      ) : null}

      {!evidence.isLoading && !items.length ? (
        <EmptyState
         
          title="No evidence yet"
          body="Upload a resume and run extraction in Profile & Role to seed the ledger with the candidate's claims. Practice interviews add observed and demonstrated signals."
        />
      ) : null}

      {items.length ? (
        <div className="space-y-3">
          {items.map((item) => {
            const meta = STATUS_META[item.status] ?? STATUS_META.unknown
            return (
              <Surface key={item.id} className="p-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0 flex-1">
                    <p className="text-sm leading-relaxed text-fg">{item.claim}</p>
                    <p className="mt-1.5 text-xs text-fg-3">
                      {item.source_kind} · {item.source_ref ?? '—'}
                      {item.competency_id ? ` · competency #${item.competency_id}` : ''}
                    </p>
                  </div>
                  <Pill tone={meta.tone}>{meta.label}</Pill>
                </div>
                <p className="mt-2 text-xs text-fg-3">{meta.blurb}</p>
                {item.status !== 'demonstrated' ? (
                  <div className="mt-3 flex flex-wrap items-center gap-2 border-t border-line pt-3">
                    <p className="text-xs font-medium text-fg-2">Correction:</p>
                    {(['demonstrated', 'observed', 'claimed', 'inferred'] as const).map((target) => (
                      <button
                        key={target}
                        className={`rounded-md px-2 py-1 text-xs font-medium transition-colors ${
                          item.status === target ? 'bg-accent-600 text-white' : 'bg-track text-fg-2 hover:bg-track'
                        }`}
                        onClick={() => patch.mutate({ evidenceId: item.id, patch: { status: target } })}
                      >
                        {STATUS_META[target].label}
                      </button>
                    ))}
                  </div>
                ) : null}
              </Surface>
            )
          })}
        </div>
      ) : null}
    </div>
  )
}
