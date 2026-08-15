// Career profile dossier — the authoritative source document for who the
// candidate is and what Pramya is allowed to know/use. A record, not a
// settings form: identity spec, target model, sources, and profile state,
// each as a registered section of one sheet.

import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  DEFAULT_USER_ID,
  useActiveProfile,
  useAnalyzeRole,
  useCreateProfile,
  useDeleteProfile,
  useDeleteDocument,
  useDocuments,
  useEvidence,
  useIndexDocument,
  useResolvedProfile,
  useRoles,
  useSetActiveProfile,
  useSetPreferredDocument,
  useUpdateProfile,
  useUploadDocument,
} from '../hooks/queries'
import { Button, ErrorState, Spinner } from '../components/ui'
import { Sheet, SheetSection, StencilNum } from '../components/sheet'

const SENIORITY = [
  { value: 'junior', label: 'Junior' },
  { value: 'mid', label: 'Mid' },
  { value: 'senior', label: 'Senior' },
  { value: 'staff', label: 'Staff' },
  { value: 'principal', label: 'Principal' },
]

const DOC_TONE: Record<string, string> = {
  parsed: 'text-draft',
  failed: 'text-redline',
  processing: 'text-ink-2',
}

function pad2(n: number): string {
  return String(n).padStart(2, '0')
}

function fmtBytes(n: number): string {
  return n >= 1024 * 1024 ? `${(n / 1024 / 1024).toFixed(1)} MB` : `${Math.max(1, Math.round(n / 1024))} KB`
}

// --- Dossier state cell ------------------------------------------------------

// Compact summary of the profile's state in the title block: what the
// dossier holds and what the interview is grounded in.
function DossierCell({
  profileName,
  evidenceCount,
  rolesCount,
  resumeStatus,
  jdStatus,
}: {
  profileName: string | null
  evidenceCount: number | null
  rolesCount: number | null
  resumeStatus: string
  jdStatus: string
}) {
  return (
    <div className="w-full border border-ink/30 bg-sheet-lit/45 px-4 py-3 sm:w-[17rem]">
      <div className="flex items-baseline justify-between gap-3">
        <p className="text-[10px] font-medium uppercase tracking-[0.12em] text-ink-2/70">Dossier state</p>
        <span className="stencil text-[10px] uppercase tracking-[0.16em] text-draft">On record</span>
      </div>
      <dl className="mt-2">
        {[
          ['Profile', profileName ?? '—'],
          ['Evidence', evidenceCount != null ? `${evidenceCount} records` : '—'],
          ['Target roles', rolesCount != null ? `${rolesCount}` : '—'],
          ['Resume', resumeStatus],
          ['JD', jdStatus],
        ].map(([label, value]) => (
          <div key={label} className="flex items-baseline justify-between gap-3 border-t border-ink/10 pt-1.5">
            <dt className="stencil text-[10px] uppercase tracking-[0.12em] text-ink-3">{label}</dt>
            <dd className={`stencil truncate text-[10px] uppercase tracking-[0.12em] ${value === '—' || value.includes('missing') ? 'text-ink-3' : value.includes('ready') || value.includes('parsed') ? 'text-draft' : 'text-ink-2'}`}>
              {value}
            </dd>
          </div>
        ))}
      </dl>
    </div>
  )
}

// --- Spec row (label : value) -------------------------------------------------

function SpecRow({ label, value, edit, children }: { label: string; value?: string | null; edit?: boolean; children?: React.ReactNode }) {
  return (
    <div className="grid grid-cols-[7.5rem_minmax(0,1fr)] items-baseline gap-x-4 border-t border-ink/10 py-2.5 first:border-t-0 first:pt-0 sm:grid-cols-[10rem_minmax(0,1fr)]">
      <dt className="stencil text-[10px] uppercase tracking-[0.12em] text-ink-3">{label}</dt>
      <dd className="min-w-0 text-[13px] leading-relaxed text-ink">
        {edit ? children : (value?.trim() ? value : <span className="text-ink-3">—</span>)}
      </dd>
    </div>
  )
}

// 36px registered control (select / input / textarea) — sheet linework.
const FIELD_CLS =
  'w-full border border-ink/30 bg-sheet px-3 text-sm text-ink placeholder:text-ink-3 focus:border-draft focus:outline-none focus:shadow-[var(--focus-ring)] disabled:bg-sheet-shadow/30 disabled:text-ink-3'

