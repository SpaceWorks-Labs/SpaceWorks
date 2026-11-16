import { fireEvent, render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { beforeEach, expect, it, vi } from 'vitest'

const { request } = vi.hoisted(() => ({ request: vi.fn() }))
vi.mock('../../../lib/api', () => ({ staffRequest: request }))

import { EventOrdersList } from './EventOrdersList'

const order = {
  id: 31, kind: 'tickets', status: 'paid', event: 7, series: null, event_title: 'Robot night', currency: 'usd',
  subtotal: '20.00', discount_total: '0', fee_total: '1.50', total: '21.50', created_at: '2026-11-01T10:00:00Z',
  paid_at: '2026-11-01T10:05:00Z', checkout_url: '', payment_status: 'succeeded', payment_disputed: false, hold_expires_at: null,
  buyer: 5, buyer_name: 'Ada Buyer',
  lines: [{ id: 1, kind: 'ticket', label: 'General', quantity: 2, unit_amount: '10.00', line_total: '20.00' }],
  seats: [{ id: 9, event_id: 7, ticket_type_id: 1, status: 'unclaimed', attendee_email: 'guest@example.com', registration_id: null, invited_at: null, claimed_at: null }],
}

beforeEach(() => {
  request.mockReset()
  request.mockImplementation(async (path: string) => {
    if (path === '/admin/events/7/orders/?page=1') return { count: 1, next: null, previous: null, results: [order] }
    if (path === '/admin/event-orders/31/') return order
    throw new Error(`Unexpected path ${path}`)
  })
})

it('opens one order with its lines, fees and places from the order detail endpoint', async () => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(<QueryClientProvider client={client}><EventOrdersList eventId={7} /></QueryClientProvider>)
  fireEvent.click(await screen.findByRole('button', { name: 'View order #31' }))
  expect(await screen.findByRole('dialog', { name: 'Order #31' })).toBeInTheDocument()
  expect(request).toHaveBeenCalledWith('/admin/event-orders/31/')
  expect(await screen.findByText('2 × General')).toBeInTheDocument()
  expect(screen.getByText('Fees')).toBeInTheDocument()
  expect(screen.getByText('Not claimed yet')).toBeInTheDocument()
  expect(screen.getAllByText('guest@example.com').length).toBeGreaterThan(0)
})
