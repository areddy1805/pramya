// TanStack Query hooks per backend resource.
// Server state lives here; components stay thin.

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, qs } from '../lib/api'
import type {
  CandidateProfile,
  Document,
  DocumentIndexResult,
  Evidence,
  ExtractionResult,
  Health,
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

export function useDocuments(userId: number, kind?: string) {
  return useQuery({
    queryKey: ['documents', userId, kind ?? 'all'],
    queryFn: () =>
      api.get<Document[]>(`/api/v1/documents${qs({ user_id: userId, kind })}`),
  })
}

export function useUploadDocument() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ userId, kind, file }: { userId: number; kind: string; file: File }) => {
      const form = new FormData()
      form.append('user_id', String(userId))
      form.append('kind', kind)
      form.append('file', file)
      return api.upload<Document>('/api/v1/documents', form)
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['documents'] }),
  })
}

export function useIndexDocument() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ userId, documentId }: { userId: number; documentId: number }) =>
      api.post<DocumentIndexResult>(`/api/v1/documents/${documentId}/index${qs({ user_id: userId })}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['documents'] }),
  })
}

// --- evidence ----------------------------------------------------------------

export function useEvidence(userId: number, status?: string) {
  return useQuery({
    queryKey: ['evidence', userId, status ?? 'all'],
    queryFn: () =>
      api.get<Evidence[]>(`/api/v1/candidates/${userId}/evidence${qs({ status })}`),
  })
}

export function useExtractResume(userId: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ documentId }: { documentId: number }) =>
      api.post<ExtractionResult>(
        `/api/v1/candidates/${userId}/extract${qs({ document_id: documentId })}`,
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['evidence'] })
      qc.invalidateQueries({ queryKey: ['documents'] })
    },
  })
}

export function usePatchEvidence(userId: number) {
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
        `/api/v1/candidates/${userId}/evidence/${evidenceId}`,
        patch,
      ),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['evidence'] }),
  })
}

// --- roles -------------------------------------------------------------------

export function useRoles(userId: number) {
  return useQuery({
    queryKey: ['roles', userId],
    queryFn: () => api.get<Role[]>(`/api/v1/roles${qs({ user_id: userId })}`),
  })
}

export function useAnalyzeRole() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: { user_id: number; jd_text: string; source_document_id?: number }) =>
      api.post<Role>('/api/v1/roles/analyze', body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['roles'] }),
  })
}

// --- interviews --------------------------------------------------------------

export function useInterviews(userId: number) {
  return useQuery({
    queryKey: ['interviews', userId],
    queryFn: () => api.get<InterviewSession[]>(`/api/v1/interviews${qs({ user_id: userId })}`),
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
      duration_minutes: number
      focus_competency_ids: number[]
      mode: string
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

// --- readiness / preparation / progress --------------------------------------

export function useReadiness(userId: number) {
  return useQuery({
    queryKey: ['readiness', userId],
    queryFn: () => api.get<Readiness>(`/api/v1/readiness/latest${qs({ user_id: userId })}`),
    retry: false,
  })
}

export function useComputeReadiness(userId: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (roleId?: number) =>
      api.post<Readiness>(`/api/v1/readiness${qs({ user_id: userId, role_id: roleId })}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['readiness'] })
      qc.invalidateQueries({ queryKey: ['preparation'] })
    },
  })
}

export function usePreparation(userId: number) {
  return useQuery({
    queryKey: ['preparation', userId],
    queryFn: () => api.get<PreparationItem[]>(`/api/v1/preparation${qs({ user_id: userId })}`),
  })
}

export function useRegeneratePreparation(userId: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () =>
      api.post<PreparationItem[]>(`/api/v1/preparation/regenerate${qs({ user_id: userId })}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['preparation'] }),
  })
}

export function useProgress(userId: number) {
  return useQuery({
    queryKey: ['progress', userId],
    queryFn: () => api.get<ProgressSummary>(`/api/v1/progress${qs({ user_id: userId })}`),
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
