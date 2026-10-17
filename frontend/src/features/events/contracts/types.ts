/** G1 contract types. These do not mount routes or enable programme features. */
export type SubjectKind = 'registration' | 'application' | 'role_assignment'
export type ProgrammeCapability =
  | 'events.hackathons' | 'events.mentoring' | 'events.mentor_rounds'
  | 'events.volunteering' | 'events.project_gallery'

export interface ProgrammeCommand {
  operation_id: string
  expected_version: number
}

export interface EmergencyContact {
  name: string
  relationship: string
  phone: string
}

export interface FormDescriptor {
  schema_version: 2
  form_id: string
  revision: number
  questions: Array<Record<string, unknown>>
  event_context?: {
    event_id: number
    event_date_revision: number
    timezone_name: string
    as_of_date: string
  }
}

export interface AdmissionSelection {
  ticket_type_id?: number
  invite_code?: string
  promo_code?: string
  email?: string
  phone?: string
  host_waiver_id?: number | null
  host_waiver_version?: string | null
  host_waiver_accepted?: boolean
}

export interface ProgrammeMemberInput extends ProgrammeCommand, AdmissionSelection {
  form: { schema_version: 2; form_id: string; revision: number }
  answers: Record<string, unknown>
  derivations: Record<string, {
    source: { kind: 'inline_dob'; date_of_birth: string }
      | { kind: 'saved_detail'; field_key: 'date_of_birth'; version: number }
    reviewed_event_date_revision: number
    reviewed_as_of_date: string
  }>
  save_choices: Record<string, boolean>
  saved_detail_versions: Record<string, number>
  coc?: { revision: number; accepted: boolean }
  optional_consents?: { mlh_data_sharing?: boolean }
  event_date_revision: number
}

export interface HackathonApplicationInput extends ProgrammeMemberInput {
  coc: { revision: number; accepted: boolean }
}

export interface NamedRoute { name: string; url: string }
export type ContextRouteKey =
  | 'context' | 'application' | 'application_submit' | 'application_withdraw'
  | 'application_rsvp' | 'application_date_review' | 'role_postings' | 'prefill'
  | 'ordinary_register'

export interface ProgrammeContext {
  context_version: 1
  event: {
    id: number; public_token: string; starts_at: string; ends_at: string
    timezone_name: string; event_date_revision: number; as_of_date: string
  }
  makerspace: { id: number; slug: string }
  programme: {
    kind: 'ordinary' | 'hackathon'
    capabilities: Record<ProgrammeCapability, boolean>
    team_mode: string | null
    finder_enabled: boolean
  }
  application_form: FormDescriptor | Array<Record<string, unknown>> | null
  registration_form: FormDescriptor | Array<Record<string, unknown>> | null
  coc: { revision: number; body: string } | null
  admission_requirements: Record<string, unknown>
  eligibility: { eligible: boolean; reason: string | null }
  saved_details: { readiness: 'ready' | 'unavailable' }
  routes: { member_base: string } & Record<ContextRouteKey, NamedRoute | null>
}

export interface ApplicationSubmission {
  id: number
  event_id: number
  version: number
  state: string
  registration_id: number | null
  allowed_actions: string[]
  save_intent: { operation_id: string; state: string; status_url: string } | null
}
