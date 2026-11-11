import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const request = vi.hoisted(() => vi.fn())
vi.mock('../../../lib/api', async () => ({ ...await vi.importActual<typeof import('../../../lib/api')>('../../../lib/api'), staffRequest: request }))
import { VolunteerManager } from './VolunteerManager'

const scope = { accountId: 17, makerspaceId: 9, eventId: 42 }
const envelope = { event_id: 42, state: 'open', version: 1, allowed_actions: [], created_at: '2026-11-01T10:00:00Z', updated_at: '2026-11-01T10:00:00Z' }
const shift = { ...envelope, id: 5, posting_id: 1, kind: 'volunteer_shift', starts_at: '2026-11-20T10:00:00Z', ends_at: '2026-11-20T12:00:00Z',
  task: 'Front desk', zone: '', capacity: 4, available: 2, signup: null, mentor_card: null }
const signup = (over: object) => ({ ...envelope, state: 'approved', shift_id: 5, attendance: null, verified_minutes: null, member_id: 31, assignment_id: 8, ...over })

function show(signups: object[]) {
  request.mockImplementation(async (path: string) => path.includes('/shifts/5/') ? { ...shift, signups }
    : { count: 1, next: null, previous: null, results: [shift] })
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><VolunteerManager scope={scope} /></QueryClientProvider>)
  fireEvent.click(screen.getByRole('tab', { name: 'Shifts and hours' }))
}

beforeEach(() => { request.mockReset() })

describe('VolunteerManager shift signups (EV-30)', () => {
  it('names the volunteer instead of showing only ids', async () => {
    show([signup({ id: 3, member_name: 'Asha Rao' })])
    fireEvent.click(await screen.findByRole('button', { name: 'View signups and hours' }))
    expect(await screen.findByRole('heading', { name: 'Asha Rao · Application 8' })).toBeTruthy()
  })

  it('falls back to the member id when the server sends no name', async () => {
    show([signup({ id: 4 })])
    fireEvent.click(await screen.findByRole('button', { name: 'View signups and hours' }))
    expect(await screen.findByRole('heading', { name: 'Member 31 · Application 8' })).toBeTruthy()
  })
})
