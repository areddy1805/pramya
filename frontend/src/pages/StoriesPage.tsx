// Stories — the evidence story library. Reusable STAR records mapped to
// competencies, ready for behavioral interviews. Each story is stored as
// authored; usage counts and coverage come from the backend, never guessed.

import { useState } from 'react'
import { useCreateStory, useStories, useProfiles, useResolvedProfile, DEFAULT_USER_ID } from '../hooks/queries'
import { Button, ErrorState, Skeleton } from '../components/ui'
import { Sheet, SheetSection, StencilNum } from '../components/sheet'

const FIELDS: { key: string; label: string; hint: string }[] = [
  { key: 'situation', label: 'Situation', hint: 'Context — where and when.' },
  { key: 'task', label: 'Task', hint: 'What you were responsible for.' },
  { key: 'action', label: 'Action', hint: 'What you actually did.' },
  { key: 'result', label: 'Result', hint: 'What happened as a result.' },
  { key: 'metrics', label: 'Metrics', hint: 'Numbers that prove impact.' },
  { key: 'conflict', label: 'Conflict', hint: 'Obstacles or tensions.' },
  { key: 'learning', label: 'Learning', hint: 'What you took away.' },
  { key: 'strength', label: 'Strength', hint: 'The competency this story demonstrates.' },
]

const taCls =
  'w-full resize-y border border-ink/30 bg-sheet px-3 py-2.5 text-sm leading-relaxed text-ink placeholder:text-ink-3 focus:border-draft focus:outline-none focus:shadow-[var(--focus-ring)]'

function pad2(n: number): string {
  return String(n).padStart(2, '0')
}

