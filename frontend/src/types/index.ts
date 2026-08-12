export interface User {
  id: number
  email: string
  full_name: string
  is_active: boolean
  is_superuser: boolean
  created_at: string
  profile?: UserProfile | null
}

export interface UserProfile {
  id: number
  user_id: number
  phone: string | null
  location: string | null
  headline: string | null
  summary: string | null
  linkedin_url: string | null
  github_url: string | null
  website: string | null
  created_at: string
  updated_at: string
}

export interface Resume {
  id: number
  user_id: number
  title: string
  file_path: string
  file_type: string
  parsed_data: string | null
  ats_score: number | null
  missing_keywords: string | null
  improvement_suggestions: string | null
  created_at: string
  updated_at: string
}

export interface Job {
  id: number
  title: string
  company_name: string | null
  location: string | null
  country: string | null
  job_type: string | null
  salary_min: number | null
  salary_max: number | null
  salary_currency: string | null
  seniority: string | null
  experience_min: number | null
  experience_max: number | null
  skills_required: string | null
  description: string | null
  source: string | null
  source_url: string | null
  match_score: number | null
  match_reason: string | null
  matched_skills: string[] | null
  created_at: string
}

export interface JobDetail extends Job {
  requirements: string | null
  posted_at: string | null
}

export interface Application {
  id: number
  user_id: number
  job_id: number
  status: string
  applied_at: string | null
  responded_at: string | null
  application_source: string
  priority: string
  ai_priority: string | null
  resume_id: number | null
  resume_version_id: number | null
  tailored_resume_id: number | null
  cover_letter_id: number | null
  cover_letter_version_id: number | null
  application_answer_version_id: number | null
  application_packet_id: number | null
  notes: string | null
  follow_up_recommended_at: string | null
  follow_up_reason: string | null
  follow_up_status: string | null
  job_title: string | null
  company_name: string | null
  match_score: number | null
  created_at: string
  updated_at: string
}

export interface ApplicationSnapshot {
  job_title: string
  company_name: string | null
  location: string | null
  country: string | null
  remote_type: string | null
  salary_min: number | null
  salary_max: number | null
  salary_currency: string | null
  description: string | null
  requirements: string | null
  responsibilities: string | null
  source: string | null
  source_url: string | null
  application_url: string | null
  canonical_url: string | null
  posted_at: string | null
  match_score: number | null
  match_confidence: number | null
  job_quality_score: number | null
  created_at: string | null
}

export interface ApplicationTimelineEntry {
  old_status: string | null
  new_status: string | null
  source: string | null
  reason: string | null
  changed_at: string
}

export interface ApplicationAuditEntry {
  event: string
  timestamp: string
  metadata: Record<string, unknown> | null
}

export interface ApplicationNote {
  id: number
  note: string
  created_at: string
}

export interface ApplicationDocument {
  id: number
  doc_type: string
  version_label: string | null
  download_url: string
}

export interface ApplicationDetail extends Application {
  snapshot: ApplicationSnapshot | null
  tags: string[]
  documents: ApplicationDocument[]
  timeline: ApplicationTimelineEntry[]
}

export interface ApplicationAnalytics {
  total_applications: number
  drafts: number
  ready: number
  applied: number
  responses: number
  interviews: number
  final_rounds: number
  offers: number
  rejected: number
  withdrawn: number
  response_rate: number
  interview_rate: number
  offer_rate: number
  funnel: {
    applied: number
    responses: number
    interviews: number
    final_rounds: number
    offers: number
  }
}

export interface NeedsAttentionItem {
  kind: 'FOLLOW_UP' | 'REMINDER'
  application_id: number
  reminder_id?: number
  reminder_type?: string
  job_title: string | null
  company_name: string | null
  reason: string
  due_at: string
}

export interface ApplicationReminder {
  id: number
  application_id: number
  reminder_type: string
  due_at: string
  status: string
  title: string | null
  message: string | null
}

export interface FollowUpResponse {
  recommended: boolean
  reason: string | null
  recommended_at: string
  message: string
  mode: string
}

