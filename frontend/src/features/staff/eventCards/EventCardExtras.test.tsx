import { fireEvent, render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { beforeEach, expect, it, vi } from 'vitest'

const { request } = vi.hoisted(() => ({ request: vi.fn() }))
vi.mock('../../../lib/api', () => ({ staffRequest: request }))

import { EventCardExtras } from './EventCardExtras'

const mount = () => render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
  <EventCardExtras eventId={7} /></QueryClientProvider>)

beforeEach(() => { request.mockReset() })

it('reads shared emergency details only on an explicit click while the event switch is on', async () => {
  request.mockImplementation(async (path: string) => {
    if (path === '/admin/events/7/card-settings') return { extras_visible_to_organizers: true }
    if (path === '/admin/events/7/id-cards/extras') return [{ card_id: 3, name: 'Ada', blood_group: 'O+', emergency_contact_name: 'Bob', emergency_contact_phone: '+1 555' }]
    throw new Error(`Unexpected ${path}`)
  })
  mount()
  const show = await screen.findByRole('button', { name: 'Show emergency details' })
  expect(request.mock.calls.some(([path]) => path === '/admin/events/7/id-cards/extras')).toBe(false)
  fireEvent.click(show)
  expect(await screen.findByText('Blood group O+ · Contact Bob · +1 555')).toBeInTheDocument()
  expect(request).toHaveBeenCalledWith('/admin/events/7/id-cards/extras', { cache: 'no-store' })
})

it('offers no read while the switch is off and saves the switch through card settings', async () => {
  request.mockImplementation(async (path: string, init?: RequestInit) => {
    if (path === '/admin/events/7/card-settings' && !init) return { extras_visible_to_organizers: false }
    if (path === '/admin/events/7/card-settings') return JSON.parse(String(init?.body))
    throw new Error(`Unexpected ${path}`)
  })
  mount()
  const toggle = await screen.findByLabelText('Let organisers of this event see shared emergency details')
  expect(screen.queryByRole('button', { name: 'Show emergency details' })).toBeNull()
  fireEvent.click(toggle)
  expect(await screen.findByRole('button', { name: 'Show emergency details' })).toBeInTheDocument()
  expect(request).toHaveBeenCalledWith('/admin/events/7/card-settings', { method: 'PUT', body: JSON.stringify({ extras_visible_to_organizers: true }) })
})
