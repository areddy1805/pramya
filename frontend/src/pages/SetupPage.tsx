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
import { Badge, Button, Card, EmptyState, ErrorState, SectionTitle, Spinner } from '../components/ui'

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
  const [uploadError, setUploadError] = useState<string | null>(null)

  const resumeDoc = documents.data?.find((d) => d.kind === 'resume')
  const jdDoc = documents.data?.find((d) => d.kind === 'jd')
  const activeRole = roles.data?.at(-1)

  async function onUploadResume(file: File) {
    setUploadError(null)
    try {
      const doc = await upload.mutateAsync({ userId: DEFAULT_USER_ID, kind: 'resume', file })
      await index.mutateAsync({ userId: DEFAULT_USER_ID, documentId: doc.id })
      await extract.mutateAsync({ documentId: doc.id })
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : 'upload failed')
    }
  }

  async function onUploadJd(file: File) {
    setUploadError(null)
    try {
      const doc = await upload.mutateAsync({ userId: DEFAULT_USER_ID, kind: 'jd', file })
      await index.mutateAsync({ userId: DEFAULT_USER_ID, documentId: doc.id })
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : 'upload failed')
    }
  }

  async function onSaveProfile() {
    await updateCandidate.mutateAsync({ headline: headline || undefined, seniority_target: seniority || undefined })
  }

  async function onAnalyzeJd() {
    if (!jdText.trim()) return
    await analyzeRole.mutateAsync({ user_id: DEFAULT_USER_ID, jd_text: jdText })
    setJdText('')
  }

  const busy = upload.isPending || index.isPending || extract.isPending || analyzeRole.isPending

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold text-slate-900">Candidate Setup</h1>
        <p className="mt-1 text-sm text-slate-600">Profile · resume · target role</p>
      </header>

      {uploadError ? <ErrorState message={uploadError} /> : null}

      <Card>
        <SectionTitle>Profile</SectionTitle>
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="block text-sm">
            <span className="text-slate-600">Headline</span>
            <input
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
              placeholder={candidate.data?.headline ?? 'Senior Backend Engineer'}
              value={headline}
              onChange={(e) => setHeadline(e.target.value)}
            />
          </label>
          <label className="block text-sm">
            <span className="text-slate-600">Seniority target</span>
            <select
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
              value={seniority}
              onChange={(e) => setSeniority(e.target.value)}
            >
              <option value="">—</option>
              <option value="junior">Junior</option>
              <option value="mid">Mid</option>
              <option value="senior">Senior</option>
              <option value="staff">Staff</option>
              <option value="principal">Principal</option>
            </select>
          </label>
        </div>
        <div className="mt-3">
          <Button onClick={() => void onSaveProfile()} disabled={updateCandidate.isPending}>
            {updateCandidate.isPending ? 'Saving…' : 'Save profile'}
          </Button>
        </div>
      </Card>

      <Card>
        <SectionTitle>Resume</SectionTitle>
        {resumeDoc ? (
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-sm font-medium text-slate-800">{resumeDoc.filename}</p>
              <p className="text-xs text-slate-500">
                status: {resumeDoc.status} · {resumeDoc.size} bytes
              </p>
            </div>
            <Badge tone={resumeDoc.status === 'parsed' ? 'green' : 'amber'}>{resumeDoc.status}</Badge>
          </div>
        ) : (
          <p className="text-sm text-slate-500">No resume yet.</p>
        )}
        <label className="mt-3 block">
          <span className="sr-only">Upload resume</span>
          <input
            type="file"
            accept=".pdf,.docx,.txt,.md"
            className="block w-full text-sm text-slate-600 file:mr-3 file:rounded-lg file:border-0 file:bg-blue-700 file:px-4 file:py-2 file:text-sm file:font-medium file:text-white"
            onChange={(e) => {
              const file = e.target.files?.[0]
              if (file) void onUploadResume(file)
            }}
          />
        </label>
        {busy ? <Spinner label="Parsing, indexing and extracting…" /> : null}
        {extract.data ? <p className="mt-2 text-xs text-slate-500">{extract.data.evidence_count} evidence claims extracted</p> : null}
      </Card>

      <Card>
        <SectionTitle>Target role (JD)</SectionTitle>
        {activeRole ? (
          <div className="mb-3">
            <p className="text-sm font-medium text-slate-800">{activeRole.title}</p>
            <p className="text-xs text-slate-500">{activeRole.seniority ?? ''} · {activeRole.competencies?.length ?? 0} competencies</p>
          </div>
        ) : (
          <p className="text-sm text-slate-500">No role analyzed yet.</p>
        )}
        <textarea
          className="min-h-28 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
          placeholder="Paste a job description here…"
          value={jdText}
          onChange={(e) => setJdText(e.target.value)}
        />
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <Button onClick={() => void onAnalyzeJd()} disabled={!jdText.trim() || analyzeRole.isPending}>
            {analyzeRole.isPending ? 'Analyzing…' : 'Analyze JD'}
          </Button>
          <label className="text-sm text-slate-500">
            or{' '}
            <input
              type="file"
              accept=".pdf,.docx,.txt,.md"
              className="text-xs file:mr-2 file:rounded-lg file:border-0 file:bg-slate-100 file:px-3 file:py-1.5 file:text-xs file:font-medium"
              onChange={(e) => {
                const file = e.target.files?.[0]
                if (file) void onUploadJd(file)
              }}
            />
            upload JD document
          </label>
        </div>
        {jdDoc ? (
          <p className="mt-2 text-xs text-slate-500">
            JD document: {jdDoc.filename} ({jdDoc.status})
          </p>
        ) : null}
      </Card>

      <Card>
        <SectionTitle>Evidence ledger</SectionTitle>
        {!documents.data?.length ? (
          <EmptyState title="No documents yet" hint="Upload a resume to build your evidence profile." />
        ) : (
          <ul className="divide-y divide-slate-100">
            {documents.data.map((d) => (
              <li key={d.id} className="flex items-center justify-between py-2 text-sm">
                <span className="text-slate-700">{d.filename}</span>
                <Badge>{d.kind} · {d.status}</Badge>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  )
}
