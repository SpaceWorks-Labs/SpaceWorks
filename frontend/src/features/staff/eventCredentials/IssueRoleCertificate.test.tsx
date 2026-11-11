import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { expect, it, vi } from 'vitest'
import { IssueRoleCertificate } from './IssueRoleCertificate'
import { staffRequest } from '../../../lib/api'
import type { RoleApplication } from '../../events/contributions/types'

vi.mock('../../../lib/api', async original => ({ ...await original<typeof import('../../../lib/api')>(), staffRequest: vi.fn() }))
it.each([['volunteer', 'volunteer_thanks'], ['mentor', 'mentor_thanks'], ['judge', 'judge_thanks']])('issues %s through the subject-aware certificate pipeline', async (role, kind) => {
  vi.mocked(staffRequest).mockReset().mockImplementation(async (_path, options) => options?.method === 'POST'
    ? { id: 9, state: 'queued' } as never : { eligible_count: 0, event_version: 7, disclosure: 'Event, date and status only.' } as never)
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(<QueryClientProvider client={client}><IssueRoleCertificate eventId={42} role={{ id: 81, event_id: 42, version: 4,
    state: 'completed', role, allowed_actions: [], posting_id: 12, save_intent: null } as RoleApplication} /></QueryClientProvider>)
  fireEvent.click(screen.getByRole('button', { name: 'Issue thank-you certificate' }))
  const confirm = await screen.findByRole('button', { name: 'Confirm issue' })
  await waitFor(() => expect(confirm).toBeEnabled())
  fireEvent.click(confirm)
  await screen.findByText(/Certificate issuance queued/)
  const call = vi.mocked(staffRequest).mock.calls.find(([, options]) => options?.method === 'POST')!
  expect(call[0]).toBe('/admin/events/42/certificates/bulk/')
  const body = JSON.parse(String(call[1]?.body))
  expect(body).toMatchObject({ expected_version: 7, all_attended: false, confirmed_count: 1, publish_event_details: false,
    subjects: [{ subject_kind: 'role_assignment', subject_id: 81, kind }] })
  expect(call[1]?.headers).toHaveProperty('Idempotency-Key', body.operation_id)
  client.clear()
})
