// Setup — workspace initialization record. Three registered inputs unlock
// everything else: who you are (profile identity), what you've done
// (resume → parsed claims), where you're going (target role from a job
// description). Reads/writes mirror the frozen Profile/Settings surfaces:
// nothing is invented, every step state derives from real query data.

import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import {
  useAnalyzeRole,
  useCandidate,
  useCreateCandidate,
  useDocuments,
  useExtractResume,
  useIndexDocument,
  useResolvedProfile,
  useRoles,
  useUpdateCandidate,
  useUploadDocument,
  DEFAULT_USER_ID,
} from '../hooks/queries'
import { Button, ErrorState, Spinner } from '../components/ui'
import { Sheet, SheetSection, StencilNum } from '../components/sheet'

const inputCls =
  'h-9 w-full border border-ink/30 bg-sheet px-3 text-sm text-ink placeholder:text-ink-3 focus:border-draft focus:outline-none focus:shadow-[var(--focus-ring)]'
const taCls =
  'w-full resize-y border border-ink/30 bg-sheet px-3 py-2.5 text-sm leading-relaxed text-ink placeholder:text-ink-3 focus:border-draft focus:outline-none focus:shadow-[var(--focus-ring)]'
const linkCls =
  'stencil text-[10px] uppercase tracking-[0.1em] text-draft underline underline-offset-2 hover:text-draft-2'

function pad2(n: number): string {
  return String(n).padStart(2, '0')
}

