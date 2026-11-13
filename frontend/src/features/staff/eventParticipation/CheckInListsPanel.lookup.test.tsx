import { fireEvent, render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { beforeEach, expect, it, vi } from 'vitest'

const { request } = vi.hoisted(() => ({ request: vi.fn() }))
vi.mock('../../../lib/api', async () => ({ ...await vi.importActual<typeof import('../../../lib/api')>('../../../lib/api'), staffRequest: request }))

import { CheckInListsPanel } from './CheckInListsPanel'

const list = { id: 4, event_id: 9, name: 'Lunch', kind: 'meal', after_entry: true, addon_id: null, addon_name: null,
  per_person: 1, archived: false, collected: 3 }

beforeEach(() => {
  request.mockReset()
  request.mockImplementation(async (path: string, init?: RequestInit) => {
    if (path === '/admin/events/9/checkin-lists/') return [list]
    if (path === '/admin/events/9/checkin-lists/4/lookup/?registration_id=77' && !init)
      return { registration_id: 77, name: 'Grace', allowed: 1, used: 1, reason: 'already_collected' }
    throw new Error(`Unexpected path ${path}`)
  })
})

it('checks eligibility read-only before recording a collection', async () => {
  render(<QueryClientProvider client={new QueryClient()}><CheckInListsPanel eventId={9} canManage={false} addons={[]} /></QueryClientProvider>)
  fireEvent.click(await screen.findByRole('button', { name: 'Collect' }))
  fireEvent.change(screen.getByLabelText('Registration number'), { target: { value: '77' } })
  fireEvent.click(screen.getByRole('button', { name: 'Check first' }))
  expect(await screen.findByText(/Grace: 1 of 1 collected\. Already collected everything\./)).toBeInTheDocument()
  // Nothing was recorded: no POST to the scan route.
  expect(request.mock.calls.some(([path]) => String(path).includes('/scan/'))).toBe(false)
})