export interface Notification {
  id: number
  user_id: number
  type: string
  title: string
  message: string | null
  is_read: boolean
  scheduled_at: string | null
  sent_at: string | null
  created_at: string
}

export interface CoverLetter {
  id: number
  user_id: number
  job_id: number
  resume_id: number | null
  content: string
  status: string
  job_title: string | null
  company_name: string | null
  created_at: string
}

export interface InterviewQuestion {
  id: number
  user_id: number
  job_id: number
  category: string
  question: string
  suggested_answer: string | null
  explanation: string | null
  created_at: string
}

export interface InterviewEvaluation {
  question_id: number
  score: number
  strengths: string
  improvements: string
  model_answer: string
}

export interface AnalyticsSummary {
  total_applications: number
  applications_by_status: Record<string, number>
  interviews: number
  response_rate_percent: number
  cover_letters: number
  resumes: number
  resume_versions: number
  interview_questions_prepared: number
  notifications_total: number
  notifications_unread: number
  average_ats_score: number | null
}

export interface AdminUser {
  id: number
  email: string
  full_name: string
  is_active: boolean
}

export interface AiLog {
  id: number
  user_id: number
  agent_type: string
  status: string
  created_at: string
}

export interface ActivityLog {
  id: number
  action: string
  entity_type: string
  created_at: string
}

export interface ResumeVersion {
  id: number
  resume_id: number
  user_id: number
  content: string
  version_label: string | null
  created_at: string
}

export type AutomationStatus = 'started' | 'running' | 'completed' | 'failed' | 'cancelled'

export interface AutomationSession {
  id: number
  user_id: number
  job_id: number | null
  job_url: string | null
  status: AutomationStatus
  steps: string | null
  confirmation_required: boolean
  user_confirmed: boolean
  result: string | null
  screenshot_paths: string | null
  created_at: string
  updated_at: string
}

export interface SkillDemand {
  skill: string
  count: number
}

export interface CompanyIntel {
  company: string
  job_count: number
  avg_salary: number | null
}

export interface SalaryBenchmark {
  seniority: string
  count: number
  avg_salary: number | null
  median_salary: number | null
  p25: number | null
  p75: number | null
}

export interface TrendPoint {
  date: string
  count: number
}

export interface JobIntelSummary {
  total_jobs: number
  distinct_companies: number
  median_salary: number | null
  avg_salary: number | null
  remote_share_pct: number
  jobs_posted_30d: number
  demand_index: number
  top_skills: SkillDemand[]
}

export interface CareerIntel {
  has_resume: boolean
  user_skills: { skill: string; jobs_count: number; in_market: boolean }[]
  recommended_skills: SkillDemand[]
  coverage_score: number
  median_target_salary: number | null
  target_jobs_count: number
  total_jobs: number
}

export interface ResumeSearchProfile {
  roles: string[]
  skills: string[]
  experienceYears: number | null
  locations: string[]
  seniority: string | null
  workMode: string | null
  designation: string | null
}

export interface SearchProfileResponse {
  has_resume: boolean
  profile: ResumeSearchProfile | null
}

export interface SourceStatusItem {
  name: string
  portal: string | null
  status: string
  count: number
  error: string | null
}

export interface SearchSessionStatus {
  search_id: number
  status: string
  time_range: string | null
  remote: string | null
  error: string | null
  started_at: string | null
  completed_at: string | null
  queries: string[]
  sources: SourceStatusItem[]
}

export interface SourceReference {
  source: string
  source_url: string
  search_source: string | null
}

