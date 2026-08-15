// TanStack Query hooks per backend resource.
// Server state lives here; components stay thin.

import { useEffect } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, qs } from '../lib/api'
import { useProfileStore } from '../stores/profile'
import type {
  ActiveProfile,
  CandidateProfile,
  CareerProfile,
  Document,
  DocumentIndexResult,
  DocumentUploadResult,
  Evidence,
  ExtractionResult,
  Health,
  InterviewContext,
  InterviewSession,
  ModelsStatus,
  PreparationItem,
  ProgressSummary,
  Question,
  Readiness,
  Report,
  Role,
  Story,
} from '../lib/types'

export const DEFAULT_USER_ID = 1

// --- career profiles ---------------------------------------------------------

export function useProfiles(userId: number) {
  return useQuery({
    queryKey: ['profiles', userId],
    queryFn: () => api.get<CareerProfile[]>(`/api/v1/candidates/${userId}/profiles`),
    retry: false,
  })
}

export function useCreateProfile(userId: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: {
      name: string
      slug?: string
      positioning?: string
      status?: string
      seniority_target?: string
      headline?: string
      timezone?: string
    }) => api.post<CareerProfile>(`/api/v1/candidates/${userId}/profiles`, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['profiles', userId] }),
  })
}

export function useUpdateProfile(userId: number, profileId: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: {
      name?: string
      slug?: string
      positioning?: string
      status?: string
      seniority_target?: string
      headline?: string
      timezone?: string
    }) => api.patch<CareerProfile>(`/api/v1/candidates/${userId}/profiles/${profileId}`, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['profiles', userId] })
      qc.invalidateQueries({ queryKey: ['active-profile', userId] })
    },
  })
}

