import type { ComponentType } from 'react'
import type { ProgrammeContext, ProgrammeMemberInput, AdmissionSelection } from '../contracts/types'
export type { ProgrammeContext, AdmissionSelection }
export interface Page<T> { count: number; next: string | null; previous: string | null; results: T[] }
export interface Application {
  id: number | null; event_id: number; version: number; state: string; registration_id: number | null
  allowed_actions: string[]; form: ProgrammeContext['application_form']; answers: Array<Record<string, unknown>>
  admission_requirements: AdmissionRequirements; admission: OwnerAdmission
  answer_review?: { event_date_revision: number; as_of_date: string; locked: boolean; date_review_required: boolean }
  optional_consents?: Record<string, { accepted: boolean; version: number; at: string }>;
  omitted_question_ids?: string[]; optional_consent_purposes?: string[]
  rsvp_due_at?: string | null; rsvp_accepted_at?: string | null
  save_intent: { operation_id: string; state: string; status_url: string } | null
}
export interface AdmissionRequirements {
  registration_audience: string; ticket_selection_required: boolean
  ticket_types: Array<{ id: number; name: string; amount: string; audience: string; spots_left: number | null }>
  currency: string; promo_codes_enabled: boolean; invite_code_allowed: boolean
  verified_email_invite_supported: boolean
  contact_requirements: { email: { fallback_required: boolean }; phone: { fallback_required: boolean } }
  host_waiver: { id: number; version: string; body: string; acceptance_required: boolean } | null
}
export interface OwnerAdmission {
  ticket_type_id: number | null; contact: { name: string; email: string; phone: string }
  quote: { amount: string; discount_amount: string; currency: string } | null
  invite_applied: boolean; promo_applied: boolean
  host_waiver_acceptance: { id: number; version: string; accepted_at: string } | null
}
export interface Prefill {
  values: Record<string, unknown>; saved_detail_versions: Record<string, number>
  save_defaults: Record<string, boolean>; derivation_inputs: Record<string, unknown>
  form_revision: number; event_date_revision: number
}
export interface FormValue {
  answers: ProgrammeMemberInput['answers']; derivations: ProgrammeMemberInput['derivations']
  save_choices: Record<string, boolean>; saved_detail_versions: Record<string, number>
}
/** F owns rendering, hidden-field rules and profile descriptors; P owns prefill. */
export interface FieldsProps {
  schema: NonNullable<ProgrammeContext['application_form']>; value: FormValue
  onChange: (value: FormValue) => void; prefill: Prefill | undefined
  errors: Record<string, unknown>; disabled: boolean; savedDetailsAvailable: boolean
}
export type FormFields = ComponentType<FieldsProps>
export interface PublicProfile { display_name?: string; url?: string; photo_url?: string }
export interface Team {
  id: number; event_id: number; version: number; state: string; name: string; team_mode: string
  allowed_actions: string[]; leader_member_id: number; seeking_members: boolean; finder_intro: string; skills: string[]
  eligibility_issue: boolean; roster_hash: string
  members: Array<{ id: number; member_id: number; joined_at: string; profile: PublicProfile | null }>
  join_requests: Array<{ id: number; profile: PublicProfile | null }>
}
export interface FinderCard {
  id: number; event_id: number; version: number; kind: 'person' | 'team'
  name?: string; intro: string; skills: string[]; slots?: number
  profile?: PublicProfile | null; profiles?: PublicProfile[]
}