export function SetupPage() {
  const navigate = useNavigate()
  const candidate = useCandidate(DEFAULT_USER_ID)
  const { activeId, active, isLoading: profilesLoading } = useResolvedProfile(DEFAULT_USER_ID)
  const updateCandidate = useUpdateCandidate(DEFAULT_USER_ID)
  const createCandidate = useCreateCandidate()
  const documents = useDocuments(DEFAULT_USER_ID, activeId)
  const upload = useUploadDocument()
  const index = useIndexDocument()
  const extract = useExtractResume(DEFAULT_USER_ID, activeId)
  const roles = useRoles(DEFAULT_USER_ID, activeId)
  const analyzeRole = useAnalyzeRole()

  const [headline, setHeadline] = useState('')
  const [seniority, setSeniority] = useState('')
  const [jdText, setJdText] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [stage, setStage] = useState<string | null>(null)

  const resumeDoc = documents.data?.find((d) => d.kind === 'resume')
  const jdDoc = documents.data?.find((d) => d.kind === 'jd')
  const activeRole = roles.data?.at(-1)

  async function onUploadResume(file: File) {
    setError(null)
    setNotice(null)
    if (activeId == null) return
    try {
      setStage('Parsing resume…')
      const result = await upload.mutateAsync({ userId: DEFAULT_USER_ID, profileId: activeId, kind: 'resume', file })
      if (result.status === 'deduplicated') {
        setNotice(`That exact file was already uploaded — reusing document #${result.document_id}.`)
        void documents.refetch()
        return
      }
      setStage('Indexing into knowledge base…')
      await index.mutateAsync({ userId: DEFAULT_USER_ID, profileId: activeId, documentId: result.document_id })
      setStage('Extracting claims…')
      await extract.mutateAsync({ documentId: result.document_id })
      setStage(null)
    } catch (err) {
      setStage(null)
      setError(err instanceof Error ? err.message : 'Resume processing failed')
    }
  }

  async function onUploadJd(file: File) {
    setError(null)
    setNotice(null)
    if (activeId == null) return
    try {
      setStage('Parsing JD…')
      const result = await upload.mutateAsync({ userId: DEFAULT_USER_ID, profileId: activeId, kind: 'jd', file })
      if (result.status === 'deduplicated') {
        setNotice(`That exact file was already uploaded — reusing document #${result.document_id}.`)
        void documents.refetch()
        return
      }
      setStage('Indexing JD…')
      await index.mutateAsync({ userId: DEFAULT_USER_ID, profileId: activeId, documentId: result.document_id })
      setStage(null)
    } catch (err) {
      setStage(null)
      setError(err instanceof Error ? err.message : 'JD processing failed')
    }
  }

  async function onSaveProfile() {
    setError(null)
    try {
      const patch = { headline: headline || undefined, seniority_target: seniority || undefined }
      if (candidate.data) {
        await updateCandidate.mutateAsync(patch)
      } else {
        // First run: create the user's default career profile (fresh install).
        await createCandidate.mutateAsync(patch)
        navigate('/profile')
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Save failed')
    }
  }

  async function onAnalyzeJd() {
    if (!jdText.trim() || activeId == null) return
    setError(null)
    try {
      setStage('Analyzing role & competencies…')
      await analyzeRole.mutateAsync({ user_id: DEFAULT_USER_ID, profile_id: activeId, jd_text: jdText })
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
  const allDone = steps.every((s) => s.done)

  return (
    <Sheet aria-label="Workspace initialization">
      {/* Title block */}
      <div className="flex flex-wrap items-start justify-between gap-x-8 gap-y-4 border-b border-ink/25 px-6 pb-4 pt-5">
        <div className="min-w-0">
          <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-ink-2">Pramya · Setup · Initiation</p>
          <h1 className="mt-1.5 text-xl font-semibold tracking-tight text-ink">Profile &amp; role</h1>
          <p className="mt-1 max-w-xl text-[13px] leading-relaxed text-ink-2">
            Three inputs unlock everything else: who you are, what you've done, where you're going.
            {active ? <span className="text-draft-2"> Working in profile “{active.name}”.</span> : null}
          </p>
        </div>
        <div className="w-full border border-ink/30 bg-sheet-lit/45 px-4 py-3 sm:w-[17rem]">
          <div className="flex items-baseline justify-between gap-3">
            <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-ink-2">Initiation state</p>
            <span className={`stencil text-[10px] uppercase tracking-[0.16em] ${allDone ? 'text-draft' : 'text-ink-2'}`}>
              {allDone ? 'Ready' : 'In progress'}
            </span>
          </div>
          <dl className="mt-2">
            {[
              ['Profile', steps[0].done ? 'Ready' : 'Pending'],
              ['Resume', steps[1].done ? 'Parsed' : 'Pending'],
              ['Target role', steps[2].done ? 'Set' : 'Pending'],
              ['Active profile', active?.name ?? '—'],
            ].map(([label, value]) => (
              <div key={label} className="flex items-baseline justify-between gap-3 border-t border-ink/15 pt-1.5">
                <dt className="stencil text-[10px] uppercase tracking-[0.12em] text-ink-3">{label}</dt>
                <dd className={`stencil truncate text-[10px] uppercase tracking-[0.12em] ${value === 'Pending' || value === '—' ? 'text-ink-3' : 'text-ink-2'}`}>{value}</dd>
              </div>
            ))}
          </dl>
        </div>
      </div>

      {/* Step line — registered initialization sequence */}
      <div aria-label="Setup progress" className="flex flex-wrap items-center gap-x-5 gap-y-2 border-b border-ink/15 px-6 py-3">
        {steps.map((step, i) => (
          <span key={step.key} className="flex items-center gap-2">
            {i > 0 ? <span aria-hidden className="h-px w-5 border-t border-dashed border-ink/25" /> : null}
            <StencilNum className="text-[10px] leading-none text-ink-3">{pad2(i + 1)}</StencilNum>
            <span className="text-[12px] font-medium text-ink">{step.label}</span>
            <span className={`stencil text-[9px] uppercase tracking-[0.14em] ${step.done ? 'text-draft' : 'text-ink-3'}`}>
              {step.done ? 'Ready' : 'Pending'}
            </span>
          </span>
        ))}
      </div>

      {error ? <ErrorState title="Something went wrong" body={error} className="m-6" /> : null}
      {notice ? (
        <p className="stencil border-b border-dashed border-draft/40 bg-draft-soft/15 px-6 py-2.5 text-[10px] uppercase leading-relaxed tracking-[0.1em] text-draft-2">
          notice · {notice}
        </p>
      ) : null}

      {/* 01 · PROFILE */}
      <SheetSection
        title="Profile"
        tone="lit"
        aside={<span className="stencil text-[10px] uppercase tracking-[0.14em] text-ink-2">identity record</span>}
      >
        <p className="py-1 text-[12px] leading-relaxed text-ink-2">One line that captures where you are, and the seniority you are aiming at.</p>
        <div className="mt-2 grid gap-4 sm:grid-cols-2">
          <label className="block">
            <span className="stencil block pb-1.5 text-[10px] uppercase tracking-[0.12em] text-ink-3">Headline</span>
            <input
              className={inputCls}
              placeholder={candidate.data?.headline ?? 'Senior Backend Engineer'}
              value={headline}
              onChange={(e) => setHeadline(e.target.value)}
            />
          </label>
          <label className="block">
            <span className="stencil block pb-1.5 text-[10px] uppercase tracking-[0.12em] text-ink-3">Seniority target</span>
            <select className={inputCls} value={seniority} onChange={(e) => setSeniority(e.target.value)}>
              <option value="">—</option>
              <option value="junior">Junior</option>
              <option value="mid">Mid</option>
              <option value="senior">Senior</option>
              <option value="staff">Staff</option>
              <option value="principal">Principal</option>
            </select>
          </label>
        </div>
        <div className="mt-4 flex items-center gap-4">
          <Button onClick={() => void onSaveProfile()} disabled={updateCandidate.isPending || profilesLoading}>
            {updateCandidate.isPending ? 'Saving…' : 'Save profile'}
          </Button>
          <Link className={linkCls} to="/profile">
            Manage profiles →
          </Link>
        </div>
      </SheetSection>

      {/* 02 · SOURCES · RESUME */}
      <SheetSection
        title="Source · resume"
        aside={
          resumeDoc ? (
            <span className={`stencil text-[10px] uppercase tracking-[0.14em] ${resumeDoc.status === 'parsed' ? 'text-draft' : 'text-ink-2'}`}>
              {resumeDoc.status}
            </span>
          ) : (
            <span className="stencil text-[10px] uppercase tracking-[0.14em] text-ink-3">not uploaded</span>
          )
        }
      >
        <p className="py-1 text-[12px] leading-relaxed text-ink-2">
          Pramya parses your resume, indexes it into your knowledge base, and extracts the claims that seed your evidence ledger.
        </p>
        {resumeDoc ? (
          <div className="mt-2 grid grid-cols-[2.25rem_minmax(0,1fr)_auto] items-center gap-x-3 border border-ink/20 px-3 py-2.5">
            <StencilNum className="text-[11px] leading-none text-ink-3">01</StencilNum>
            <div className="min-w-0">
              <p className="truncate text-[13px] font-semibold text-ink">{resumeDoc.filename}</p>
              <p className="text-[11px] text-ink-3">{resumeDoc.size.toLocaleString()} bytes · {resumeDoc.kind}</p>
            </div>
            {extract.data ? (
              <span className="stencil text-[10px] uppercase tracking-[0.12em] text-draft">{extract.data.evidence_count} claims</span>
            ) : (
              <span className="stencil text-[10px] uppercase tracking-[0.12em] text-ink-3">indexed</span>
            )}
          </div>
        ) : null}
        <div className="mt-3 flex flex-wrap items-center gap-4">
          <label className="inline-flex h-9 cursor-pointer items-center border border-ink/30 bg-sheet px-3 text-sm text-ink transition-colors hover:border-draft/60 focus-within:shadow-[var(--focus-ring)]">
            Upload resume
            <input
              type="file"
              accept=".pdf,.docx,.txt,.md"
              className="sr-only"
              onChange={(e) => {
                const file = e.target.files?.[0]
                if (file) void onUploadResume(file)
              }}
            />
          </label>
          {stage && !stage.includes('role') ? <Spinner label={stage} subtle /> : null}
        </div>
      </SheetSection>

      {/* 03 · TARGET ROLE */}
      <SheetSection
        title="Target role"
        aside={
          activeRole ? (
            <span className="stencil text-[10px] uppercase tracking-[0.14em] text-draft">
              {activeRole.competencies?.length ?? 0} competencies
            </span>
          ) : (
            <span className="stencil text-[10px] uppercase tracking-[0.14em] text-ink-3">not set</span>
          )
        }
      >
        <p className="py-1 text-[12px] leading-relaxed text-ink-2">
          Paste a job description or upload one. Pramya builds the competency model — required vs preferred — that drives readiness and preparation.
        </p>
        {activeRole ? (
          <div className="mt-2 grid grid-cols-[2.25rem_minmax(0,1fr)] items-baseline gap-x-3 border border-ink/20 px-3 py-2.5">
            <StencilNum className="text-[11px] leading-none text-ink-3">01</StencilNum>
            <div className="min-w-0">
              <p className="text-[13px] font-semibold text-ink">
                {activeRole.title} {activeRole.seniority ? `· ${activeRole.seniority}` : ''}
              </p>
              {activeRole.summary ? <p className="mt-0.5 text-[12px] leading-relaxed text-ink-2">{activeRole.summary}</p> : null}
            </div>
          </div>
        ) : null}
        <textarea
          aria-label="Job description text"
          className={`${taCls} mt-2 min-h-28`}
          placeholder="Paste a job description here…"
          value={jdText}
          onChange={(e) => setJdText(e.target.value)}
        />
        <div className="mt-3 flex flex-wrap items-center gap-4">
          <Button onClick={() => void onAnalyzeJd()} disabled={!jdText.trim() || analyzeRole.isPending || activeId == null}>
            {analyzeRole.isPending ? 'Analyzing…' : 'Analyze JD'}
          </Button>
          <label className="stencil inline-flex cursor-pointer items-center gap-2 text-[10px] uppercase tracking-[0.1em] text-ink-2">
            <span className="inline-flex h-9 cursor-pointer items-center border border-ink/30 bg-sheet px-3 text-sm normal-case tracking-normal text-ink transition-colors hover:border-draft/60 focus-within:shadow-[var(--focus-ring)]">
              Upload JD
            </span>
            <input
              type="file"
              accept=".pdf,.docx,.txt,.md"
              className="sr-only"
              onChange={(e) => {
                const file = e.target.files?.[0]
                if (file) void onUploadJd(file)
              }}
            />
            {jdDoc ? (
              <span className={`${linkCls} normal-case tracking-normal`}>
                {jdDoc.filename} ({jdDoc.status})
              </span>
            ) : null}
          </label>
          {stage?.includes('role') ? <Spinner label={stage} subtle /> : null}
        </div>
      </SheetSection>

      {/* Revision strip */}
      <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-2 border-t border-ink/25 px-6 pb-4 pt-3">
        <p className="stencil text-[10px] uppercase leading-relaxed tracking-[0.1em] text-ink-2">
          profile {active?.name ?? '—'} · {steps.filter((s) => s.done).length}/3 inputs on file
          <br />
          drawn {new Date().toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })}
        </p>
        <p className="stencil text-[10px] uppercase leading-relaxed tracking-[0.1em] text-ink-3">
          {allDone ? 'workspace initialized — continue to preparation.' : 'remaining inputs shown above as pending.'}
        </p>
      </div>
    </Sheet>
  )
}