export function useDeleteProfile(userId: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (profileId: number) =>
      api.delete(`/api/v1/candidates/${userId}/profiles/${profileId}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['profiles', userId] }),
  })
}

export function useActiveProfile(userId: number) {
  return useQuery({
    queryKey: ['active-profile', userId],
    queryFn: () => api.get<ActiveProfile>(`/api/v1/candidates/${userId}/active-profile`),
    retry: false,
  })
}

/** Resolved interview context for the selected profile — server-authoritative. */
export function useInterviewContext(userId: number, profileId: number | null) {
  return useQuery({
    queryKey: ['interview-context', userId, profileId],
    queryFn: () =>
      api.get<InterviewContext>(`/api/v1/candidates/${userId}/profiles/${profileId}/context`),
    enabled: profileId !== null && profileId > 0,
    retry: false,
  })
}

export function useSetActiveProfile(userId: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (profileId: number) =>
      api.put<ActiveProfile>(`/api/v1/candidates/${userId}/active-profile`, { profile_id: profileId }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['active-profile', userId] })
      qc.invalidateQueries({ queryKey: ['profiles', userId] })
      qc.invalidateQueries()
    },
  })
}

/**
 * Effective active profile id for a user: server truth first, then the
 * user's first profile, then null (no profiles yet). Keeps the zustand
 * mirror in sync so the switcher reflects the persisted selection.
 */
export function useResolvedProfile(userId: number): {
  active: CareerProfile | null
  activeId: number | null
  profiles: CareerProfile[]
  isLoading: boolean
} {
  const profilesQuery = useProfiles(userId)
  const activeQuery = useActiveProfile(userId)
  const setActiveProfile = useProfileStore((s) => s.setActiveProfile)

  const profiles = profilesQuery.data ?? []
  let active: CareerProfile | null = activeQuery.data?.profile ?? null
  if (!active && profiles.length > 0) {
    active = profiles[0]
  }
  const activeId = active?.id ?? null

  useEffect(() => {
    if (userId > 0 && activeId != null) {
      setActiveProfile(userId, activeId)
    }
  }, [userId, activeId, setActiveProfile])

  return {
    active,
    activeId,
    profiles,
    isLoading: profilesQuery.isLoading || activeQuery.isLoading,
  }
}

export function useHealth() {
  return useQuery({ queryKey: ['health'], queryFn: () => api.get<Health>('/api/v1/health') })
}

// --- candidate ---------------------------------------------------------------

export function useCandidate(userId: number) {
  return useQuery({
    queryKey: ['candidate', userId],
    queryFn: () => api.get<CandidateProfile>(`/api/v1/candidates/${userId}`),
    retry: false,
  })
}

export function useCreateCandidate() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (profile: { seniority_target?: string; headline?: string; timezone?: string }) =>
      api.post<CandidateProfile>('/api/v1/candidates', { user_id: DEFAULT_USER_ID, ...profile }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['candidate'] }),
  })
}

export function useUpdateCandidate(userId: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (patch: { seniority_target?: string; headline?: string; timezone?: string }) =>
      api.patch<CandidateProfile>(`/api/v1/candidates/${userId}`, patch),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['candidate', userId] }),
  })
}

// --- documents ---------------------------------------------------------------

export function useDocuments(userId: number, profileId: number | null, kind?: string) {
  return useQuery({
    queryKey: ['documents', userId, profileId, kind ?? 'all'],
    queryFn: () =>
      api.get<Document[]>(`/api/v1/documents${qs({ user_id: userId, profile_id: profileId, kind })}`),
    enabled: profileId !== null && profileId > 0,
  })
}

export function useUploadDocument() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({
      userId,
      profileId,
      kind,
      file,
    }: {
      userId: number
      profileId: number
      kind: string
      file: File
    }) => {
      const form = new FormData()
      form.append('user_id', String(userId))
      form.append('profile_id', String(profileId))
      form.append('kind', kind)
      form.append('file', file)
      return api.upload<DocumentUploadResult>('/api/v1/documents', form)
    },
    onSuccess: (_d, vars) =>
      qc.invalidateQueries({ queryKey: ['documents', vars.userId, vars.profileId] }),
  })
}

export function useIndexDocument() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({
      userId,
      profileId,
      documentId,
    }: {
      userId: number
      profileId: number
      documentId: number
    }) =>
      api.post<DocumentIndexResult>(
        `/api/v1/documents/${documentId}/index${qs({ user_id: userId, profile_id: profileId })}`,
      ),
    onSuccess: (_d, vars) =>
      qc.invalidateQueries({ queryKey: ['documents', vars.userId, vars.profileId] }),
  })
}

export function useDeleteDocument(userId: number, profileId: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (documentId: number) =>
      api.delete(`/api/v1/documents/${documentId}${qs({ user_id: userId, profile_id: profileId })}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['documents', userId, profileId] }),
  })
}

// --- evidence ----------------------------------------------------------------

export function useEvidence(userId: number, profileId: number | null, status?: string) {
  return useQuery({
    queryKey: ['evidence', userId, profileId, status ?? 'all'],
    queryFn: () =>
      api.get<Evidence[]>(
        `/api/v1/candidates/${userId}/evidence${qs({ profile_id: profileId, status })}`,
      ),
    enabled: profileId !== null && profileId > 0,
  })
}

export function useExtractResume(userId: number, profileId: number | null) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ documentId }: { documentId: number }) =>
      api.post<ExtractionResult>(
        `/api/v1/candidates/${userId}/extract${qs({ document_id: documentId, profile_id: profileId })}`,
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['evidence'] })
      qc.invalidateQueries({ queryKey: ['documents'] })
    },
  })
}

export function usePatchEvidence(userId: number, profileId: number | null) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({
      evidenceId,
      patch,
    }: {
      evidenceId: number
      patch: { status?: string; strength?: number; notes?: string }
    }) =>
      api.patch<Evidence>(
        `/api/v1/candidates/${userId}/evidence/${evidenceId}${qs({ profile_id: profileId })}`,
        patch,
      ),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['evidence'] }),
  })
}

// --- roles -------------------------------------------------------------------

export function useRoles(userId: number, profileId: number | null) {
  return useQuery({
    queryKey: ['roles', userId, profileId],
    queryFn: () =>
      api.get<Role[]>(`/api/v1/roles${qs({ user_id: userId, profile_id: profileId })}`),
    enabled: profileId !== null && profileId > 0,
  })
}