// --- Profile switcher ---------------------------------------------------------

function ProfileSwitcher({
  profiles,
  activeId,
  newName,
  onName,
  onCreate,
  onSwitch,
  busy,
}: {
  profiles: Array<{ id: number; name: string }>
  activeId: number | null
  newName: string
  onName: (v: string) => void
  onCreate: () => void
  onSwitch: (id: number) => void
  busy: boolean
}) {
  return (
    <SheetSection
      title="Profiles · workspaces"
      aside={<span className="stencil text-[10px] uppercase tracking-[0.14em] text-ink-2">{profiles.length} on record</span>}
    >
      <div className="flex flex-wrap items-center gap-1.5 py-1">
        {profiles.map((p) => {
          const active = p.id === activeId
          return (
            <button
              key={p.id}
              type="button"
              onClick={() => onSwitch(p.id)}
              aria-pressed={active}
              className={`stencil h-8 border px-2.5 text-[10px] uppercase tracking-[0.12em] transition-colors focus-visible:outline-none focus-visible:shadow-[var(--focus-ring)] ${
                active ? 'border-draft bg-draft-soft text-draft-2' : 'border-ink/30 text-ink-2 hover:border-draft hover:text-draft'
              }`}
            >
              {p.name}
            </button>
          )
        })}
        <span aria-hidden className="mx-1.5 h-5 w-px bg-ink/20" />
        <input
          aria-label="New profile name"
          className={`h-9 w-40 ${FIELD_CLS}`}
          placeholder="New profile name…"
          value={newName}
          onChange={(e) => onName(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') onCreate()
          }}
        />
        <Button size="sm" onClick={onCreate} disabled={!newName.trim() || busy}>
          {busy ? 'Creating…' : 'New profile'}
        </Button>
      </div>
    </SheetSection>
  )
}

// --- Document ledger row ------------------------------------------------------

function DocRow({
  index,
  filename,
  status,
  size,
  current,
  currentLabel,
  actions,
}: {
  index: string
  filename: string
  status: string
  size: number
  current: boolean
  currentLabel: string
  actions: React.ReactNode
}) {
  return (
    <li className={`grid grid-cols-[2rem_minmax(0,1fr)_auto] items-center gap-x-3 border-b border-ink/5 px-1 py-2 last:border-b-0 ${current ? 'bg-draft-soft/30' : ''}`}>
      <StencilNum className="text-[11px] leading-none text-ink-3">{index}</StencilNum>
      <div className="min-w-0">
        <div className="flex items-center gap-2">
          <p className="truncate text-[13px] text-ink">{filename}</p>
          {current ? <span className="stencil shrink-0 text-[9px] uppercase tracking-[0.14em] text-draft">{currentLabel}</span> : null}
        </div>
        <p className="text-[11px] text-ink-3">
          <span className={`stencil text-[10px] uppercase tracking-[0.1em] ${DOC_TONE[status] ?? 'text-ink-2'}`}>{status}</span>
          {' · '}
          {fmtBytes(size)}
        </p>
      </div>
      <div className="flex shrink-0 items-center gap-1.5">{actions}</div>
    </li>
  )
}

// --- Upload drop zone ---------------------------------------------------------

function UploadZone({ label, hint, accept, onFile }: { label: string; hint: string; accept: string; onFile: (f: File) => void }) {
  return (
    <label className="mt-3 flex h-10 cursor-pointer items-center justify-between gap-3 border border-dashed border-ink/40 px-3 transition-colors hover:border-draft focus-within:border-draft focus-within:shadow-[var(--focus-ring)]">
      <span className="stencil text-[10px] uppercase tracking-[0.12em] text-ink-2">{label}</span>
      <span className="text-[11px] text-ink-3">{hint}</span>
      <input
        type="file"
        accept={accept}
        className="sr-only"
        onChange={(e) => {
          const file = e.target.files?.[0]
          if (file) onFile(file)
        }}
      />
    </label>
  )
}

