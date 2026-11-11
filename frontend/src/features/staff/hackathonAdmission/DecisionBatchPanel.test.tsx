import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { staffRequest } from '../../../lib/api'
import { DecisionBatchPanel } from './DecisionBatchPanel'
vi.mock('../../../lib/api', () => ({ memberRequest: vi.fn(), staffRequest: vi.fn() }))

afterEach(() => vi.clearAllMocks())
describe('private batch release', () => {
  it('recovers an existing private draft without staging another batch', async () => {
    const request = vi.mocked(staffRequest)
    request.mockResolvedValueOnce({ id: 8, event_id: 42, version: 1, state: 'draft', allowed_actions: ['release', 'cancel'], decisions: [] })
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(<QueryClientProvider client={client}><DecisionBatchPanel eventId={42} selections={[]} resumeBatchId={8} onReleased={vi.fn()} /></QueryClientProvider>)
    fireEvent.click(screen.getByRole('button', { name: 'Resume private batch #8' }))
    await screen.findByRole('button', { name: 'Release this batch' })
    expect(request).toHaveBeenCalledOnce()
    expect(request.mock.calls[0][0]).toBe('/admin/events/42/application-decisions/8/')
    expect(request.mock.calls[0][1]?.method).not.toBe('POST')
  })
  it('stages first and releases only the exact returned batch on an explicit second action', async () => {
    const request = vi.mocked(staffRequest), onReleased = vi.fn()
    request.mockResolvedValueOnce({ id: 8, event_id: 42, version: 1, state: 'draft', allowed_actions: ['release', 'cancel'],
      decisions: [{ id: 9, application_id: 61, cohort_id: null, expected_version: 1, outcome: 'offer', reason_code: 'review_complete' }] })
      .mockResolvedValueOnce({ id: 8, event_id: 42, version: 2, state: 'committed', allowed_actions: [], decisions: [] })
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(<QueryClientProvider client={client}><DecisionBatchPanel eventId={42} selections={[
      { application_id: 61, expected_version: 1, outcome: 'offer', reason_code: 'review_complete' }]} onReleased={onReleased} /></QueryClientProvider>)
    fireEvent.click(screen.getByRole('button', { name: 'Stage private decisions' }))
    await screen.findByRole('button', { name: 'Release this batch' })
    expect(request).toHaveBeenCalledTimes(1)
    expect(request.mock.calls[0][0]).toBe('/admin/events/42/application-decisions/stage/')
    expect(onReleased).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole('button', { name: 'Release this batch' }))
    await waitFor(() => expect(onReleased).toHaveBeenCalledOnce())
    const command = JSON.parse(request.mock.calls[1][1]!.body as string)
    expect(command).toMatchObject({ batch_id: 8, expected_version: 1 })
    expect(command).not.toHaveProperty('decisions')
  })
})