export function useAnalyzeRole() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: {
      user_id: number
      profile_id?: number
      jd_text: string
      source_document_id?: number
    }) => api.post<Role>('/api/v1/roles/analyze', body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['roles'] }),
  })
}

// --- interviews --------------------------------------------------------------

export function useInterviews(userId: number, profileId: number | null = null) {
  return useQuery({
    queryKey: ['interviews', userId, profileId],
    queryFn: () =>
      api.get<InterviewSession[]>(`/api/v1/interviews${qs({ user_id: userId, profile_id: profileId })}`),
  })
}

export function useInterview(interviewId: number, userId: number) {
  return useQuery({
    queryKey: ['interview', interviewId],
    queryFn: () =>
      api.get<InterviewSession>(`/api/v1/interviews/${interviewId}${qs({ user_id: userId })}`),
    refetchInterval: 5000,
    enabled: interviewId > 0,
  })
}

export function useCreateInterview() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: {
      user_id: number
      kind: string
      role_id?: number
      profile_id?: number
      duration_minutes: number
      focus_competency_ids: number[]
      mode: string
      style?: string
    }) => api.post<InterviewSession>('/api/v1/interviews', body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['interviews'] }),
  })
}

export function useInterviewAction() {
  const qc = useQueryClient()
  const base = (id: number) => `/api/v1/interviews/${id}`
  const invalidate = (id: number) => {
    qc.invalidateQueries({ queryKey: ['interview', id] })
    qc.invalidateQueries({ queryKey: ['interviews'] })
  }
  return {
    begin: useMutation({
      mutationFn: ({ interviewId: id, userId }: { interviewId: number; userId: number }) =>
        api.post<InterviewSession>(`${base(id)}/begin${qs({ user_id: userId })}`),
      onSuccess: (_d, vars) => invalidate(vars.interviewId),
    }),
    nextQuestion: useMutation({
      mutationFn: ({ interviewId: id, userId }: { interviewId: number; userId: number }) =>
        api.post<Question>(`${base(id)}/questions${qs({ user_id: userId })}`),
      onSuccess: (_d, vars) => invalidate(vars.interviewId),
    }),
    answer: useMutation({
      mutationFn: ({
        interviewId: id,
        userId,
        questionId,
        text,
        key,
      }: {
        interviewId: number
        userId: number
        questionId: number
        text: string
        key?: string
      }) =>
        api.post(`${base(id)}/answers${qs({ user_id: userId })}`, {
          question_id: questionId,
          answer_text: text,
          idempotency_key: key,
          mode: 'text',
        }),
      onSuccess: (_d, vars) => invalidate(vars.interviewId),
    }),
    hint: useMutation({
      mutationFn: ({ interviewId: id, userId, questionId }: { interviewId: number; userId: number; questionId: number }) =>
        api.post<{ hint: string }>(`${base(id)}/hint${qs({ user_id: userId, question_id: questionId })}`),
      onSuccess: (_d, vars) => invalidate(vars.interviewId),
    }),
    pause: useMutation({
      mutationFn: ({ interviewId: id, userId }: { interviewId: number; userId: number }) => api.post(`${base(id)}/pause${qs({ user_id: userId })}`),
      onSuccess: (_d, vars) => invalidate(vars.interviewId),
    }),
    resume: useMutation({
      mutationFn: ({ interviewId: id, userId }: { interviewId: number; userId: number }) => api.post(`${base(id)}/resume${qs({ user_id: userId })}`),
      onSuccess: (_d, vars) => invalidate(vars.interviewId),
    }),
    stop: useMutation({
      mutationFn: ({ interviewId: id, userId }: { interviewId: number; userId: number }) => api.post(`${base(id)}/stop${qs({ user_id: userId })}`),
      onSuccess: (_d, vars) => invalidate(vars.interviewId),
    }),
    cancel: useMutation({
      mutationFn: ({ interviewId: id, userId }: { interviewId: number; userId: number }) => api.post(`${base(id)}/cancel${qs({ user_id: userId })}`),
      onSuccess: (_d, vars) => invalidate(vars.interviewId),
    }),
  }
}

