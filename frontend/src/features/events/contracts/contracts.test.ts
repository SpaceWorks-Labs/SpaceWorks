import { describe, expect, it } from 'vitest'
import admission from '../../../../../backend/tests/events/programme/contracts/fixtures/application-admission-v3.json'
import bootstrap from '../../../../../backend/tests/events/programme/contracts/fixtures/public-url-bootstrap-v3.json'
import emergency from '../../../../../backend/tests/events/programme/contracts/fixtures/emergency-contact-v2.json'
import { parseApplicationSubmission, parseProgrammeContext } from './parsers'

describe('G1 canonical provider/consumer fixtures', () => {
  it('bootstraps account-only application using token context IDs and returned URLs', () => {
    const context = parseProgrammeContext(bootstrap.context)
    expect(bootstrap.setup.memberships).toEqual([])
    expect(context.makerspace.id).toBe(bootstrap.prefill_request.context.makerspace_id)
    expect(context.event.id).toBe(bootstrap.prefill_request.context.event_id)
    expect(context.routes.application_submit?.name).toBe('events-programme-member-application-submit')
    expect(bootstrap.virtual_draft.id).toBeNull()
    expect(parseApplicationSubmission(bootstrap.submit_response).save_intent?.state).toBe('pending')
  })

  it('parses no-save admission success and preserves the exact compound answer', () => {
    expect(parseApplicationSubmission(admission.response).registration_id).toBe(71)
    expect(admission.response.save_intent).toBeNull()
    expect(admission.canonical_snapshot.answers[1]).toEqual(emergency.canonical)
    expect(emergency.save_choices.emergency_contact).toBe(false)
  })

  it('keeps ordinary context free of application affordances', () => {
    const ordinary = parseProgrammeContext(bootstrap.ordinary_context)
    expect(ordinary.application_form).toBeNull()
    expect(ordinary.routes.ordinary_register?.name).toBe('public-event-register')
  })

  it('accepts account-only applications without enabling hackathons or changing action targets', () => {
    const generic = structuredClone(bootstrap.context)
    generic.programme.kind = 'applications'
    generic.programme.capabilities['events.hackathons'] = false
    generic.programme.team_mode = 'solo'
    generic.programme.finder_enabled = false
    const context = parseProgrammeContext(generic)
    expect(context.programme.kind).toBe('applications')
    expect(context.programme.capabilities['events.hackathons']).toBe(false)
    expect(context.application_form).toEqual(bootstrap.context.application_form)
    expect(context.routes.application_submit).toEqual(bootstrap.context.routes.application_submit)
    expect(context.routes.member_base).toBe(`/api/v1/member/makerspaces/${context.makerspace.id}/events/${context.event.id}`)
  })

  it('still rejects unknown programme kinds and unsupported context versions', () => {
    const unknown = structuredClone(bootstrap.context)
    unknown.programme.kind = 'future-programme'
    expect(() => parseProgrammeContext(unknown)).toThrow('Unsupported programme context')
    expect(() => parseProgrammeContext({ ...structuredClone(bootstrap.context),
      programme: { ...bootstrap.context.programme, kind: ['applications'] } })).toThrow('Unsupported programme context')
    const version = { ...structuredClone(bootstrap.context), context_version: 2 }
    expect(() => parseProgrammeContext(version)).toThrow('Unsupported programme context')
  })

  it.each(['https://foreign.example/api/v1/', '//foreign.example/api/v1/', '/api/v1/../secret?x=1',
    '/api/v1/../secret', '/api/v1/%2e%2e/secret']) (
    'refuses noncanonical API route %s', url => {
      const changed = structuredClone(bootstrap.context)
      changed.routes.application.url = url
      expect(() => parseProgrammeContext(changed)).toThrow()
    },
  )

  it('refuses a mismatched host and ineligible action URLs', () => {
    const changed = structuredClone(bootstrap.context)
    changed.makerspace.id = 10
    expect(() => parseProgrammeContext(changed)).toThrow('mismatch')
    const ineligible = structuredClone(bootstrap.context)
    ineligible.eligibility.eligible = false
    expect(() => parseProgrammeContext(ineligible)).toThrow('Ineligible')
    const wrongTarget = structuredClone(bootstrap.context)
    wrongTarget.routes.application.url = '/api/v1/member/makerspaces/9/events/99/application/'
    expect(() => parseProgrammeContext(wrongTarget)).toThrow('another event')
  })

  it('does not accept staged decision or credentials as owner output', () => {
    expect(() => parseApplicationSubmission({ ...admission.response, staged_decision: 'offer' })).toThrow()
    expect(() => parseApplicationSubmission({ ...admission.response, promo_code: 'secret' })).toThrow()
  })
})
