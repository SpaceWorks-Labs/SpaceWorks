import type { Config as WireConfig, Review as WireReview, ReviewApplication as WireApplication, AdmissionDecisionBatch as WireBatch } from '../../../generated/api'
export interface ReviewCriterion { key: string; label: string; anchors: Record<string, string> }
export interface Rubric { revision: number; criteria: ReviewCriterion[] }
export type ReviewApplication = Omit<WireApplication, 'answers'> & { answers: Array<{ id: string; label: string; type: string; value: unknown }> }
export type ReviewAssignment = Omit<WireReview, 'id' | 'rubric' | 'applications' | 'completed_scores'> & {
  id: number; rubric: Rubric; applications: ReviewApplication[]; completed_scores?: Array<Record<string, number>>
}
// The generated `Batch` component name is shared with certificate issue batches, so its
// `state` enum is not the decision-batch lifecycle; state it explicitly here.
export type DecisionBatch = Omit<WireBatch, 'id' | 'decisions' | 'state'> & {
  id: number; state: 'draft' | 'committed' | 'cancelled'; decisions: Array<{ id: number; application_id: number | null; cohort_id: number | null
    outcome: 'offer' | 'waitlist' | 'reject'; reason_code: string; expected_version: number }>
}
export interface DecisionSelection {
  application_id?: number; cohort_id?: number; expected_version: number
  outcome: 'offer' | 'waitlist' | 'reject'; reason_code: string; review_override_code?: string
}
export type Config = Omit<Required<WireConfig>, 'review_rubric' | 'counts' | 'optional_mlh_schema'> & {
  review_rubric: Rubric; counts?: WireConfig['counts']; optional_mlh_schema?: Record<string, unknown>
}