export interface JobSearchResult {
  id: number
  search_result_id: number
  rank: number
  title: string
  company_name: string | null
  location: string | null
  country: string | null
  job_type: string | null
  remote_type: string | null
  salary_min: number | null
  salary_max: number | null
  salary_currency: string | null
  description: string | null
  skills_required: string | null
  seniority: string | null
  experience_min: number | null
  experience_max: number | null
  posted_at: string | null
  posting_verified: boolean | null
  discovered_at: string | null
  last_verified_at: string | null
  freshness: string | null
  is_active: boolean | null
  source: string | null
  search_source: string | null
  source_url: string | null
  canonical_url: string | null
  application_url: string | null
  sources: string[]
  source_references: SourceReference[]
  match_score: number
  match_confidence: number | null
  requirements: RequirementCounts | null
  skill_score: number
  experience_score: number
  responsibility_score: number
  seniority_score: number
  location_score: number
  salary_score: number
  matched_skills: string[]
  missing_skills: string[]
  related_skills: string[]
  recommendation: string | null
  match_reason: string | null
  job_quality_score: number | null
  rank_explanation: string | null
}

export interface SearchResultsResponse {
  search_id: number
  status: string
  message: string | null
  jobs: JobSearchResult[]
}

export interface SearchHistoryItem {
  search_id: number
  status: string
  time_range: string | null
  remote: string | null
  queries: string[]
  result_count: number
  created_at: string | null
  completed_at: string | null
}

// -------------------------------
// Advanced match + career evidence
// -------------------------------
export interface RequirementCounts {
  met: number
  related: number
  partial: number
  missing: number
  critical_missing: string[]
}

export interface RequirementMatrixItem {
  requirement_id: number
  requirement: string
  skill: string | null
  importance: string
  is_critical: boolean
  classification: 'DIRECT_MATCH' | 'RELATED_MATCH' | 'PARTIAL_MATCH' | 'NO_EVIDENCE'
  fact_id: number | null
  fact_name: string | null
  skill_score: number
  confidence: number
  evidence_text: string | null
}

export interface MatchedFact {
  fact_id: number
  fact_name: string
  fact_type: string
  classification: string
  evidence_text: string | null
  confidence: number
}

export interface AdvancedMatch {
  overall_score: number
  required_skill_score: number
  preferred_skill_score: number
  education_score: number
  career_goal_score: number
  experience_score: number
  seniority_score: number
  location_score: number
  salary_score: number
  responsibility_score: number
  match_confidence: number
  recommendation: string
  requirements: RequirementMatrixItem[]
  critical_missing: string[]
  matched_facts: MatchedFact[]
  relevant_projects: string[]
  relevant_achievements: string[]
  relevant_experience: string[]
  why_match: string
  why_not: string
  match_reason: string
}

export interface ShouldApplyResponse {
  decision: 'STRONGLY_RECOMMENDED' | 'RECOMMENDED' | 'CONSIDER' | 'LOW_PRIORITY' | 'SKIP'
  confidence: number
  recommendation: string
  reasons: string[]
  risks: string[]
  critical_gaps: string[]
}

export interface RoiResponse {
  roi_score: number
  decision: string
  estimated_salary: number | null
  salary_currency: string | null
  salary_confidence: number
  signals: Record<string, number>
  notes: string[]
}

export interface JobMatchEvidenceRecord {
  id: number
  career_fact_id: number | null
  fact_name: string | null
  fact_type: string | null
  classification: string
  reason: string | null
  evidence_text: string | null
  confidence: number
  created_at: string | null
}

export interface CareerFact {
  id: number
  user_id: number
  fact_type: string
  name: string
  value: string | null
  description: string | null
  confidence: number
  status: string
  verified_by_user: boolean | null
  is_public: boolean | null
  created_at: string | null
  updated_at: string | null
}

export interface CareerEvidence {
  id: number
  user_id: number
  career_fact_id: number
  evidence_type: string
  source: string
  source_id: number | null
  source_section: string | null
  evidence_text: string | null
  confidence: number
  verification_status: string
  verified_by_user: boolean | null
  created_at: string | null
  updated_at: string | null
}

export interface CareerVaultSummary {
  facts_total: number
  facts_by_status: Record<string, number>
  facts_by_type: Record<string, number>
  evidence_total: number
}

export interface CareerIndexResponse {
  facts_created: number
  facts_kept: number
  facts_rejected: number
  evidence_created: number
}
