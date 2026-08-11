import { useState } from 'react'
import { useCreateStory, useStories, DEFAULT_USER_ID } from '../hooks/queries'
import { Badge, Button, Card, EmptyState, SectionTitle } from '../components/ui'

export function StoriesPage() {
  const stories = useStories(DEFAULT_USER_ID)
  const createStory = useCreateStory()
  const [form, setForm] = useState({
    situation: '',
    task: '',
    action: '',
    result: '',
    metrics: '',
    conflict: '',
    learning: '',
    strength: '',
  })

  const filled = Object.values(form).some((v) => v.trim())

  async function save() {
    await createStory.mutateAsync({ user_id: DEFAULT_USER_ID, ...form })
    setForm({ situation: '', task: '', action: '', result: '', metrics: '', conflict: '', learning: '', strength: '' })
  }

  const fields: { key: keyof typeof form; label: string }[] = [
    { key: 'situation', label: 'Situation' },
    { key: 'task', label: 'Task' },
    { key: 'action', label: 'Action' },
    { key: 'result', label: 'Result' },
    { key: 'metrics', label: 'Metrics' },
    { key: 'conflict', label: 'Conflict' },
    { key: 'learning', label: 'Learning' },
    { key: 'strength', label: 'Strength' },
  ]

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold text-slate-900">Story Bank</h1>
        <p className="mt-1 text-sm text-slate-600">
          STAR stories mapped to competencies — reusable in interviews.
        </p>
      </header>

      <Card>
        <SectionTitle>Add a story</SectionTitle>
        <div className="grid gap-3 sm:grid-cols-2">
          {fields.map((f) => (
            <label key={f.key} className="block text-sm">
              <span className="text-slate-600">{f.label}</span>
              <textarea
                className="mt-1 min-h-16 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                value={form[f.key]}
                onChange={(e) => setForm((prev) => ({ ...prev, [f.key]: e.target.value }))}
              />
            </label>
          ))}
        </div>
        <div className="mt-3">
          <Button onClick={() => void save()} disabled={!filled || createStory.isPending}>
            {createStory.isPending ? 'Saving…' : 'Save story'}
          </Button>
        </div>
      </Card>

      <Card>
        <SectionTitle>Saved stories ({stories.data?.length ?? 0})</SectionTitle>
        {!stories.data?.length ? (
          <EmptyState title="No stories yet" hint="Add your first STAR story above." />
        ) : (
          <ul className="space-y-3">
            {stories.data.map((story) => (
              <li key={story.id} className="rounded-lg border border-slate-100 p-3">
                <p className="text-sm text-slate-800">
                  <span className="font-semibold">S:</span> {story.situation}
                </p>
                <p className="mt-1 text-sm text-slate-800">
                  <span className="font-semibold">R:</span> {story.result}
                </p>
                <div className="mt-2 flex flex-wrap gap-2">
                  {story.metrics ? <Badge tone="green">📈 {story.metrics}</Badge> : null}
                  {story.strength ? <Badge tone="blue">{story.strength}</Badge> : null}
                  <Badge>used {story.usage_count}×</Badge>
                </div>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  )
}
