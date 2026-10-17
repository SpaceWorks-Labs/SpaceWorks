import type { ApplicationSubmission, ProgrammeContext } from './types'

function record(value: unknown): Record<string, unknown> {
  if (value === null || typeof value !== 'object' || Array.isArray(value)) {
    throw new Error('Invalid programme contract object.')
  }
  return value as Record<string, unknown>
}

function positiveInteger(value: unknown) {
  if (typeof value !== 'number' || !Number.isSafeInteger(value) || value <= 0) {
    throw new Error('Invalid programme contract ID or revision.')
  }
}

function apiPath(value: unknown): asserts value is string {
  if (typeof value !== 'string' || !value.startsWith('/api/v1/')
      || /[\\\s?#%]/.test(value) || /\/(?:\.{1,2})(?:\/|$)/.test(value)
      || value.includes('://')) {
    throw new Error('Programme routes must be same-origin API paths.')
  }
}

const routeKeys = [
  'context', 'application', 'application_submit', 'application_withdraw',
  'application_rsvp', 'application_date_review', 'role_postings', 'prefill', 'ordinary_register',
] as const

/** Transport parsing only. F owns full form validation; server owns authority. */
export function parseProgrammeContext(value: unknown): ProgrammeContext {
  const data = record(value)
  const event = record(data.event)
  const space = record(data.makerspace)
  const programme = record(data.programme)
  const routes = record(data.routes)
  if (data.context_version !== 1 || !['ordinary', 'hackathon'].includes(String(programme.kind))) {
    throw new Error('Unsupported programme context.')
  }
  positiveInteger(event.id)
  positiveInteger(space.id)
  positiveInteger(event.event_date_revision)
  for (const key of ['public_token', 'starts_at', 'ends_at', 'timezone_name', 'as_of_date']) {
    if (typeof event[key] !== 'string' || !event[key]) throw new Error('Invalid event context.')
  }
  if (typeof space.slug !== 'string' || !space.slug) throw new Error('Invalid host context.')
  const capabilities = record(programme.capabilities)
  for (const key of ['events.hackathons', 'events.mentoring', 'events.mentor_rounds',
    'events.volunteering', 'events.project_gallery']) {
    if (typeof capabilities[key] !== 'boolean') throw new Error('Invalid capability flag.')
  }
  if (typeof programme.finder_enabled !== 'boolean'
      || (programme.team_mode !== null && typeof programme.team_mode !== 'string')) {
    throw new Error('Invalid programme configuration.')
  }
  for (const key of ['application_form', 'registration_form']) {
    const form = data[key]
    if (form === undefined) throw new Error('Missing form descriptor.')
    if (form !== null && !Array.isArray(form)) {
      const descriptor = record(form)
      if (descriptor.schema_version !== 2 || typeof descriptor.form_id !== 'string'
          || !Array.isArray(descriptor.questions)) throw new Error('Invalid form descriptor.')
      positiveInteger(descriptor.revision)
    }
  }
  const eligibility = record(data.eligibility)
  if (typeof eligibility.eligible !== 'boolean'
      || (eligibility.reason !== null && typeof eligibility.reason !== 'string')) {
    throw new Error('Invalid eligibility projection.')
  }
  record(data.admission_requirements)
  if (!['ready', 'unavailable'].includes(String(record(data.saved_details).readiness))) {
    throw new Error('Invalid saved details readiness.')
  }
  if (data.coc !== null) {
    positiveInteger(record(data.coc).revision)
    if (typeof record(data.coc).body !== 'string') throw new Error('Invalid code of conduct.')
  }
  apiPath(routes.member_base)
  if (routes.member_base !== `/api/v1/member/makerspaces/${space.id}/events/${event.id}`) {
    throw new Error('Programme context host/event mismatch.')
  }
  for (const key of routeKeys) {
    if (routes[key] === null) continue
    const route = record(routes[key])
    if (typeof route.name !== 'string' || !route.name) throw new Error('Invalid named route.')
    apiPath(route.url)
    if ((key.startsWith('application') || key === 'role_postings')
        && !route.url.startsWith(`${routes.member_base}/`)) {
      throw new Error('Programme action targets another event.')
    }
    if (key === 'prefill' && route.url !== '/api/v1/member/saved-details/prefill/') {
      throw new Error('Invalid saved details prefill route.')
    }
  }
  if (!eligibility.eligible && routeKeys.some(key => key !== 'context' && routes[key] !== null)) {
    throw new Error('Ineligible context must not advertise admission actions.')
  }
  if (programme.kind === 'ordinary' && (data.application_form !== null
      || ['application', 'application_submit', 'application_withdraw', 'application_rsvp',
        'application_date_review'].some(key => routes[key] !== null))) {
    throw new Error('Ordinary context cannot advertise application routes.')
  }
  return data as unknown as ProgrammeContext
}

export function parseApplicationSubmission(value: unknown): ApplicationSubmission {
  const data = record(value)
  for (const key of ['id', 'event_id', 'version']) positiveInteger(data[key])
  if (data.registration_id !== null) positiveInteger(data.registration_id)
  if (typeof data.state !== 'string' || !Array.isArray(data.allowed_actions)
      || data.allowed_actions.some(action => typeof action !== 'string')) {
    throw new Error('Invalid application result.')
  }
  if (data.save_intent !== null) {
    const intent = record(data.save_intent)
    if (typeof intent.operation_id !== 'string' || typeof intent.state !== 'string') {
      throw new Error('Invalid saved detail intent.')
    }
    apiPath(intent.status_url)
  }
  if (['staged_decision', 'invite_code', 'promo_code', 'source_dob_envelope'].some(key => key in data)) {
    throw new Error('Private internal state in owner application result.')
  }
  return data as unknown as ApplicationSubmission
}
