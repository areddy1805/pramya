// Career profile workspace: profile switcher + CRUD, resume management,
// JD/documents, target roles, evidence summary. Every control performs a
// real API operation and renders loading/success/error/empty states from
// server state — no fake local-only success.

import { useMemo, useState } from 'react'
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
  EmptyState,
  ErrorState,
  Field,
  Pill,
  SectionHeading,
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
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [stage, setStage] = useState<string | null>(null)

  const currentResume =
    resumes.find((d) => d.id === active?.preferred_resume_document_id) ??
    resumes[resumes.length - 1] ??
    null
  const currentJd =
    jds.find((d) => d.id === active?.preferred_jd_document_id) ?? jds[jds.length - 1] ?? null
  const canSubmitEdit = activeId != null && Boolean(name.trim())

  async function onSwitch(profileId: number) {
    setError(null)
    setNotice(null)
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
    if (!canSubmitEdit) return
    try {
      await updateProfile.mutateAsync({
        name: name || undefined,
        positioning: positioning || undefined,
        headline: headline || undefined,
        seniority_target: seniority || undefined,
      })
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

  // Render the edit form only after server data for the active profile is known.
  const loadedProfile = activeQuery.data?.profile ?? active

  return (
    <div className="space-y-8">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Career profiles</h1>
        <p className="mt-1 text-sm text-fg-2">
          Each profile is an independent workspace — its own resume, target roles, JDs, and evidence. Switching profiles changes the workspace context; nothing leaks between them.
        </p>
      </header>

      {error ? <ErrorState title="Request failed" body={error} /> : null}
      {notice ? (
        <div className="rounded-xl border border-accent-line bg-accent-soft px-4 py-3 text-sm text-accent">
          {notice}
        </div>
      ) : null}

      {/* Profile switcher + create */}
      <Surface className="p-6">
        <SectionHeading>Profiles</SectionHeading>
        {isLoading ? (
          <Spinner label="Loading profiles…" />
        ) : profiles.length === 0 ? (
          <EmptyState
            title="No profiles yet"
            body="Create your first career profile to start building your workspace."
          />
        ) : (
          <div className="space-y-2">
            {profiles.map((p) => (
              <div
                key={p.id}
                className={`flex items-center justify-between rounded-lg border px-4 py-3 ${
                  p.id === activeId ? 'border-accent-line bg-accent-soft' : 'border-line bg-canvas'
                }`}
              >
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium text-fg">{p.name}</p>
                  <p className="truncate text-xs text-fg-3">
                    {p.headline || p.positioning || p.slug || `Profile #${p.id}`}
                  </p>
                </div>
                <div className="flex shrink-0 items-center gap-2">
                  {p.id === activeId ? (
                    <Pill tone="accent">Active</Pill>
                  ) : (
                    <Button variant="secondary" size="sm" onClick={() => void onSwitch(p.id)}>
                      Switch
                    </Button>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
        <div className="mt-4 flex items-center gap-2">
          <TextInput
            className="max-w-xs"
            placeholder="New profile name (e.g. AI Engineer)"
            value={newProfileName}
            onChange={(e) => setNewProfileName(e.target.value)}
          />
          <Button onClick={() => void onCreateProfile()} disabled={!newProfileName.trim() || createProfile.isPending}>
            {createProfile.isPending ? 'Creating…' : 'Create profile'}
          </Button>
          {activeId != null && profiles.length > 1 ? (
            <Button variant="danger" size="sm" onClick={() => void onDeleteProfile()} disabled={deleteProfile.isPending}>
              Delete
            </Button>
          ) : null}
        </div>
      </Surface>

      {activeId == null || loadedProfile == null ? (
        <Surface className="p-6">
          <EmptyState title="Select a profile" body="Create or switch to a profile to see its workspace." />
        </Surface>
      ) : (
        <>
          {/* Profile identity */}
          <Surface className="p-6">
            <SectionHeading aside={<Pill tone={loadedProfile.status === 'active' ? 'ok' : 'neutral'}>{loadedProfile.status}</Pill>}>
              {loadedProfile.name}
            </SectionHeading>
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
            <div className="mt-4 grid gap-4">
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
            <div className="mt-4">
              <Button onClick={() => void onSaveProfile()} disabled={!canSubmitEdit || updateProfile.isPending}>
                {updateProfile.isPending ? 'Saving…' : 'Save profile'}
              </Button>
            </div>
          </Surface>

          {/* Resume */}
          <Surface className="p-6">
            <SectionHeading
              aside={
                currentResume ? (
                  <Pill tone={currentResume.status === 'parsed' ? 'ok' : 'warn'}>{currentResume.status}</Pill>
                ) : undefined
              }
            >
              Resume
            </SectionHeading>
            <p className="mb-4 text-sm text-fg-2">
              One current resume per profile — choose which version interviews are grounded in. Earlier versions are kept.
            </p>
            {resumes.length === 0 ? (
              <EmptyState title="No resume yet" body="Upload a resume (PDF, DOCX, TXT, MD) — it is parsed, indexed, and extracted into this profile's evidence." />
            ) : (
              <div className="mb-4 space-y-2">
                {resumes.map((d) => {
                  const isCurrent = d.id === currentResume?.id
                  return (
                    <div key={d.id} className="flex items-center justify-between gap-3 rounded-lg border border-line bg-canvas px-4 py-3">
                      <div className="min-w-0">
                        <p className="truncate text-sm font-medium text-fg">
                          {d.filename} {isCurrent ? <span className="text-xs text-accent">· current</span> : null}
                        </p>
                        <p className="text-xs text-fg-3">{d.size.toLocaleString()} bytes · {d.status}</p>
                      </div>
                      <div className="flex shrink-0 items-center gap-2">
                        {isCurrent ? (
                          <Pill tone="ok">current</Pill>
                        ) : (
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
                        )}
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
            <label className="inline-flex cursor-pointer">
              <span className="rounded-lg border border-line bg-surface px-4 py-2 text-sm font-medium text-fg transition-colors hover:border-fg-3 hover:bg-surface-2">
                {currentResume ? 'Replace resume' : 'Upload resume'}
              </span>
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
          </Surface>

          {/* Target roles */}
          <Surface className="p-6">
            <SectionHeading aside={roles.data && roles.data.length > 0 ? <Pill tone="ok">{roles.data.length} roles</Pill> : undefined}>
              Target roles
            </SectionHeading>
            <p className="mb-4 text-sm text-fg-2">
              Paste a job description or upload a JD. Pramya builds the competency model that drives readiness and preparation for this profile.
            </p>
            {roles.data && roles.data.length === 0 ? (
              <EmptyState title="No target roles" body="Add a job description to define this profile's target." />
            ) : (
              <div className="mb-4 space-y-2">
                {roles.data?.map((r) => (
                  <div key={r.id} className="rounded-lg border border-line bg-canvas px-4 py-3">
                    <p className="text-sm font-medium text-fg">{r.title} {r.seniority ? `· ${r.seniority}` : ''}</p>
                    {r.summary ? <p className="mt-0.5 text-xs text-fg-2">{r.summary}</p> : null}
                    {r.competencies && r.competencies.length > 0 ? (
                      <p className="mt-1 text-xs text-fg-3">{r.competencies.length} competencies</p>
                    ) : null}
                  </div>
                ))}
              </div>
            )}
            <TextArea
              className="min-h-24"
              placeholder="Paste a job description here…"
              value={jdText}
              onChange={(e) => setJdText(e.target.value)}
            />
            <div className="mt-3 flex flex-wrap items-center gap-3">
              {currentJd ? (
                <Button
                  variant="ghost"
                  size="sm"
                  disabled={setPreferred.isPending}
                  onClick={() => void setPreferred.mutateAsync({ kind: 'jd', documentId: null })}
                >
                  Use no JD (resume-only mode)
                </Button>
              ) : null}
              <Button onClick={() => void onAnalyzeJd()} disabled={!jdText.trim() || analyzeRole.isPending}>
                {analyzeRole.isPending ? 'Analyzing…' : 'Analyze JD'}
              </Button>
              <label className="text-sm text-fg-2">
                or{' '}
                <input
                  type="file"
                  accept=".pdf,.docx,.txt,.md"
                  className="cursor-pointer text-xs text-fg-2 file:mr-2 file:rounded-lg file:border-0 file:bg-track file:px-3 file:py-1.5 file:text-xs file:font-medium file:cursor-pointer"
                  onChange={(e) => {
                    const file = e.target.files?.[0]
                    if (file) void onUploadJd(file)
                  }}
                />
                upload a JD document
              </label>
              {stage?.includes('role') ? <div className="mt-3"><Spinner label={stage} /></div> : null}
            </div>
          </Surface>

          {/* Documents / JDs */}
          <Surface className="p-6">
            <SectionHeading aside={jds.length > 0 ? <Pill>{jds.length} documents</Pill> : undefined}>
              Documents & JDs
            </SectionHeading>
            {jds.length === 0 ? (
              <EmptyState title="No JD documents" body="Uploaded JDs appear here, deduplicated by content." />
            ) : (
              <div className="space-y-2">
                {jds.map((d) => {
                  const isSelected = d.id === currentJd?.id
                  return (
                    <div key={d.id} className="flex items-center justify-between gap-3 rounded-lg border border-line bg-canvas px-4 py-3">
                      <div className="min-w-0">
                        <p className="truncate text-sm font-medium text-fg">
                          {d.filename} {isSelected ? <span className="text-xs text-accent">· in use</span> : null}
                        </p>
                        <p className="text-xs text-fg-3">{d.size.toLocaleString()} bytes · {d.status}</p>
                      </div>
                      <div className="flex shrink-0 items-center gap-2">
                        {isSelected ? (
                          <Pill tone="accent">in use</Pill>
                        ) : (
                          <Button
                            variant="secondary"
                            size="sm"
                            disabled={d.status !== 'parsed' || setPreferred.isPending}
                            onClick={() => void setPreferred.mutateAsync({ kind: 'jd', documentId: d.id })}
                          >
                            Use for interviews
                          </Button>
                        )}
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
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </Surface>

          {/* Evidence summary */}
          <Surface className="p-6">
            <SectionHeading aside={evidence.data ? <Pill>{evidence.data.length} records</Pill> : undefined}>
              Evidence
            </SectionHeading>
            {evidence.data && evidence.data.length === 0 ? (
              <EmptyState title="No evidence yet" body="Extract claims from a resume or complete interviews to build this profile's evidence ledger." />
            ) : (
              <p className="text-sm text-fg-2">
                {evidence.data?.length ?? 0} evidence records in this profile. View and correct them in the Evidence ledger.
              </p>
            )}
          </Surface>
        </>
      )}
    </div>
  )
}
