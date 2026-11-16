import emergency from '../../../../../backend/tests/events/programme/contracts/fixtures/emergency-contact-v2.json'
import { describe, expect, it } from 'vitest'
import admission from '../../../../../backend/tests/events/programme/contracts/fixtures/application-admission-v3.json'
import bootstrap from '../../../../../backend/tests/events/programme/contracts/fixtures/public-url-bootstrap-v3.json'
import { parseProgrammeContext } from '../contracts/parsers'
import { applicationPayload } from './applicationPayload'
import type { Application, FormValue, AdmissionSelection } from './types'

// The bootstrap fixture's descriptor predates the joint emergency fixture. Compose
// the two frozen descriptors locally; backend fixture reconciliation belongs to G.
const context = parseProgrammeContext({ ...bootstrap.context, application_form: { ...bootstrap.context.application_form,
  questions: [...bootstrap.context.application_form.questions, ...emergency.schema.questions] } })
const virtual = bootstrap.virtual_draft as Application
const request = admission.request
const value: FormValue = { answers: request.answers, derivations: request.derivations,
  save_choices: request.save_choices, saved_detail_versions: request.saved_detail_versions }
const selection: AdmissionSelection = { ticket_type_id: request.ticket_type_id, invite_code: request.invite_code,
  promo_code: request.promo_code, email: request.email, phone: request.phone, host_waiver_id: request.host_waiver_id,
  host_waiver_version: request.host_waiver_version, host_waiver_accepted: request.host_waiver_accepted }

describe('A/G literal admission consumer', () => {
  it('sends exact reviewed top-level fields and the compound answer', () => {
    const { operation_id: _operation, ...expected } = request
    expect(applicationPayload(context, virtual, value, selection, true, false)).toEqual(expected)
  })
  it('never includes codes on PATCH and never changes sensitive save choices', () => {
    const result = applicationPayload(context, virtual, value, selection, true, false, true)
    expect(result).not.toHaveProperty('invite_code')
    expect(result).not.toHaveProperty('promo_code')
    expect(result.save_choices.emergency_contact).toBe(false)
    expect(result.answers.emergency).toEqual(admission.canonical_snapshot.answers[1].value)
  })
  it('does not infer the first ticket or an accepted waiver', () => {
    const result = applicationPayload(context, virtual, value, {}, false, false)
    expect(result).not.toHaveProperty('ticket_type_id')
    expect(result).not.toHaveProperty('host_waiver_accepted')
    expect(result.coc.accepted).toBe(false)
  })
})
