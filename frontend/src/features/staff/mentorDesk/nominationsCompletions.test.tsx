import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, expect, it, vi } from 'vitest'
import type { ReactNode } from 'react'
const { request } = vi.hoisted(() => ({ request: vi.fn() }))
vi.mock('../../../lib/api', async () => ({ ...await vi.importActual<typeof import('../../../lib/api')>('../../../lib/api'), staffRequest: request, memberRequest: request }))
import { MentorRoundsPanel } from './MentorRoundsPanel'
import { RoleLifecycleActions } from './RoleLifecycleActions'

const scope = { accountId: 17, makerspaceId: 9, eventId: 42 }
function mount(node: ReactNode) {
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>{node}</QueryClientProvider>)
}
beforeEach(() => { request.mockReset() })

it('nominates a visited team through the round nominations route with the round version', async () => {
  const round = { id: 5, event_id: 42, version: 3, state: 'live', allowed_actions: [], label: 'Round one',
    closes_at: '2099-01-01T00:00:00Z', form_schema: {},
    teams: [{ team_id: 21, team_alias: 'Bench A', visit_state: 'done', lease: null, prior_notes: [] },
      { team_id: 22, team_alias: 'Bench B', visit_state: 'open', lease: null, prior_notes: [] }] }
  request.mockImplementation(async (path: string, init?: RequestInit) => {
    if (path === '/admin/events/42/mentor-rounds/5/' && !init?.method) return round
    if (path === '/admin/events/42/mentor-rounds/5/nominations/') return { id: 1, event_id: 42, version: 1, state: 'recorded', allowed_actions: [] }
    throw new Error(`Unexpected ${path}`)
  })
  mount(<MentorRoundsPanel scope={scope} roundId={5} sessionId="s" renderForm={() => null} />)
  fireEvent.click(await screen.findByRole('button', { name: 'Nominate Bench A' }))
  expect(screen.queryByRole('button', { name: 'Nominate Bench B' })).toBeNull()
  await waitFor(() => expect(request).toHaveBeenCalledWith('/admin/events/42/mentor-rounds/5/nominations/', expect.anything()))
  const call = request.mock.calls.find(([path]) => path === '/admin/events/42/mentor-rounds/5/nominations/')!
  expect(JSON.parse(call[1].body)).toMatchObject({ team_id: 21, expected_version: 3 })
  expect(await screen.findByRole('button', { name: 'Nominated' })).toBeDisabled()
})

it('records a second-person requirement completion for an approved role', async () => {
  request.mockResolvedValue({ id: 3, event_id: 42, version: 1, state: 'recorded', allowed_actions: [] })
  const row = { id: 81, event_id: 42, version: 4, state: 'approved', allowed_actions: [], role: 'volunteer', posting_id: 12, save_intent: null }
  mount(<RoleLifecycleActions scope={scope} row={row as never} />)
  fireEvent.change(screen.getByLabelText('Completed kind for application 81'), { target: { value: 'briefing' } })
  fireEvent.change(screen.getByLabelText('Completed requirement ID for application 81'), { target: { value: '7' } })
  fireEvent.click(screen.getByRole('button', { name: 'Record completion' }))
  await waitFor(() => expect(request).toHaveBeenCalledTimes(1))
  expect(request.mock.calls[0][0]).toBe('/admin/events/42/roles/81/requirement-completions/')
  expect(JSON.parse(request.mock.calls[0][1].body)).toMatchObject({ kind: 'briefing', reference_id: 7, expected_version: 4 })
  expect(await screen.findByText('Completion of requirement 7 recorded.')).toBeInTheDocument()
})

it('never arms a timer beyond the 32-bit limit for a round that closes far in the future', async () => {
  // A longer delay is clamped to 1 ms by the browser, which would clear the drafts of a round that is still live.
  const round = { id: 5, event_id: 42, version: 3, state: 'live', allowed_actions: [], label: 'Round one',
    closes_at: '2099-01-01T00:00:00Z', form_schema: {}, teams: [] }
  request.mockResolvedValue(round)
  const arm = vi.spyOn(window, 'setTimeout')
  mount(<MentorRoundsPanel scope={scope} roundId={5} sessionId="s" renderForm={() => null} />)
  await screen.findByText('Round one')
  const delays = arm.mock.calls.map(([, ms]) => Number(ms ?? 0))
  expect(delays.filter((ms) => ms > 2_000_000_000)).toEqual([2_147_483_647])
  expect(Math.max(...delays)).toBe(2_147_483_647)
  arm.mockRestore()
})
