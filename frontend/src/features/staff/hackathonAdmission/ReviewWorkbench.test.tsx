import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { staffRequest } from '../../../lib/api'
import { ReviewWorkbench } from './ReviewWorkbench'
vi.mock('../../../lib/api', () => ({ memberRequest: vi.fn(), staffRequest: vi.fn() }))
afterEach(() => vi.clearAllMocks())

const assignment = { id: 81, event_id: 42, version: 1, state: 'assigned', round: 1,
  allowed_actions: ['submit', 'recuse'], rubric: { revision: 1, criteria: [{ key: 'craft', label: 'Craft',
    anchors: { '1': 'Starting', '2': 'Developing', '3': 'Clear', '4': 'Strong', '5': 'Exceptional' } }] },
  applications: [{ id: 61, event_id: 42, version: 1, state: 'submitted', alias: 'Applicant SAFE', blind: true,
    blind_notice: 'Free text can reveal identity.', answers: [{ id: 'idea', label: 'Your idea', type: 'short_text', value: 'A repair jig' }] }] }

describe('anchored reviewer workbench', () => {
  it('replaces answers with the safe recusal response without a forbidden GET', async () => {
    const request = vi.mocked(staffRequest)
    request.mockResolvedValueOnce(assignment).mockResolvedValueOnce({ ...assignment, state: 'recused', version: 2, allowed_actions: [], applications: [] })
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(<QueryClientProvider client={client}><ReviewWorkbench eventId={42} reviewId={81} /></QueryClientProvider>)
    await screen.findByText('A repair jig')
    fireEvent.click(screen.getByRole('button', { name: 'Recuse from this application' }))
    await screen.findByText('Your recusal is recorded. This application has been removed from your review.')
    expect(screen.queryByText('A repair jig')).not.toBeInTheDocument()
    expect(request).toHaveBeenCalledTimes(2)
    expect(client.getQueryData(['application-review', 42, 81])).toMatchObject({ state: 'recused', applications: [] })
  })
  it('shows anchors and sends scores without another identity or reviewer data', async () => {
    const request = vi.mocked(staffRequest)
    request.mockResolvedValue(assignment)
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(<QueryClientProvider client={client}><ReviewWorkbench eventId={42} reviewId={81} /></QueryClientProvider>)
    await screen.findByText('A repair jig')
    expect(screen.getByText('Applicant SAFE')).toBeInTheDocument()
    fireEvent.click(screen.getByLabelText('3 · Clear'))
    fireEvent.change(screen.getByLabelText('Private review notes'), { target: { value: 'Clear workshop use.' } })
    fireEvent.click(screen.getByRole('button', { name: 'Submit review' }))
    await waitFor(() => expect(request.mock.calls.some(call => call[1]?.method === 'PATCH')).toBe(true))
    const patch = request.mock.calls.find(call => call[1]?.method === 'PATCH')!
    expect(JSON.parse(patch[1]!.body as string)).toMatchObject({ expected_version: 1, scores: { craft: 3 }, notes: 'Clear workshop use.' })
    expect(JSON.parse(patch[1]!.body as string)).not.toHaveProperty('member_id')
  })
})
