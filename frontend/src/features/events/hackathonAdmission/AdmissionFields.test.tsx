import { fireEvent, render as rtlRender, screen } from '@testing-library/react'
import { useState } from 'react'
import { describe, expect, it, vi } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
// useChargesOn (#184 G5, 14992cc1) reads the tenant and its bootstrap query: a single space whose events charge.
vi.mock('../../../lib/tenant', async (importOriginal) => ({ ...await importOriginal<typeof import('../../../lib/tenant')>(),
  useTenant: () => ({ mode: 'single', bootstrap: { charges_tracked: { events: true } } }) }))
function render(ui: Parameters<typeof rtlRender>[0], options?: Parameters<typeof rtlRender>[1]) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const wrapper = ({ children }: { children?: Parameters<typeof rtlRender>[0] }) => <QueryClientProvider client={client}>{children}</QueryClientProvider>
  return rtlRender(ui, { wrapper, ...options })
}
import admission from '../../../../../backend/tests/events/programme/contracts/fixtures/application-admission-v3.json'
import { AdmissionFields } from './AdmissionFields'
import type { AdmissionRequirements, AdmissionSelection } from './types'

function Harness() {
  const [value, set] = useState<AdmissionSelection>({})
  return <><AdmissionFields requirements={admission.admission_requirements as AdmissionRequirements} value={value} onChange={set} disabled={false} />
    <output data-testid="selection">{JSON.stringify(value)}</output></>
}
describe('reviewed admission controls', () => {
  it('has no silent ticket or waiver acceptance and keeps the version opaque', () => {
    render(<Harness />)
    expect(screen.getByRole('combobox', { name: 'Ticket' })).toHaveValue('')
    expect(screen.getByRole('checkbox', { name: 'I accept this host waiver.' })).not.toBeChecked()
    fireEvent.change(screen.getByRole('combobox', { name: 'Ticket' }), { target: { value: '8' } })
    fireEvent.click(screen.getByRole('checkbox', { name: 'I accept this host waiver.' }))
    expect(JSON.parse(screen.getByTestId('selection').textContent!)).toMatchObject({ ticket_type_id: 8,
      host_waiver_id: 13, host_waiver_version: 'host-2026-10', host_waiver_accepted: true })
  })
  it('renders contact fallbacks independently from application questions', () => {
    render(<Harness />)
    expect(screen.getByLabelText('Contact email')).toBeRequired()
    expect(screen.getByLabelText('Contact phone')).toHaveAttribute('maxlength', '64')
    expect(screen.getByLabelText('Invitation code (optional)')).toHaveAttribute('autocomplete', 'off')
  })
})
