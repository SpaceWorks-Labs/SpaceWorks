import { fireEvent, render as rtlRender, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
const admissionFlow = vi.hoisted(() => ({ useAdmission: vi.fn(), mutate: vi.fn() }))
vi.mock('./useAdmission', () => ({ useAdmission: admissionFlow.useAdmission }))
import { HackathonApplicationPage } from './HackathonApplicationPage'
// useChargesOn (#184 G5, 14992cc1) reads the tenant and its bootstrap query: a single space whose events charge.
vi.mock('../../../lib/tenant', async (importOriginal) => ({ ...await importOriginal<typeof import('../../../lib/tenant')>(),
  useTenant: () => ({ mode: 'single', bootstrap: { charges_tracked: { events: true } } }) }))
function render(ui: Parameters<typeof rtlRender>[0], options?: Parameters<typeof rtlRender>[1]) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const wrapper = ({ children }: { children?: Parameters<typeof rtlRender>[0] }) => <QueryClientProvider client={client}>{children}</QueryClientProvider>
  return rtlRender(ui, { wrapper, ...options })
}
import bootstrap from '../../../../../backend/tests/events/programme/contracts/fixtures/public-url-bootstrap-v3.json'
import admission from '../../../../../backend/tests/events/programme/contracts/fixtures/application-admission-v3.json'
import { parseProgrammeContext } from '../contracts/parsers'
import { ApplicationEditor } from './ApplicationEditor'
import type { Application, FieldsProps } from './types'

function Fields({ value, onChange }: FieldsProps) {
  return <label>Institution<input value={String(value.answers.institution ?? '')}
    onChange={event => onChange({ ...value, answers: { institution: event.target.value } })} /></label>
}
function props() {
  const application = { ...bootstrap.virtual_draft, admission_requirements: admission.admission_requirements, optional_consent_purposes: ["mlh_data_sharing"] } as Application
  return { context: parseProgrammeContext(bootstrap.context), application, Fields, pending: false, error: null,
    onSave: vi.fn() }
}
describe('application consent review', () => {
  it('starts submitted edits from current sharing consent and sends a revocation', () => {
    const current = props()
    current.application = { ...current.application, optional_consents: { mlh_data_sharing: { accepted: true, version: 1, at: '2026-10-18T00:00:00Z' } } }
    render(<ApplicationEditor {...current} />)
    const sharing = screen.getByLabelText('I choose to share my submitted details with MLH (optional).')
    expect(sharing).toBeChecked()
    fireEvent.click(sharing)
    fireEvent.click(screen.getByText('Save draft'))
    expect(current.onSave).toHaveBeenCalledWith(expect.objectContaining({ optional_consents: { mlh_data_sharing: false } }), true)
  })
  it('clears consent when the waiver changes while preserving typed answers', () => {
    const current = props(), view = render(<ApplicationEditor {...current} />)
    fireEvent.change(screen.getByLabelText('Institution'), { target: { value: 'Maker College' } })
    fireEvent.click(screen.getByLabelText('I accept this host waiver.'))
    expect(screen.getByLabelText('I accept this host waiver.')).toBeChecked()
    const changed = { ...current, application: { ...current.application, admission_requirements: {
      ...current.application.admission_requirements, host_waiver: { ...admission.admission_requirements.host_waiver,
        version: 'host-2026-11', body: 'Updated waiver.' } } } }
    view.rerender(<ApplicationEditor {...changed} />)
    expect(screen.getByLabelText('I accept this host waiver.')).not.toBeChecked()
    expect(screen.getByLabelText('Institution')).toHaveValue('Maker College')
  })
  it('keeps code-of-conduct and host agreement as separate choices', () => {
    render(<ApplicationEditor {...props()} />)
    fireEvent.click(screen.getByLabelText('I agree to this code of conduct.'))
    expect(screen.getByLabelText('I accept this host waiver.')).not.toBeChecked()
    expect(screen.getByLabelText('I choose to share my submitted details with MLH (optional).')).not.toBeChecked()
  })
})

it('preserves a dirty draft across a version conflict until the owner explicitly reviews reapplication', () => {
  const current = props()
  const view = render(<ApplicationEditor {...current} />)
  fireEvent.change(screen.getByLabelText('Institution'), { target: { value: 'My unsaved school' } })
  view.rerender(<ApplicationEditor {...current} application={{ ...current.application, version: current.application.version + 1 }} />)
  expect(screen.getByLabelText('Institution')).toHaveValue('My unsaved school')
  expect(screen.getByRole('button', { name: 'Submit application' })).toBeDisabled()
  fireEvent.click(screen.getByRole('button', { name: 'Keep my draft and review the new version' }))
  fireEvent.click(screen.getByRole('button', { name: 'Save draft' }))
  expect(current.onSave).toHaveBeenCalledWith(expect.objectContaining({ expected_version: current.application.version + 1,
    answers: expect.objectContaining({ institution: 'My unsaved school' }) }), true)
})


describe('closed application action contracts', () => {
  function offered(reviewDate = false) {
    const current = props()
    const application: Application = { ...current.application, state: 'offered', version: 7,
      allowed_actions: ['rsvp', 'withdraw'], rsvp_accepted_at: null,
      admission_requirements: { ...current.application.admission_requirements, host_waiver: null },
      ...(reviewDate ? { answer_review: { event_date_revision: 19, as_of_date: '2026-11-07',
        date_review_required: true, locked: false } } : {}) }
    admissionFlow.mutate.mockReset()
    admissionFlow.useAdmission.mockReturnValue({ context: { data: current.context }, application: { data: application },
      prefill: {}, mutation: { mutate: admissionFlow.mutate, isPending: false, error: null } })
    render(<MemoryRouter><HackathonApplicationPage publicToken="public-event" accountId={4} Fields={Fields}
      onSignIn={() => undefined} onOrdinaryRegister={() => undefined} /></MemoryRouter>)
  }
  it.each([['Accept offer', 'accept'], ['Decline offer', 'decline'], ['Choose waitlist', 'waitlist']])(
    'sends the strict RSVP input when the owner clicks %s', (label, decision) => {
      offered()
      fireEvent.click(screen.getByRole('button', { name: label }))
      expect(admissionFlow.mutate).toHaveBeenCalledWith({ route: 'application_rsvp', body: { expected_version: 7, decision } })
    })
  it('keeps withdrawal on its dedicated command and reason', () => {
    offered()
    fireEvent.click(screen.getByRole('button', { name: 'Withdraw application' }))
    expect(admissionFlow.mutate).toHaveBeenCalledWith({ route: 'application_withdraw',
      body: { expected_version: 7, reason_code: 'participant_withdrew' } })
  })
  it('keeps explicit event-date review on its dedicated revision-checked command', () => {
    offered(true)
    fireEvent.click(screen.getByRole('checkbox', { name: 'I have reviewed my answers for this date.' }))
    fireEvent.click(screen.getByRole('button', { name: 'Confirm date review' }))
    expect(admissionFlow.mutate).toHaveBeenCalledWith({ route: 'application_date_review', body: {
      expected_version: 7, event_date_revision: 19, as_of_date: '2026-11-07', confirmed: true } })
  })
})
