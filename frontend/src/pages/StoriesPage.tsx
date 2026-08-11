import { useState } from 'react'
import { useCreateStory, useStories, DEFAULT_USER_ID } from '../hooks/queries'
import { Button, EmptyState, Field, Pill, SectionHeading, Surface, TextArea } from '../components/ui'

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

export function StoriesPage() {
  const stories = useStories(DEFAULT_USER_ID)
  const createStory = useCreateStory()
  const [form, setForm] = useState<Record<string, string>>({})

  const filled = Object.values(form).some((v) => v.trim())

  async function save() {
    await createStory.mutateAsync({ user_id: DEFAULT_USER_ID, ...form })
    setForm({})
  }

  return (
    <div className="space-y-8">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Story bank</h1>
        <p className="mt-1 text-sm text-ink-500">Your reusable evidence in STAR form — mapped to competencies, ready for behavioral interviews.</p>
      </header>

      <Surface className="p-6">
        <SectionHeading>Add a story</SectionHeading>
        <div className="grid gap-4 sm:grid-cols-2">
          {FIELDS.map((f) => (
            <Field key={f.key} label={f.label} hint={f.hint}>
              <TextArea
                className="min-h-16"
                value={form[f.key] ?? ''}
                onChange={(e) => setForm((prev) => ({ ...prev, [f.key]: e.target.value }))}
              />
            </Field>
          ))}
        </div>
        <div className="mt-4">
          <Button onClick={() => void save()} disabled={!filled || createStory.isPending}>
            {createStory.isPending ? 'Saving…' : 'Save story'}
          </Button>
        </div>
      </Surface>

      <Surface className="p-6">
        <SectionHeading aside={<Pill>{stories.data?.length ?? 0} stories</Pill>}>Saved stories</SectionHeading>
        {!stories.data?.length ? (
          <EmptyState icon="📚" title="Your story bank is empty" body="Add one STAR story above. During behavioral interviews, the interviewer can ground questions in what you've actually done." />
        ) : (
          <ul className="space-y-3">
            {stories.data.map((story) => (
              <li key={story.id} className="rounded-lg border border-ink-200 p-4">
                <div className="grid gap-3 sm:grid-cols-2">
                  <p className="text-sm text-ink-800"><span className="font-semibold">S</span> {story.situation}</p>
                  <p className="text-sm text-ink-800"><span className="font-semibold">T</span> {story.task}</p>
                  <p className="text-sm text-ink-800"><span className="font-semibold">A</span> {story.action}</p>
                  <p className="text-sm text-ink-800"><span className="font-semibold">R</span> {story.result}</p>
                </div>
                <div className="mt-3 flex flex-wrap gap-2">
                  {story.metrics ? <Pill tone="ok">📈 {story.metrics}</Pill> : null}
                  {story.strength ? <Pill tone="accent">{story.strength}</Pill> : null}
                  {story.conflict ? <Pill>{story.conflict}</Pill> : null}
                  <Pill>used {story.usage_count}×</Pill>
                </div>
              </li>
            ))}
          </ul>
        )}
      </Surface>
    </div>
  )
}