export function ProfilePage() {
  const userId = DEFAULT_USER_ID
  const { active, activeId, profiles } = useResolvedProfile(userId)
  const activeQuery = useActiveProfile(userId)
  const setActive = useSetActiveProfile(userId)
  const createProfile = useCreateProfile(userId)
  const updateProfile = useUpdateProfile(userId, activeId ?? 0)
  const deleteProfile = useDeleteProfile(userId)

  const documents = useDocuments(userId, activeId)
  const resumes = useMemo(() => documents.data?.filter((d) => d.kind === 'resume') ?? [], [documents.data])
  const jds = useMemo(() => documents.data?.filter((d) => d.kind === 'jd') ?? [], [documents.data])
  const upload = useUploadDocument()
  const index = useIndexDocument()
  const setPreferred = useSetPreferredDocument(userId, activeId ?? 0)
  const deleteDoc = useDeleteDocument(userId, activeId ?? 0)
  const roles = useRoles(userId, activeId)
  const analyzeRole = useAnalyzeRole()
  const evidence = useEvidence(userId, activeId)

  // Form state
  const [name, setName] = useState('')
  const [positioning, setPositioning] = useState('')
  const [headline, setHeadline] = useState('')
  const [seniority, setSeniority] = useState('')
  const [newProfileName, setNewProfileName] = useState('')
  const [jdText, setJdText] = useState('')
  const [editing, setEditing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [stage, setStage] = useState<string | null>(null)

  const currentResume =
    resumes.find((d) => d.id === active?.preferred_resume_document_id) ??
    resumes[resumes.length - 1] ??
    null
  const currentJd =
    jds.find((d) => d.id === active?.preferred_jd_document_id) ?? jds[jds.length - 1] ?? null

  // Unsaved changes — any typed value in the revision block.
  const dirty = editing && (name.trim() !== '' || positioning.trim() !== '' || headline.trim() !== '' || seniority !== '')

  async function onSwitch(profileId: number) {
    setError(null)
    setNotice(null)
    setEditing(false)
    try {
      await setActive.mutateAsync(profileId)
      setName('')
      setPositioning('')
      setHeadline('')
      setSeniority('')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Switch failed')
    }
  }

  async function onCreateProfile() {
    setError(null)
    if (!newProfileName.trim()) return
    try {
      await createProfile.mutateAsync({ name: newProfileName.trim() })
      setNewProfileName('')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Create failed')
    }
  }

  async function onSaveProfile() {
    setError(null)
    if (activeId == null) return
    try {
      await updateProfile.mutateAsync({
        name: name || undefined,
        positioning: positioning || undefined,
        headline: headline || undefined,
        seniority_target: seniority || undefined,
      })
      setEditing(false)
      setName('')
      setPositioning('')
      setHeadline('')
      setSeniority('')
      setNotice('Profile saved.')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Save failed')
    }
  }

  async function onUploadResume(file: File) {
    setError(null)
    setNotice(null)
    if (activeId == null) return
    try {
      setStage('Uploading & parsing resume…')
      const result = await upload.mutateAsync({ userId, profileId: activeId, kind: 'resume', file })
      if (result.status === 'deduplicated') {
        setNotice(`That exact file is already uploaded — using existing document #${result.document_id}.`)
      } else {
        setStage('Indexing into knowledge base…')
        await index.mutateAsync({ userId, profileId: activeId, documentId: result.document_id })
      }
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
      setStage('Uploading & parsing JD…')
      const result = await upload.mutateAsync({ userId, profileId: activeId, kind: 'jd', file })
      if (result.status === 'deduplicated') {
        setNotice(`That exact file is already uploaded — using existing document #${result.document_id}.`)
      } else {
        setStage('Indexing JD…')
        await index.mutateAsync({ userId, profileId: activeId, documentId: result.document_id })
      }
      setStage(null)
    } catch (err) {
      setStage(null)
      setError(err instanceof Error ? err.message : 'JD processing failed')
    }
  }

  async function onAnalyzeJd() {
    setError(null)
    if (!jdText.trim() || activeId == null) return
    try {
      setStage('Analyzing role & competencies…')
      await analyzeRole.mutateAsync({ user_id: userId, profile_id: activeId, jd_text: jdText })
      setJdText('')
      setStage(null)
    } catch (err) {
      setStage(null)
      setError(err instanceof Error ? err.message : 'Role analysis failed')
    }
  }

  async function onDeleteProfile() {
    setError(null)
    if (activeId == null || profiles.length <= 1) {
      setError('Cannot delete the last profile.')
      return
    }
    if (!window.confirm(`Delete profile "${active?.name}"? All its resumes, roles, and evidence will be removed.`)) return
    try {
      await deleteProfile.mutateAsync(activeId)
      const remaining = profiles.find((p) => p.id !== activeId)
      if (remaining) await setActive.mutateAsync(remaining.id)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Delete failed')
    }
  }

  const loadedProfile = activeQuery.data?.profile ?? active

  return (
    <Sheet aria-label="Profile dossier">
      {/* Title block */}
      <div className="flex flex-wrap items-start justify-between gap-x-8 gap-y-4 border-b border-ink/25 px-6 pb-4 pt-5">
        <div className="min-w-0">
          <p className="text-[10px] font-medium uppercase tracking-[0.12em] text-ink-2/70">Pramya · Profile · Dossier</p>
          <h1 className="mt-1.5 text-xl font-semibold tracking-tight text-ink">Career profiles</h1>
          <p className="mt-1 max-w-xl text-[13px] leading-relaxed text-ink-2">
            Each profile is an independent workspace — its own resume, target roles, JDs, and evidence. Nothing leaks between them.
          </p>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            {activeId != null && profiles.length > 1 ? (
              <Button variant="danger" size="sm" onClick={() => void onDeleteProfile()} disabled={deleteProfile.isPending}>
                Delete profile
              </Button>
            ) : null}
          </div>
        </div>
        <DossierCell
          profileName={loadedProfile?.name ?? active?.name ?? null}
          evidenceCount={evidence.data ? evidence.data.length : null}
          rolesCount={roles.data ? roles.data.length : null}
          resumeStatus={currentResume ? (currentResume.status === 'parsed' ? 'Ready' : currentResume.status) : 'Missing'}
          jdStatus={currentJd ? (currentJd.status === 'parsed' ? 'In use' : currentJd.status) : 'Resume-only'}
        />
      </div>

      {error ? <ErrorState title="Request failed" body={error} className="m-6" /> : null}
      {notice ? (
        <div className="mx-6 mt-4 border border-draft/50 bg-draft-soft/40 px-4 py-2.5">
          <p className="stencil text-[10px] uppercase tracking-[0.12em] text-draft-2">{notice}</p>
        </div>
      ) : null}

      {/* 01 · PROFILES */}
      <ProfileSwitcher
        profiles={profiles}
        activeId={activeId}
        newName={newProfileName}
        onName={setNewProfileName}
        onCreate={() => void onCreateProfile()}
        onSwitch={(id) => void onSwitch(id)}
        busy={createProfile.isPending}
      />

      {activeId == null || loadedProfile == null ? (
        <SheetSection title="Identity">
          <div className="border border-dashed border-ink/25 px-4 py-8 text-center">
            <p className="stencil text-[11px] uppercase tracking-[0.16em] text-ink-3">Select a profile</p>
            <p className="mx-auto mt-2 max-w-md text-[13px] leading-relaxed text-ink-2">
              Create or switch to a profile to see its workspace.
            </p>
          </div>
        </SheetSection>
      ) : (
        <>
          {/* 02 · IDENTITY */}
          <SheetSection
            title="Identity"
            tone={editing ? 'shadow' : 'flat'}
            aside={
              <span className="stencil text-[10px] uppercase tracking-[0.14em] text-ink-2">{loadedProfile.status}</span>
            }
          >
            <dl className="py-1">
              <SpecRow label="Name" value={loadedProfile.name} />
              <SpecRow label="Headline" value={loadedProfile.headline} />
              <SpecRow label="Seniority target" value={loadedProfile.seniority_target ? `${loadedProfile.seniority_target} target` : null} />
              <SpecRow label="Positioning" value={loadedProfile.positioning} />
            </dl>

            {editing ? (
              <div className="mt-4 border border-ink/25 bg-sheet-lit/30 px-4 py-3">
                <div className="flex items-baseline justify-between gap-3">
                  <p className="text-[10px] font-medium uppercase tracking-[0.12em] text-ink-2/70">Revision · identity fields</p>
                  {dirty ? <span className="stencil text-[10px] uppercase tracking-[0.16em] text-redline">Unsaved changes</span> : null}
                </div>
                <div className="mt-3 grid gap-x-8 gap-y-4 sm:grid-cols-2">
                  <label className="block">
                    <span className="mb-1 block text-[10px] font-medium uppercase tracking-[0.12em] text-ink-2/70">Name</span>
                    <input className={`h-9 ${FIELD_CLS}`} placeholder={loadedProfile.name} value={name} onChange={(e) => setName(e.target.value)} />
                  </label>
                  <label className="block">
                    <span className="mb-1 block text-[10px] font-medium uppercase tracking-[0.12em] text-ink-2/70">Seniority target</span>
                    <select className={`h-9 ${FIELD_CLS}`} value={seniority} onChange={(e) => setSeniority(e.target.value)}>
                      <option value="">—</option>
                      {SENIORITY.map((s) => (
                        <option key={s.value} value={s.value}>
                          {s.label}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="block sm:col-span-2">
                    <span className="mb-1 block text-[10px] font-medium uppercase tracking-[0.12em] text-ink-2/70">Headline</span>
                    <input className={`h-9 ${FIELD_CLS}`} placeholder={loadedProfile.headline ?? 'Senior Backend Engineer'} value={headline} onChange={(e) => setHeadline(e.target.value)} />
                  </label>
                  <label className="block sm:col-span-2">
                    <span className="mb-1 block text-[10px] font-medium uppercase tracking-[0.12em] text-ink-2/70">Positioning</span>
                    <textarea
                      className={`min-h-20 resize-y py-2 ${FIELD_CLS}`}
                      placeholder={loadedProfile.positioning ?? 'What makes you the right fit for this path?'}
                      value={positioning}
                      onChange={(e) => setPositioning(e.target.value)}
                    />
                  </label>
                </div>
                <div className="mt-4 flex flex-wrap items-center justify-end gap-2 border-t border-ink/10 pt-3">
                  <Button variant="ghost" size="sm" onClick={() => { setEditing(false); setName(''); setPositioning(''); setHeadline(''); setSeniority('') }}>
                    Cancel
                  </Button>
                  <button
                    type="button"
                    onClick={() => void onSaveProfile()}
                    disabled={updateProfile.isPending}
                    className="stencil flex h-8 items-center justify-between gap-3 border border-draft bg-draft-soft/40 px-3 text-[10px] font-semibold uppercase tracking-[0.14em] text-draft-2 transition-colors hover:bg-draft-soft/70 focus-visible:outline-none focus-visible:shadow-[var(--focus-ring)] disabled:cursor-not-allowed disabled:opacity-45"
                  >
                    <span>{updateProfile.isPending ? 'Saving…' : 'Commit revision'}</span>
                    <span aria-hidden>→</span>
                  </button>
                </div>
              </div>
            ) : (
              <div className="mt-4 flex items-center justify-end border-t border-ink/10 pt-3">
                <Button variant="secondary" size="sm" onClick={() => setEditing(true)}>
                  Edit identity
                </Button>
              </div>
            )}
          </SheetSection>

          {/* 03 · TARGET */}
          <div className="grid lg:grid-cols-12">
            <SheetSection title="Target · competency model" className="lg:col-span-7 lg:border-r">
              {roles.data && roles.data.length === 0 ? (
                <div className="border border-dashed border-ink/25 px-4 py-6 text-center">
                  <p className="stencil text-[10px] uppercase tracking-[0.16em] text-ink-3">No target roles</p>
                  <p className="mx-auto mt-2 max-w-sm text-[12px] leading-relaxed text-ink-2">
                    Add a job description to define this profile's target.
                  </p>
                </div>
              ) : (
                <ol>
                  {roles.data?.map((r, i) => (
                    <li key={r.id} className="grid grid-cols-[2rem_minmax(0,1fr)_auto] items-center gap-x-3 border-b border-ink/5 py-2 last:border-b-0">
                      <StencilNum className="text-[11px] leading-none text-ink-3">{pad2(i + 1)}</StencilNum>
                      <div className="min-w-0">
                        <p className="truncate text-[13px] text-ink">
                          {r.title}
                          {r.seniority ? <span className="text-ink-2"> · {r.seniority}</span> : null}
                        </p>
                        {r.summary ? <p className="mt-0.5 line-clamp-2 text-[11px] leading-relaxed text-ink-2">{r.summary}</p> : null}
                      </div>
                      {r.competencies && r.competencies.length > 0 ? (
                        <span className="stencil shrink-0 text-[10px] uppercase tracking-[0.1em] text-ink-2">{r.competencies.length} competencies</span>
                      ) : null}
                    </li>
                  ))}
                </ol>
              )}
            </SheetSection>

            <SheetSection title="Target · role analysis" tone="shadow" className="lg:col-span-5">
              <p className="py-1 text-[12px] leading-relaxed text-ink-2">
                Paste a job description or upload a JD — Pramya builds the competency model that drives readiness and preparation.
              </p>
              <textarea
                aria-label="Job description text"
                className={`mt-2 min-h-20 resize-y py-2 ${FIELD_CLS}`}
                placeholder="Paste a job description here…"
                value={jdText}
                onChange={(e) => setJdText(e.target.value)}
              />
              <div className="mt-2 flex flex-wrap items-center gap-2">
                <Button onClick={() => void onAnalyzeJd()} disabled={!jdText.trim() || analyzeRole.isPending}>
                  {analyzeRole.isPending ? 'Analyzing…' : 'Analyze JD'}
                </Button>
                <label className="flex items-center gap-2 text-[11px] text-ink-2">
                  <input
                    type="file"
                    accept=".pdf,.docx,.txt,.md"
                    className="cursor-pointer text-[11px] text-ink-3 file:mr-2 file:border file:border-ink/30 file:bg-sheet file:px-2.5 file:py-1 file:text-[11px] file:text-ink-2 file:cursor-pointer"
                    onChange={(e) => {
                      const file = e.target.files?.[0]
                      if (file) void onUploadJd(file)
                    }}
                  />
                  or upload a JD file
                </label>
                {stage?.includes('role') ? <Spinner label={stage} subtle /> : null}
              </div>
            </SheetSection>
          </div>

          {/* 04 · SOURCES */}
          <div className="grid lg:grid-cols-12">
            <SheetSection
              title="Source · resume"
              className="lg:col-span-7 lg:border-r"
              aside={<span className="stencil text-[10px] uppercase tracking-[0.14em] text-ink-2">{resumes.length} on record</span>}
            >
              <p className="py-1 text-[12px] leading-relaxed text-ink-2">
                Choose which version interviews are grounded in. Earlier versions are kept.
              </p>
              {resumes.length === 0 ? (
                <div className="border border-dashed border-ink/25 px-4 py-6 text-center">
                  <p className="stencil text-[10px] uppercase tracking-[0.16em] text-ink-3">No resume yet</p>
                  <p className="mx-auto mt-2 max-w-sm text-[12px] leading-relaxed text-ink-2">
                    Upload a resume (PDF, DOCX, TXT, MD) — it is parsed, indexed, and extracted into this profile's evidence.
                  </p>
                </div>
              ) : (
                <ol>
                  {resumes.map((d, i) => {
                    const isCurrent = d.id === currentResume?.id
                    return (
                      <DocRow
                        key={d.id}
                        index={pad2(i + 1)}
                        filename={d.filename}
                        status={d.status}
                        size={d.size}
                        current={isCurrent}
                        currentLabel="current"
                        actions={
                          isCurrent ? null : (
                            <>
                              <Button
                                variant="secondary"
                                size="sm"
                                disabled={d.status !== 'parsed' || setPreferred.isPending}
                                onClick={() => void setPreferred.mutateAsync({ kind: 'resume', documentId: d.id })}
                              >
                                Make current
                              </Button>
                              <Button
                                variant="ghost"
                                size="sm"
                                disabled={deleteDoc.isPending}
                                onClick={() => {
                                  if (window.confirm(`Delete resume "${d.filename}"? Existing interview records keep their snapshot.`)) {
                                    void deleteDoc.mutateAsync(d.id)
                                  }
                                }}
                              >
                                Delete
                              </Button>
                            </>
                          )
                        }
                      />
                    )
                  })}
                </ol>
              )}
              <UploadZone
                label="Upload resume"
                hint="PDF · DOCX · TXT · MD"
                accept=".pdf,.docx,.txt,.md"
                onFile={(f) => void onUploadResume(f)}
              />
              {stage && !stage.includes('role') ? (
                <div className="mt-3">
                  <Spinner label={stage} subtle />
                </div>
              ) : null}
            </SheetSection>

            <SheetSection
              title="Source · job descriptions"
              tone="shadow"
              className="lg:col-span-5"
              aside={<span className="stencil text-[10px] uppercase tracking-[0.14em] text-ink-2">{jds.length} on record</span>}
            >
              <p className="py-1 text-[12px] leading-relaxed text-ink-2">
                JDs you interview against, deduplicated by content. One is selected for practice.
              </p>
              {jds.length === 0 ? (
                <div className="border border-dashed border-ink/25 px-4 py-6 text-center">
                  <p className="stencil text-[10px] uppercase tracking-[0.16em] text-ink-3">No JD documents</p>
                  <p className="mx-auto mt-2 max-w-sm text-[12px] leading-relaxed text-ink-2">Uploaded JDs appear here, deduplicated by content.</p>
                </div>
              ) : (
                <ol>
                  {jds.map((d, i) => {
                    const isSelected = d.id === currentJd?.id
                    return (
                      <DocRow
                        key={d.id}
                        index={pad2(i + 1)}
                        filename={d.filename}
                        status={d.status}
                        size={d.size}
                        current={isSelected}
                        currentLabel="in use"
                        actions={
                          <>
                            {!isSelected ? (
                              <Button
                                variant="secondary"
                                size="sm"
                                disabled={d.status !== 'parsed' || setPreferred.isPending}
                                onClick={() => void setPreferred.mutateAsync({ kind: 'jd', documentId: d.id })}
                              >
                                Use
                              </Button>
                            ) : null}
                            <Button
                              variant="ghost"
                              size="sm"
                              disabled={deleteDoc.isPending}
                              onClick={() => {
                                if (window.confirm(`Delete JD "${d.filename}"? Existing interview records keep their snapshot.`)) {
                                  void deleteDoc.mutateAsync(d.id)
                                }
                              }}
                            >
                              Delete
                            </Button>
                          </>
                        }
                      />
                    )
                  })}
                </ol>
              )}
              {currentJd ? (
                <Button
                  variant="ghost"
                  size="sm"
                  className="mt-2"
                  disabled={setPreferred.isPending}
                  onClick={() => void setPreferred.mutateAsync({ kind: 'jd', documentId: null })}
                >
                  Use no JD — resume-only mode
                </Button>
              ) : null}
              <UploadZone
                label="Upload JD"
                hint="PDF · DOCX · TXT · MD"
                accept=".pdf,.docx,.txt,.md"
                onFile={(f) => void onUploadJd(f)}
              />
              {stage && !stage.includes('role') ? (
                <div className="mt-3">
                  <Spinner label={stage} subtle />
                </div>
              ) : null}
            </SheetSection>
          </div>

          {/* 05 · EVIDENCE */}
          <SheetSection
            title="Evidence"
            aside={<span className="stencil text-[10px] uppercase tracking-[0.14em] text-ink-2">{evidence.data?.length ?? 0} records</span>}
          >
            <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-3 py-1">
              <p className="max-w-xl text-[13px] leading-relaxed text-ink-2">
                {evidence.data && evidence.data.length === 0
                  ? 'Extract claims from a resume or complete interviews to build this profile\u2019s evidence ledger.'
                  : `${evidence.data?.length ?? 0} evidence records — claims, observations, and demonstrated answers. View and correct them in the ledger.`}
              </p>
              <Link className="stencil text-[10px] uppercase tracking-[0.12em] text-draft underline underline-offset-2 hover:text-draft-2" to="/evidence">
                Open evidence ledger →
              </Link>
            </div>
          </SheetSection>
        </>
      )}

      {/* Revision strip */}
      <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-2 border-t border-ink/25 px-6 pb-4 pt-3">
        <p className="stencil text-[10px] uppercase leading-relaxed tracking-[0.1em] text-ink-2">
          dossier {loadedProfile?.name ?? active?.name ?? '—'} · status {loadedProfile?.status ?? '—'}
          <br />
          drawn {new Date().toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })}
        </p>
        <p className="stencil text-[10px] uppercase leading-relaxed tracking-[0.1em] text-ink-3">
          edits are revisions — each save is a controlled update of this record.
        </p>
      </div>
    </Sheet>
  )
}
