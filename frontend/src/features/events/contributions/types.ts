import type { FormDescriptor, ProgrammeMemberInput } from '../contracts/types'

export interface Page<T> { count: number; next: string | null; previous: string | null; results: T[] }
export interface Aggregate { id: number; event_id: number; version: number; state: string; allowed_actions: string[] }
export interface Posting extends Aggregate {
  role: 'mentor' | 'volunteer'; title: string; description?: string
  form?: FormDescriptor; coc?: { revision: number; body: string }; application?: RoleApplication | null
}
export interface RoleApplication extends Aggregate {
  role: string; posting_id: number | null; answers?: unknown; form?: FormDescriptor
  answer_review?: { event_date_revision: number; as_of_date: string; locked: boolean; date_review_required: boolean }
  save_intent: { operation_id: string; state: string; status_url: string } | null
}
export interface Shift extends Aggregate {
  posting_id: number; kind: 'volunteer' | 'office_hours'; starts_at: string; ends_at: string
  task: string; zone: string; capacity: number; available: number | null; signup: Signup | null
}
export interface Signup extends Aggregate { shift_id: number; attendance: string | null; verified_minutes: number | null }
export interface HelpRequest extends Aggregate {
  origin: 'team' | 'mentor' | 'round'; team_id?: number; team_alias?: string; category?: string
  priority?: number; zone?: { table?: string; zone?: string }; summary?: string
  position?: number | null; wait_estimate?: string
}
export interface HelpComment { id: number; help_id: number; body: string; origin: 'team' | 'mentor'; created_at: string; request_version: number }
export interface Booking extends Aggregate { slot_id: number; team_id: number }
export interface EventScope { eventId: number; makerspaceId: number; accountId: number }
export type RoleFormValue = Pick<ProgrammeMemberInput, 'form' | 'answers' | 'derivations' | 'save_choices'
  | 'saved_detail_versions' | 'coc' | 'optional_consents' | 'event_date_revision'> & {
  skills?: string[]
  availability?: Array<{ starts_at: string; ends_at: string }>
}

export function parseAggregate<T extends Aggregate>(value: T): T {
  if (!value || !Number.isSafeInteger(value.id) || value.id < 1 || !Number.isSafeInteger(value.event_id)
    || !Number.isSafeInteger(value.version) || value.version < 1 || typeof value.state !== 'string'
    || !Array.isArray(value.allowed_actions) || value.allowed_actions.some(x => typeof x !== 'string')) {
    throw new Error('The programme returned an invalid response. Refresh and try again.')
  }
  return value
}

export function parsePage<T extends Aggregate>(value: Page<T>): Page<T> {
  if (!value || !Number.isSafeInteger(value.count) || value.count < 0 || !Array.isArray(value.results)) {
    throw new Error('The programme returned an invalid list.')
  }
  // Frozen read-only posting/slot cards intentionally omit aggregate command
  // members. Preserve that shape; never invent a version or an action grant.
  for (const row of value.results) {
    if (!row || !Number.isSafeInteger(row.id) || row.id < 1) throw new Error('The programme returned an invalid row.')
    const readable: Partial<Aggregate> = row
    if ('allowed_actions' in readable) parseAggregate(row)
    else if (readable.version !== undefined && (!Number.isSafeInteger(readable.version) || readable.version < 1)) throw new Error('The programme returned an invalid version.')
  }
  return value
}