export function StoriesPage() {
  const stories = useStories(DEFAULT_USER_ID)
  const createStory = useCreateStory()
  const { activeId } = useResolvedProfile(DEFAULT_USER_ID)
  const profiles = useProfiles(DEFAULT_USER_ID)
  const [form, setForm] = useState<Record<string, string>>({})

  const filled = Object.values(form).some((v) => v.trim())

  async function save() {
    await createStory.mutateAsync({ user_id: DEFAULT_USER_ID, ...form })
    setForm({})
  }

  const data = stories.data ?? []
  const totalUsage = data.reduce((n, s) => n + (s.usage_count ?? 0), 0)
  const mapped = data.filter((s) => Boolean(s.strength)).length
  const profileName = profiles.data?.find((p) => p.id === activeId)?.name ?? null

  return (
    <Sheet aria-label="Evidence story library">
      {/* Title block */}
      <div className="flex flex-wrap items-start justify-between gap-x-8 gap-y-4 border-b border-ink/25 px-6 pb-4 pt-5">
        <div className="min-w-0">
          <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-ink-2">Pramya · Stories · Library</p>
          <h1 className="mt-1.5 text-xl font-semibold tracking-tight text-ink">Story bank</h1>
          <p className="mt-1 max-w-xl text-[13px] leading-relaxed text-ink-2">
            Your reusable evidence in STAR form — mapped to competencies, ready for behavioral interviews.
          </p>
        </div>
        <div className="w-full border border-ink/30 bg-sheet-lit/45 px-4 py-3 sm:w-[17rem]">
          <div className="flex items-baseline justify-between gap-3">
            <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-ink-2">Library state</p>
            <span className={`stencil text-[10px] uppercase tracking-[0.16em] ${data.length ? 'text-draft' : 'text-ink-3'}`}>
              {data.length ? 'On record' : 'Empty'}
            </span>
          </div>
          <dl className="mt-2">
            {[
              ['Profile', profileName ?? '—'],
              ['Stories', data.length ? `${data.length} on record` : '—'],
              ['Mapped', data.length ? `${mapped} to a strength` : '—'],
              ['Usage', totalUsage ? `${totalUsage} total` : '—'],
            ].map(([label, value]) => (
              <div key={label} className="flex items-baseline justify-between gap-3 border-t border-ink/15 pt-1.5">
                <dt className="stencil text-[10px] uppercase tracking-[0.12em] text-ink-3">{label}</dt>
                <dd className={`stencil truncate text-[10px] uppercase tracking-[0.12em] ${value === '—' ? 'text-ink-3' : 'text-ink-2'}`}>{value}</dd>
              </div>
            ))}
          </dl>
        </div>
      </div>

      {/* 01 · ADD A STORY */}
      <SheetSection
        title="Add a story"
        tone="lit"
        aside={<span className="stencil text-[10px] uppercase tracking-[0.14em] text-ink-2">STAR structure</span>}
      >
        <div className="grid gap-x-6 gap-y-4 sm:grid-cols-2">
          {FIELDS.map((f) => (
            <label key={f.key} className="block">
              <span className="stencil block pb-1.5 text-[10px] uppercase tracking-[0.12em] text-ink-3">
                {f.label} <span className="text-ink-3/70 normal-case tracking-normal">— {f.hint}</span>
              </span>
              <textarea
                className={`${taCls} min-h-16`}
                value={form[f.key] ?? ''}
                onChange={(e) => setForm((prev) => ({ ...prev, [f.key]: e.target.value }))}
              />
            </label>
          ))}
        </div>
        <div className="mt-4">
          <Button onClick={() => void save()} disabled={!filled || createStory.isPending}>
            {createStory.isPending ? 'Saving…' : 'Save story'}
          </Button>
        </div>
      </SheetSection>

      {/* 02 · SAVED STORIES */}
      {stories.isLoading ? (
        <div className="space-y-2 px-6 py-6">
          <Skeleton className="h-16" />
          <Skeleton className="h-16" />
        </div>
      ) : stories.isError ? (
        <div className="px-6 py-6">
          <ErrorState
            title="Could not load stories"
            body={stories.error instanceof Error ? stories.error.message : undefined}
            onRetry={() => stories.refetch()}
          />
        </div>
      ) : data.length === 0 ? (
        <SheetSection title="Saved stories" aside={<span className="stencil text-[10px] uppercase tracking-[0.14em] text-ink-3">no stories</span>}>
          <div className="border border-dashed border-ink/25 px-6 py-10 text-center">
            <p className="stencil text-[12px] uppercase tracking-[0.2em] text-ink-3">Your story bank is empty</p>
            <div className="mx-auto mt-6 grid w-full max-w-xl grid-cols-2 gap-2.5" aria-hidden>
              <span className="block h-2.5 w-full border border-dashed border-ink/30" />
              <span className="block h-2.5 w-4/5 border border-dashed border-ink/30" />
              <span className="block h-2.5 w-3/5 border border-dashed border-ink/30" />
              <span className="block h-2.5 w-full border border-dashed border-ink/30" />
            </div>
            <p className="mx-auto mt-4 max-w-md text-[13px] leading-relaxed text-ink-2">
              Add one STAR story above. During behavioral interviews, the interviewer can ground questions in what you've actually done.
            </p>
          </div>
        </SheetSection>
      ) : (
        <SheetSection
          title="Saved stories"
          aside={<span className="stencil text-[10px] uppercase tracking-[0.14em] text-ink-2">{data.length} stories on record</span>}
        >
          <ol>
            {data.map((story, i) => (
              <li key={story.id} className="border-b border-ink/10 py-4 last:border-b-0">
                <div className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-1">
                  <p className="flex items-baseline gap-2.5">
                    <StencilNum className="text-[11px] leading-none text-ink-3">{pad2(i + 1)}</StencilNum>
                    <span className="stencil text-[10px] uppercase tracking-[0.14em] text-ink-3">story #{story.id}</span>
                  </p>
                  <span className="stencil shrink-0 text-[10px] uppercase tracking-[0.12em] text-ink-3">used {story.usage_count ?? 0}×</span>
                </div>
                <div className="mt-2.5 grid gap-x-10 gap-y-2.5 sm:grid-cols-2">
                  {story.situation ? (
                    <p className="text-[13px] leading-relaxed text-ink">
                      <span className="stencil mr-2 text-[10px] uppercase tracking-[0.12em] text-draft">S</span>
                      {story.situation}
                    </p>
                  ) : null}
                  {story.task ? (
                    <p className="text-[13px] leading-relaxed text-ink">
                      <span className="stencil mr-2 text-[10px] uppercase tracking-[0.12em] text-draft">T</span>
                      {story.task}
                    </p>
                  ) : null}
                  {story.action ? (
                    <p className="text-[13px] leading-relaxed text-ink">
                      <span className="stencil mr-2 text-[10px] uppercase tracking-[0.12em] text-draft">A</span>
                      {story.action}
                    </p>
                  ) : null}
                  {story.result ? (
                    <p className="text-[13px] leading-relaxed text-ink">
                      <span className="stencil mr-2 text-[10px] uppercase tracking-[0.12em] text-draft">R</span>
                      {story.result}
                    </p>
                  ) : null}
                </div>
                {(story.metrics || story.strength || story.conflict || story.learning) ? (
                  <p className="stencil mt-2.5 flex flex-wrap items-center gap-x-4 gap-y-1 text-[10px] uppercase leading-relaxed tracking-[0.1em] text-ink-3">
                    {story.metrics ? <span className="text-ink-2">metrics · {story.metrics}</span> : null}
                    {story.strength ? <span className="text-draft">strength · {story.strength}</span> : null}
                    {story.conflict ? <span>conflict · {story.conflict}</span> : null}
                    {story.learning ? <span>learning · {story.learning}</span> : null}
                  </p>
                ) : null}
              </li>
            ))}
          </ol>
        </SheetSection>
      )}

      {/* Revision strip */}
      <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-2 border-t border-ink/25 px-6 pb-4 pt-3">
        <p className="stencil text-[10px] uppercase leading-relaxed tracking-[0.1em] text-ink-2">
          profile {profileName ?? '—'} · {data.length} stories · {mapped} mapped · {totalUsage} uses total
          <br />
          drawn {new Date().toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })}
        </p>
        <p className="stencil text-[10px] uppercase leading-relaxed tracking-[0.1em] text-ink-3">
          stories are authored records — usage counts come from the backend.
        </p>
      </div>
    </Sheet>
  )
}
