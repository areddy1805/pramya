// Domain types mirroring backend Pydantic schemas (source of truth:
// backend/app/api/v1 + backend/app/domain/schemas.py).

export interface Health {
  status: string
  app: string
  version: string
  env: string
}

export interface CandidateProfile {
  id: number
  user_id: number
  seniority_target: string | null
  headline: string | null
  timezone: string | null
  created_at: string
}

// Career profile (multi-profile workspace).
export interface CareerProfile {
  id: number
  user_id: number
  name: string
  slug: string | null
  positioning: string | null
  status: string
  seniority_target: string | null
  headline: string | null
  timezone: string | null
  created_at: string
  updated_at: string | null
}

export interface ActiveProfile {
  profile_id: number | null
  profile: CareerProfile | null
}

export type DocumentKind = 'resume' | 'jd' | 'debrief' | 'transcript'
export type DocumentStatus = 'pending' | 'parsing' | 'parsed' | 'failed'

export interface Document {
  id: number
  user_id: number
  profile_id: number | null
  kind: DocumentKind
  filename: string
  mime: string
  size: number
  content_hash: string
  status: DocumentStatus
  parsed_at: string | null
  created_at: string
}

// Idempotent upload result: created or deduplicated.
export interface DocumentUploadResult {
  status: 'created' | 'deduplicated'
  created: boolean
  document_id: number
  profile_id: number | null
  processing_status: string
  kind: DocumentKind
  filename: string
}

export interface DocumentIndexResult {
  document_id: number
  chunk_count: number
  dimension: number
}

export type EvidenceStatus = 'claimed' | 'observed' | 'demonstrated' | 'inferred' | 'unknown'

export interface Evidence {
  id: number
  user_id: number
  source_kind: string
  source_ref: string | null
  claim: string
  status: EvidenceStatus
  competency_id: number | null
  strength: number | null
  notes: string | null
  created_at: string
}

export interface Competency {
  id: number
  name: string
  category: string
  level: number
  importance: string
  weight: number
  importance_rank: number
}

export interface Role {
  id: number
  user_id: number
  title: string
  seniority: string | null
  summary: string | null
  created_at: string
  competencies?: Competency[]
}

export type InterviewKind =
  | 'general'
  | 'resume_deep_dive'
  | 'job_description'
  | 'technical'
  | 'behavioral'
  | 'project_deep_dive'
  | 'system_design'
  | 'coding_reasoning'

export interface InterviewSession {
  id: number
  user_id: number
  role_id: number | null
  kind: string
  status: string
  started_at: string | null
  ended_at: string | null
  config: Record<string, unknown> | null
}

export interface Question {
  id: number
  text: string
  difficulty: string
  type: string
  hint_levels: string[]
  rationale: string | null
  category?: string | null
  source?: string | null
  source_ref?: string | null
}

export interface Answer {
  id: number
  question_id: number
  text: string
  mode: string
  created_at: string | null
}

export interface Hint {
  hint: string
}

export interface ReportQuestionFeedback {
  question_id: number | null
  question: string
  category: string | null
  source: string | null
  answer: string
  overall: number
  good: string[]
  missing: string[]
  expected_follow_ups: string[]
  prep_recommendation: string
}

export interface Report {
  report: string
  scorecard: Record<string, number | string[]> | null
  questions: ReportQuestionFeedback[] | null
  gaps: string[] | null
  topics: string[] | null
}

export interface Readiness {
  overall: number
  confidence: number
  evidence_coverage: number
  per_competency: CompetencyReadiness[]
  critical_gaps: CriticalGap[]
  created_at: string | null
}

export interface CompetencyReadiness {
  name: string
  score: number
  confidence: number
  evidence_coverage: number
  demonstrated_level: number
  importance: string
}

export interface CriticalGap {
  competency_id: number
  name: string
  demonstrated_level: number
  required_level: number
  score: number
  gap: number
}

export interface PreparationItem {
  id: number
  competency_id: number | null
  competency_name: string | null
  priority: number
  estimated_minutes: number | null
  reason: string | null
  assessment_type: string | null
  expected_improvement: number | null
  status: string
}

export interface ProgressPoint {
  evaluation_id: number
  session_id: number
  competency_id: number | null
  competency_name: string
  overall: number
  created_at: string
}

export interface CompetencySeries {
  competency_id: number | null
  name: string
  latest: number | null
  trend: number | null
  points: ProgressPoint[]
}

export interface ProgressSummary {
  total_evaluations: number
  sessions: number
  average_overall: number
  series: CompetencySeries[]
}

export interface ExtractionResult {
  extraction: Record<string, unknown>
  evidence_count: number
}

export interface ProviderStatus {
  name: string
  configured: boolean
  healthy: boolean | null
  base_url: string | null
  models: string[]
}

export interface ModelInfo {
  id: string
  provider: string
  capability: string
  thinking: boolean
}

export interface TaskPolicy {
  task: string
  model: string
  fallbacks: string[]
}

export interface ModelsStatus {
  providers: ProviderStatus[]
  models: ModelInfo[]
  policies: TaskPolicy[]
  local_ai_enabled: boolean
}

export interface Story {
  id: number
  user_id: number
  situation: string | null
  task: string | null
  action: string | null
  result: string | null
  metrics: string | null
  conflict: string | null
  learning: string | null
  strength: string | null
  competency_ids: number[] | null
  freshness: number | null
  usage_count: number
  coverage: number | null
  confidence: number | null
  created_at: string
}

export interface InterviewDebrief {
  id: number
  user_id: number
  company: string
  role: string | null
  round: string | null
  questions: Record<string, unknown>[] | null
  feedback: string | null
  result: string | null
  analysis: Record<string, unknown> | null
  created_at: string
}
