import type { FormDescriptor, ProgrammeMemberInput } from '../contracts/types'

export interface Page<T> { count: number; next: string | null; previous: string | null; results: T[] }
export type Aggregate = Omit<import('../../../generated/api').Aggregate, 'id'> & { id: number }
export type Posting = Omit<import('../../../generated/api').Posting, 'form' | 'coc' | 'application' | 'role'> & {
  role: 'mentor' | 'volunteer'; form?: FormDescriptor; coc?: { revision: number; body: string }; application?: RoleApplication | null
}
export type RoleApplication = Omit<import('../../../generated/api').Role, 'form' | 'answer_review' | 'save_intent' | 'submitted_at' | 'decision' | 'grant'> & {
  form?: FormDescriptor; submitted_at?: string | null; decision?: string | null; grant?: number | null
  answer_review?: import('../../../generated/api').AnswerReview
  save_intent: import('../../../generated/api').SaveIntent | null
}
export type Shift = Omit<import('../../../generated/api').Shift, 'mentor_card' | 'signup'> & {
  mentor_card?: unknown; signup: Signup | null
}
export type Signup = import('../../../generated/api').Signup
export type HelpRequest = import('../../../generated/api').Help
export type HelpComment = import('../../../generated/api').Comment
export type Booking = import('../../../generated/api').Booking
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
