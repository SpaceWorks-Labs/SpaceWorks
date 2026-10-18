export interface ReviewCriterion { key: string; label: string; anchors: Record<string, string> }
export interface Rubric { revision: number; criteria: ReviewCriterion[] }
export interface ReviewApplication {
  id: number; event_id: number; version: number; state: string; alias: string; blind: boolean
  blind_notice: string | null; answers: Array<{ id: string; label: string; type: string; value: unknown }>
  draft_batch_id?: number | null; cohort_id?: number | null; cohort_version?: number | null; review_id?: number | null; rsvp_due_at?: string | null
}
export interface ReviewAssignment {
  id: number; event_id: number; version: number; state: string; round: number
  allowed_actions: string[]; rubric: Rubric; applications: ReviewApplication[]
  completed_scores?: Array<Record<string, number>>
}
export interface DecisionBatch {
  id: number; event_id: number; version: number; state: string; allowed_actions: string[]
  decisions: Array<{ id: number; application_id: number | null; cohort_id: number | null
    outcome: 'offer' | 'waitlist' | 'reject'; reason_code: string; expected_version: number }>
}
export interface DecisionSelection {
  application_id?: number; cohort_id?: number; expected_version: number
  outcome: 'offer' | 'waitlist' | 'reject'; reason_code: string; review_override_code?: string
}
export interface Config {
  id: number | null; event_id: number; version: number; state: string; enabled: boolean; allowed_actions: string[]
  team_mode: 'solo' | 'individual_then_team' | 'team_together'; team_min: number; team_max: number
  finder_enabled: boolean; team_eligibility: 'confirmed' | 'offered'; rsvp_days: number
  review_mode: 'auto' | 'rolling' | 'batch'; review_count: number; blind_review: boolean
  optional_mlh_schema?: Record<string, unknown>;
  review_round_closed: boolean; review_rubric: Rubric; application_form: unknown
  offer_capacity: number | null; attendance_required: boolean; late_policy: 'reject' | 'accept_flagged'
  application_opens_at: string | null; application_closes_at: string | null; team_lock_at: string | null
  submission_opens_at: string | null; submission_deadline: string | null; submission_grace_minutes: number
  storage_budget_bytes: number | null; upload_policy: string; upload_policy_version: number
  coc: { revision: number; body: string } | null
  counts?: { offered: number; confirmed: number; offer_capacity: number | null; hard_spots_left: number | null }
}