export function useReport(interviewId: number, userId: number, enabled: boolean) {
  return useQuery({
    queryKey: ['report', interviewId],
    queryFn: () =>
      api.get<Report>(`/api/v1/interviews/${interviewId}/report${qs({ user_id: userId })}`),
    enabled,
    retry: false,
  })
}

export interface TranscriptTurn {
  seq: number
  kind: string
  question_id?: number | null
  question?: string | null
  answer?: string | null
  evaluation_overall?: number | null
  hints_used?: number
}

export interface Transcript {
  interview_id: number
  turns: TranscriptTurn[]
}

export function useTranscript(interviewId: number, userId: number, enabled: boolean) {
  return useQuery({
    queryKey: ['transcript', interviewId],
    queryFn: () =>
      api.get<Transcript>(`/api/v1/interviews/${interviewId}/transcript${qs({ user_id: userId })}`),
    enabled,
    retry: false,
  })
}

export interface Debrief {
  id: number
  user_id: number
  company: string
  role?: string | null
  round?: string | null
  questions?: Record<string, unknown>[] | null
  feedback?: string | null
  result?: string | null
  analysis?: Record<string, unknown> | null
  created_at?: string
}

export function useDebriefs(userId: number) {
  return useQuery({
    queryKey: ['debriefs', userId],
    queryFn: () => api.get<Debrief[]>(`/api/v1/debriefs${qs({ user_id: userId })}`),
    retry: false,
  })
}

export function useCreateDebrief() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: Record<string, unknown>) => api.post<Debrief>('/api/v1/debriefs', body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['debriefs'] }),
  })
}

export function useAnalyzeDebrief() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      api.post<Debrief>('/api/v1/debriefs/analyze', body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['debriefs'] }),
  })
}

// --- readiness / preparation / progress --------------------------------------

export function useReadiness(userId: number, profileId: number | null = null) {
  return useQuery({
    queryKey: ['readiness', userId, profileId],
    queryFn: () =>
      api.get<Readiness>(`/api/v1/readiness/latest${qs({ user_id: userId, profile_id: profileId })}`),
    retry: false,
  })
}

export function useComputeReadiness(userId: number, profileId: number | null = null) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (roleId?: number) =>
      api.post<Readiness>(`/api/v1/readiness${qs({ user_id: userId, role_id: roleId, profile_id: profileId })}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['readiness'] })
      qc.invalidateQueries({ queryKey: ['preparation'] })
    },
  })
}

export function usePreparation(userId: number, profileId: number | null = null) {
  return useQuery({
    queryKey: ['preparation', userId, profileId],
    queryFn: () =>
      api.get<PreparationItem[]>(`/api/v1/preparation${qs({ user_id: userId, profile_id: profileId })}`),
  })
}

export function useRegeneratePreparation(userId: number, profileId: number | null = null) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () =>
      api.post<PreparationItem[]>(
        `/api/v1/preparation/regenerate${qs({ user_id: userId, profile_id: profileId })}`,
      ),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['preparation'] }),
  })
}

export function useProgress(userId: number, profileId: number | null = null) {
  return useQuery({
    queryKey: ['progress', userId, profileId],
    queryFn: () =>
      api.get<ProgressSummary>(`/api/v1/progress${qs({ user_id: userId, profile_id: profileId })}`),
  })
}

// --- models / stories --------------------------------------------------------

export function useModelsStatus() {
  return useQuery({
    queryKey: ['models-status'],
    queryFn: () => api.get<ModelsStatus>('/api/v1/models/status'),
    refetchInterval: 30_000,
  })
}

export function useStories(userId: number) {
  return useQuery({
    queryKey: ['stories', userId],
    queryFn: () => api.get<Story[]>(`/api/v1/stories${qs({ user_id: userId })}`),
  })
}

export function useCreateStory() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (story: Partial<Story> & { user_id: number }) =>
      api.post<Story>('/api/v1/stories', story),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['stories'] }),
  })
}
