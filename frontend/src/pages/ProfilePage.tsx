// Career profile workspace: profile switcher + CRUD, resume management,
// JD/documents, target roles, evidence summary. Every control performs a
// real API operation and renders loading/success/error/empty states from
// server state — no fake local-only success.

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
import {
  Button,
  DocumentRow,
  EmptyState,
  ErrorState,
  Field,
  Micro,
  Pill,
  Select,
  Spinner,
  Surface,
  TextArea,
  TextInput,
} from '../components/ui'

export function ProfilePage() {
  const userId = DEFAULT_USER_ID
  const { active, activeId, profiles, isLoading } = useResolvedProfile(userId)
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
    <div className="space-y-8">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <Micro>Workspace</Micro>
          <h1 className="mt-1 text-xl font-semibold tracking-tight">Career profiles</h1>
          <p className="mt-1 max-w-xl text-sm leading-relaxed text-fg-2">
            Each profile is an independent workspace — its own resume, target roles, JDs, and evidence. Nothing leaks between them.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {activeId != null && profiles.length > 1 ? (
            <Button variant="danger" size="sm" onClick={() => void onDeleteProfile()} disabled={deleteProfile.isPending}>
              Delete profile
            </Button>
          ) : null}
          <Button size="sm" onClick={() => void onCreateProfile()} disabled={!newProfileName.trim() || createProfile.isPending}>
            {createProfile.isPending ? 'Creating…' : 'New profile'}
          </Button>
        </div>
      </header>

      {error ? <ErrorState title="Request failed" body={error} /> : null}
      {notice ? (
        <div className="rounded-[var(--r-md)] border border-accent-line bg-accent-soft px-4 py-2.5 text-sm text-accent">
          {notice}
        </div>
      ) : null}

      {/* Profile list — compact selector row */}
      <Surface className="p-4" tone="inset">
        <div className="flex flex-wrap items-center gap-2">
          <Micro className="mr-2">Profiles</Micro>
          {isLoading ? <Spinner label="Loading" subtle /> : null}
          {profiles.map((p) => (
            <button
              key={p.id}
              type="button"
              onClick={() => void onSwitch(p.id)}
              className={`rounded-[var(--r-md)] border px-3 py-1.5 text-[13px] font-medium transition-colors ${
                p.id === activeId
                  ? 'border-accent-line bg-accent-soft text-accent'
                  : 'border-line bg-surface text-fg-2 hover:border-fg-3 hover:text-fg'
              }`}
            >
              {p.name}
            </button>
          ))}
          <span className="mx-2 h-4 w-px bg-line" aria-hidden />
          <input
            aria-label="New profile name"
            className="w-44 rounded-[var(--r-md)] border border-line bg-surface px-2.5 py-1.5 text-[13px] text-fg placeholder:text-fg-disabled focus:border-accent focus:outline-none focus:shadow-[var(--focus-ring)]"
            placeholder="New profile name…"
            value={newProfileName}
            onChange={(e) => setNewProfileName(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') void onCreateProfile()
            }}
          />
        </div>
      </Surface>

      {activeId == null || loadedProfile == null ? (
        <EmptyState title="Select a profile" body="Create or switch to a profile to see its workspace." />
      ) : (
        <>
          {/* Identity band — on canvas, not in a card */}
          <div className="flex flex-wrap items-start justify-between gap-4 border-b border-line pb-5">
            <div className="min-w-0">
              <div className="flex items-center gap-2.5">
                <h2 className="text-lg font-semibold tracking-tight text-fg">{loadedProfile.name}</h2>
                <Pill tone={loadedProfile.status === 'active' ? 'ok' : 'neutral'}>{loadedProfile.status}</Pill>
              </div>
              {loadedProfile.positioning ? <p className="mt-0.5 text-sm text-fg-2">{loadedProfile.positioning}</p> : null}
              <p className="mt-0.5 text-xs text-fg-3">
                {loadedProfile.headline ? `${loadedProfile.headline} · ` : ''}
                {loadedProfile.seniority_target ? `${loadedProfile.seniority_target} target` : 'no seniority target'}
              </p>
            </div>
            <div className="flex items-center gap-2">
              {editing ? (
                <>
                  <Button size="sm" onClick={() => void onSaveProfile()} disabled={updateProfile.isPending}>
                    {updateProfile.isPending ? 'Saving…' : 'Save'}
                  </Button>
                  <Button variant="ghost" size="sm" onClick={() => setEditing(false)}>Cancel</Button>
                </>
              ) : (
                <Button variant="secondary" size="sm" onClick={() => setEditing(true)}>Edit identity</Button>
              )}
            </div>
          </div>

          {editing ? (
            <Surface className="p-5">
              <Micro className="mb-4">Identity</Micro>
              <div className="grid gap-4 sm:grid-cols-2">
                <Field label="Name">
                  <TextInput placeholder={loadedProfile.name} value={name} onChange={(e) => setName(e.target.value)} />
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
              <div className="mt-4 space-y-4">
                <Field label="Headline" hint="One line that captures where you are.">
                  <TextInput placeholder={loadedProfile.headline ?? 'Senior Backend Engineer'} value={headline} onChange={(e) => setHeadline(e.target.value)} />
                </Field>
                <Field label="Positioning" hint="How you position yourself for this target.">
                  <TextArea
                    className="min-h-20"
                    placeholder={loadedProfile.positioning ?? 'What makes you the right fit for this path?'}
                    value={positioning}
                    onChange={(e) => setPositioning(e.target.value)}
                  />
                </Field>
              </div>
            </Surface>
          ) : null}

          <div className="grid grid-cols-[minmax(0,1fr)] gap-8 lg:grid-cols-2">
            {/* Core context */}
            <div className="space-y-8">
              {/* Resume workspace */}
              <section>
                <div className="mb-2 flex items-center justify-between gap-3">
                  <Micro>Resume</Micro>
                  {currentResume ? (
                    <Pill tone={currentResume.status === 'parsed' ? 'ok' : 'warn'}>{currentResume.status}</Pill>
                  ) : null}
                </div>
                <p className="mb-3 text-[13px] leading-relaxed text-fg-3">
                  Choose which version interviews are grounded in. Earlier versions are kept.
                </p>
                {resumes.length === 0 ? (
                  <EmptyState title="No resume yet" body="Upload a resume (PDF, DOCX, TXT, MD) — it is parsed, indexed, and extracted into this profile's evidence." />
                ) : (
                  <div className="space-y-1">
                    {resumes.map((d) => {
                      const isCurrent = d.id === currentResume?.id
                      return (
                        <DocumentRow
                          key={d.id}
                          filename={d.filename}
                          statusTone={d.status === 'parsed' ? 'ok' : d.status === 'failed' ? 'danger' : 'warn'}
                          meta={`${d.size.toLocaleString()} bytes · ${d.status}${isCurrent ? ' · used in interviews' : ''}`}
                          selected={isCurrent}
                          selectedLabel="current"
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
                  </div>
                )}
                <label className="drop-zone mt-3 flex cursor-pointer items-center justify-between gap-3 px-4 py-3">
                  <span className="text-[13px] font-medium text-fg-2">Upload resume</span>
                  <span className="text-xs text-fg-3">PDF · DOCX · TXT · MD</span>
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
                {stage && !stage.includes('role') ? <div className="mt-3"><Spinner label={stage} /></div> : null}
              </section>

              {/* Target roles */}
              <section>
                <Micro className="mb-2">Target roles</Micro>
                <p className="mb-3 text-[13px] leading-relaxed text-fg-3">
                  Paste a job description or upload a JD. Pramya builds the competency model that drives readiness and preparation.
                </p>
                {roles.data && roles.data.length === 0 ? (
                  <EmptyState title="No target roles" body="Add a job description to define this profile's target." />
                ) : (
                  <div className="divide-y divide-line border-y border-line">
                    {roles.data?.map((r) => (
                      <div key={r.id} className="flex items-center justify-between gap-3 py-2.5">
                        <div className="min-w-0">
                          <p className="text-sm font-medium text-fg">{r.title} {r.seniority ? `· ${r.seniority}` : ''}</p>
                          {r.summary ? <p className="mt-0.5 line-clamp-2 text-xs text-fg-3">{r.summary}</p> : null}
                        </div>
                        {r.competencies && r.competencies.length > 0 ? (
                          <span className="shrink-0 text-xs text-fg-3">{r.competencies.length} competencies</span>
                        ) : null}
                      </div>
                    ))}
                  </div>
                )}
                <div className="mt-3 space-y-2">
                  <TextArea
                    className="min-h-20"
                    placeholder="Paste a job description here…"
                    value={jdText}
                    onChange={(e) => setJdText(e.target.value)}
                  />
                  <div className="flex flex-wrap items-center gap-2">
                    <Button onClick={() => void onAnalyzeJd()} disabled={!jdText.trim() || analyzeRole.isPending}>
                      {analyzeRole.isPending ? 'Analyzing…' : 'Analyze JD'}
                    </Button>
                    <label className="flex items-center gap-2 text-[13px] text-fg-2">
                      <input
                        type="file"
                        accept=".pdf,.docx,.txt,.md"
                        className="cursor-pointer text-xs text-fg-3 file:mr-2 file:rounded-[var(--r-sm)] file:border-0 file:bg-track file:px-2.5 file:py-1 file:text-xs file:font-medium file:cursor-pointer"
                        onChange={(e) => {
                          const file = e.target.files?.[0]
                          if (file) void onUploadJd(file)
                        }}
                      />
                      or upload a JD file
                    </label>
                    {stage?.includes('role') ? <Spinner label={stage} subtle /> : null}
                  </div>
                </div>
              </section>
            </div>

            {/* Supporting context */}
            <div className="space-y-8">
              {/* JD documents */}
              <section>
                <div className="mb-2 flex items-center justify-between gap-3">
                  <Micro>Job descriptions</Micro>
                  {jds.length > 0 ? <span className="text-xs text-fg-3">{jds.length}</span> : null}
                </div>
                <p className="mb-3 text-[13px] leading-relaxed text-fg-3">
                  JDs you interview against, deduplicated by content. One is selected for practice.
                </p>
                {jds.length === 0 ? (
                  <EmptyState title="No JD documents" body="Uploaded JDs appear here, deduplicated by content." />
                ) : (
                  <div className="space-y-1">
                    {jds.map((d) => {
                      const isSelected = d.id === currentJd?.id
                      return (
                        <DocumentRow
                          key={d.id}
                          filename={d.filename}
                          statusTone={d.status === 'parsed' ? 'ok' : d.status === 'failed' ? 'danger' : 'warn'}
                          meta={`${d.size.toLocaleString()} bytes · ${d.status}`}
                          selected={isSelected}
                          selectedLabel="in use"
                          actions={
                            <>
                              {!isSelected ? (
                                <Button
                                  variant="secondary"
                                  size="sm"
                                  disabled={d.status !== 'parsed' || setPreferred.isPending}
                                  onClick={() => void setPreferred.mutateAsync({ kind: 'jd', documentId: d.id })}
                                >
                                  Use for interviews
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
                  </div>
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
                <label className="drop-zone mt-3 flex cursor-pointer items-center justify-between gap-3 px-4 py-3">
                  <span className="text-[13px] font-medium text-fg-2">Upload JD</span>
                  <span className="text-xs text-fg-3">PDF · DOCX · TXT · MD</span>
                  <input
                    type="file"
                    accept=".pdf,.docx,.txt,.md"
                    className="sr-only"
                    onChange={(e) => {
                      const file = e.target.files?.[0]
                      if (file) void onUploadJd(file)
                    }}
                  />
                </label>
                {stage && !stage.includes('role') ? <div className="mt-3"><Spinner label={stage} /></div> : null}
              </section>

              {/* Evidence */}
              <section>
                <div className="mb-2 flex items-center justify-between gap-3">
                  <Micro>Evidence</Micro>
                  {evidence.data ? <span className="text-xs text-fg-3">{evidence.data.length} records</span> : null}
                </div>
                {evidence.data && evidence.data.length === 0 ? (
                  <EmptyState title="No evidence yet" body="Extract claims from a resume or complete interviews to build this profile's evidence ledger." />
                ) : (
                  <p className="text-[13px] leading-relaxed text-fg-2">
                    {evidence.data?.length ?? 0} evidence records — claims, observations, and demonstrated answers. View and correct them in the ledger.
                  </p>
                )}
                <Link className="mt-2 inline-block text-[13px] font-medium text-accent hover:underline" to="/evidence">
                  Open evidence ledger →
                </Link>
              </section>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
