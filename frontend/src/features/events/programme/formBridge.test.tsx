import { expect, it } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { formSchema, filledState, ProgrammeFields } from './formBridge'
import { memberFormInput, type FormSchemaV2, type FormState } from '../../forms'
import { applicationPayload } from '../hackathonAdmission/applicationPayload'
import { parseProgrammeContext } from '../contracts/parsers'
import bootstrap from '../../../../../backend/tests/events/programme/contracts/fixtures/public-url-bootstrap-v3.json'
import type { Application } from '../hackathonAdmission/types'
import { checkInInput } from '../../staff/eventsApi'

const schema: FormSchemaV2 = { schema_version: 2, form_id: 'application', revision: 1,
  event_context: { event_id: 42, event_date_revision: 7, as_of_date: '2026-12-01', timezone_name: 'UTC' }, questions: [
    { id: 'enable', type: 'yes_no', label: 'Share extra information' },
    { id: 'diet', type: 'short_text', label: 'Dietary needs', profile_field_key: 'dietary_needs', show_if: { field_id: 'enable', op: 'eq', value: true } },
    { id: 'age', type: 'age_at_event', label: 'Age at event start', profile_field_key: 'age_at_event' },
  ] }
const blank: FormState = { answers: {}, derivations: {}, save_choices: {}, saved_detail_versions: {} }

it('validates open generated JSON before rendering a form', () => {
  expect(() => formSchema({ schema_version: 3 })).toThrow()
  expect(() => formSchema({ ...schema, questions: [{ id: 'x', type: 'made_up', label: 'Bad' }] })).toThrow()
  expect(formSchema(schema)).toEqual(schema)
})
it('prefills private DOB sources without claiming owner review or storing an age answer', () => {
  const filled = filledState(schema, blank, { values: {}, saved_detail_versions: { date_of_birth: 3 }, save_defaults: { date_of_birth: false },
    form_revision: 1, event_date_revision: 7, derivation_inputs: { age: { source: { kind: 'saved_detail', field_key: 'date_of_birth', version: 3 }, value: 26, as_of_date: '2026-12-01' } } })
  expect(filled.answers.age).toBeUndefined()
  expect(filled.derivations.age.reviewed_event_date_revision).toBe(0)
  expect(filled.save_choices.date_of_birth).toBe(false)
})
it('keeps hidden draft text in React while omitting its answer and save choice at submission', () => {
  const value = { ...blank, answers: { enable: false, diet: 'private draft' }, save_choices: { dietary_needs: true } }
  const normalized = memberFormInput(schema, value)
  expect(value.answers.diet).toBe('private draft')
  expect(normalized.answers).not.toHaveProperty('diet')
  expect(normalized.save_choices).not.toHaveProperty('dietary_needs')
  const context = { ...parseProgrammeContext(bootstrap.context), application_form: schema }
  const body = applicationPayload(context, bootstrap.virtual_draft as Application, value, {}, true, false)
  expect(body.answers).not.toHaveProperty('diet')
})
it('never turns saving on when the account vault is unavailable', () => {
  let next: FormState | undefined
  render(<ProgrammeFields schema={{ ...schema, questions: [{ id: 'name', label: 'Name', type: 'short_text', profile_field_key: 'name' }] }}
    value={blank} prefill={undefined} onChange={value => { next = value }} errors={{}} disabled={false} savedDetailsAvailable={false} />)
  fireEvent.change(screen.getByRole('textbox'), { target: { value: 'Maker' } })
  expect(next?.save_choices.name).toBe(false)
})
it('chooses exactly one legacy UUID or v2 credential input for check-in', () => {
  const uuid = '12345678-1234-1234-1234-123456789abc'
  expect(checkInInput(uuid)).toEqual({ checkin_token: uuid })
  expect(checkInInput('sw-event-v2.opaque.signature')).toEqual({ credential: 'sw-event-v2.opaque.signature' })
})
