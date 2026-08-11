import { useState } from 'react'
import {
  useAnalyzeRole,
  useCandidate,
  useDocuments,
  useExtractResume,
  useIndexDocument,
  useRoles,
  useUpdateCandidate,
  useUploadDocument,
  DEFAULT_USER_ID,
} from '../hooks/queries'
import { Button, ErrorState, Field, Pill, SectionHeading, Select, Spinner, Surface, TextArea, TextInput } from '../components/ui'

export function SetupPage() {
  const candidate = useCandidate(DEFAULT_USER_ID)
  const updateCandidate = useUpdateCandidate(DEFAULT_USER_ID)
  const documents = useDocuments(DEFAULT_USER_ID)
  const upload = useUploadDocument()
  const index = useIndexDocument()
  const extract = useExtractResume(DEFAULT_USER_ID)
  const roles = useRoles(DEFAULT_USER_ID)
  const analyzeRole = useAnalyzeRole()

  const [headline, setHeadline] = useState('')
  const [seniority, setSeniority] = useState('')
  const [jdText, setJdText] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [stage, setStage] = useState<string | null>(null)

  const resumeDoc = documents.data?.find((d) => d.kind === 'resume')
  const jdDoc = documents.data?.find((d) => d.kind === 'jd')
  const activeRole = roles.data?.at(-1)

  async function onUploadResume(file: File) {
    setError(null)
    try {
      setStage('Parsing resume…')
      const doc = await upload.mutateAsync({ userId: DEFAULT_USER_ID, kind: 'resume', file })
      setStage('Indexing into knowledge base…')
      await index.mutateAsync({ userId: DEFAULT_USER_ID, documentId: doc.id })
      setStage('Extracting claims…')
      await extract.mutateAsync({ documentId: doc.id })
      setStage(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Resume processing failed')
      setStage(null)
    }
  }

  async function onUploadJd(file: File) {
    setError(null)
    try {
      setStage('Parsing JD…')
      const doc = await upload.mutateAsync({ userId: DEFAULT_USER_ID, kind: 'jd', file })
      setStage('Indexing JD…')
      await index.mutateAsync({ userId: DEFAULT_USER_ID, documentId: doc.id })
      setStage(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'JD processing failed')
      setStage(null)
    }
  }

  async function onSaveProfile() {
    setError(null)
    try {
      await updateCandidate.mutateAsync({ headline: headline || undefined, seniority_target: seniority || undefined })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Save failed')
    }
  }

  async function onAnalyzeJd() {
    if (!jdText.trim()) return
    setError(null)
    try {
      setStage('Analyzing role & competencies…')
      await analyzeRole.mutateAsync({ user_id: DEFAULT_USER_ID, jd_text: jdText })
      setJdText('')
      setStage(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Role analysis failed')
      setStage(null)
    }
  }

  const steps = [
    { key: 'profile', label: 'Profile', done: Boolean(candidate.data?.headline || candidate.data?.seniority_target) },
    { key: 'resume', label: 'Resume', done: resumeDoc?.status === 'parsed' },
    { key: 'role', label: 'Target role', done: Boolean(activeRole) },
  ]

  return (
    <div className="space-y-8">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Profile & role</h1>
        <p className="mt-1 text-sm text-ink-500">Three inputs unlock everything else: who you are, what you've done, where you're going.</p>
      </header>

      {/* Setup progress */}
      <div aria-label="Setup progress" className="flex items-center gap-2">
        {steps.map((step, i) => (
          <div key={step.key} className="flex items-center gap-2">
            {i > 0 ? <span aria-hidden className="h-px w-6 bg-ink-200" /> : null}
            <Pill tone={step.done ? 'ok' : 'neutral'}>{step.done ? '✓ ' : ''}{step.label}</Pill>
          </div>
        ))}
      </div>

      {error ? <ErrorState title="Something went wrong" body={error} /> : null}

      <Surface className="p-6">
        <SectionHeading>Profile</SectionHeading>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Headline" hint="One line that captures where you are.">
            <TextInput placeholder={candidate.data?.headline ?? 'Senior Backend Engineer'} value={headline} onChange={(e) => setHeadline(e.target.value)} />
          </Field>
          <Field label="Seniority target">
            <Select value={seniority} onChange={(e) => setSeniority(e.target.value)}>
              <option value="">—</option>
              <option value="junior">Junior</option>
              <option value="mid">Mid</option>
              <option value="senior">Senior</option>
              <option value="staff">Staff</option>
              <option value="principal">Principal</option>
            </Select>
          </Field>
        </div>
        <div className="mt-4">
          <Button onClick={() => void onSaveProfile()} disabled={updateCandidate.isPending}>
            {updateCandidate.isPending ? 'Saving…' : 'Save profile'}
          </Button>
        </div>
      </Surface>

      <Surface className="p-6">
        <SectionHeading aside={resumeDoc ? <Pill tone={resumeDoc.status === 'parsed' ? 'ok' : 'warn'}>{resumeDoc.status}</Pill> : undefined}>
          Resume
        </SectionHeading>
        <p className="mb-4 text-sm text-ink-500">
          Pramya parses your resume, indexes it into your knowledge base, and extracts the claims that seed your evidence ledger.
        </p>
        {resumeDoc ? (
          <div className="mb-4 flex items-center justify-between rounded-lg border border-ink-200 bg-ink-50 px-4 py-3">
            <div className="min-w-0">
              <p className="truncate text-sm font-medium text-ink-800">{resumeDoc.filename}</p>
              <p className="text-xs text-ink-400">{resumeDoc.size.toLocaleString()} bytes · {resumeDoc.kind}</p>
            </div>
            {extract.data ? <Pill tone="ok">{extract.data.evidence_count} claims extracted</Pill> : null}
          </div>
        ) : null}
        <label className="inline-block">
          <span className="sr-only">Upload resume</span>
          <input
            type="file"
            accept=".pdf,.docx,.txt,.md"
            className="block w-full cursor-pointer text-sm text-ink-500 file:mr-3 file:rounded-lg file:border-0 file:bg-accent-700 file:px-4 file:py-2 file:text-sm file:font-medium file:text-white file:cursor-pointer hover:file:bg-accent-800"
            onChange={(e) => {
              const file = e.target.files?.[0]
              if (file) void onUploadResume(file)
            }}
          />
        </label>
        {stage && !stage.includes('role') ? <div className="mt-3"><Spinner label={stage} /></div> : null}
      </Surface>

      <Surface className="p-6">
        <SectionHeading aside={activeRole ? <Pill tone="ok">{activeRole.competencies?.length ?? 0} competencies</Pill> : undefined}>
          Target role
        </SectionHeading>
        <p className="mb-4 text-sm text-ink-500">
          Paste a job description or upload one. Pramya builds the competency model — required vs preferred — that drives readiness and preparation.
        </p>
        {activeRole ? (
          <div className="mb-4 rounded-lg border border-ink-200 bg-ink-50 px-4 py-3">
            <p className="text-sm font-medium text-ink-800">
              {activeRole.title} {activeRole.seniority ? `· ${activeRole.seniority}` : ''}
            </p>
            {activeRole.summary ? <p className="mt-0.5 text-xs text-ink-500">{activeRole.summary}</p> : null}
          </div>
        ) : null}
        <TextArea
          className="min-h-28"
          placeholder="Paste a job description here…"
          value={jdText}
          onChange={(e) => setJdText(e.target.value)}
        />
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <Button onClick={() => void onAnalyzeJd()} disabled={!jdText.trim() || analyzeRole.isPending}>
            {analyzeRole.isPending ? 'Analyzing…' : 'Analyze JD'}
          </Button>
          <label className="text-sm text-ink-500">
            or{' '}
            <input
              type="file"
              accept=".pdf,.docx,.txt,.md"
              className="cursor-pointer text-xs text-ink-500 file:mr-2 file:rounded-lg file:border-0 file:bg-ink-100 file:px-3 file:py-1.5 file:text-xs file:font-medium file:cursor-pointer"
              onChange={(e) => {
                const file = e.target.files?.[0]
                if (file) void onUploadJd(file)
              }}
            />
            upload a JD document
          </label>
          {jdDoc ? <Pill>{jdDoc.filename} ({jdDoc.status})</Pill> : null}
        </div>
        {stage?.includes('role') ? <div className="mt-3"><Spinner label={stage} /></div> : null}
      </Surface>
    </div>
  )
}
