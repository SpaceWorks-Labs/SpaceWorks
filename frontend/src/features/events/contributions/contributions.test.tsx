import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { ReactNode } from 'react'
import routes from '../../../../../backend/tests/events/programme/contracts/fixtures/routes-v3.json'
import { expectNoA11yViolations } from '../../../test/axe'

const { request } = vi.hoisted(() => ({ request: vi.fn() }))
vi.mock('../../../lib/api', async () => ({ ...await vi.importActual<typeof import('../../../lib/api')>('../../../lib/api'), memberRequest: request, staffRequest: request }))
import { HelpComposer } from './HelpComposer'
import { HelpQueue } from './HelpQueue'
import { basePath, programmeKey, useProgrammeCommand } from './api'
import { parseAggregate, parsePage } from './types'

const scope = { accountId: 17, makerspaceId: 9, eventId: 42 }
const row = { id: 601, event_id: 42, version: 1, state: 'open', allowed_actions: ['comment', 'cancel'], origin: 'team', team_alias: 'Bench A', category: 'PCB', zone: { table: 'B4' } }
function setup(node: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  return render(<QueryClientProvider client={client}>{node}</QueryClientProvider>)
}
beforeEach(() => { request.mockReset() })

describe('contributor and mentor HTTP consumers', () => {
  it('uses complete API v1 paths and keeps member/event caches distinct', () => {
    expect(basePath(scope, 'member')).toBe('/member/makerspaces/9/events/42')
    expect(basePath(scope, 'admin')).toBe('/admin/events/42')
    expect(programmeKey(scope, 'member')).not.toEqual(programmeKey({ ...scope, accountId: 18 }, 'member'))
    expect(programmeKey(scope, 'member')).not.toEqual(programmeKey(scope, 'admin'))
  })

  it('accepts the frozen owner help response and refuses malformed aggregates', () => {
    const route = routes.routes.find(x => x.name === 'events-programme-member-help-collection')!
    expect(parseAggregate(route.operations.POST!.response_example as unknown as typeof row).origin).toBe('team')
    expect(() => parseAggregate({ ...row, id: -1 })).toThrow(/invalid response/)
  })

  it('preserves minimal frozen posting and office-hour cards without fabricating a version', () => {
    for (const name of ['events-programme-member-role-posting-list', 'events-programme-member-office-hours-list']) {
      const route = routes.routes.find(x => x.name === name)!
      const page = route.operations.GET!.response_example as unknown as import('./types').Page<import('./types').Aggregate>
      expect(parsePage(page)).toEqual(page)
    }
  })

  it('renders a safe queue without fetching private descriptions', async () => {
    request.mockResolvedValue({ count: 1, next: null, previous: null, results: [row] })
    const view = setup(<HelpQueue scope={scope} onOpen={vi.fn()} />)
    expect(await screen.findByText('PCB · Bench A')).toBeVisible()
    expect(request).toHaveBeenCalledWith('/member/makerspaces/9/events/42/help/?page=1')
    expect(screen.queryByRole('button', { name: 'Claim request' })).not.toBeInTheDocument()
    await expectNoA11yViolations(view.container)
  })

  it('mentor raises a team-specific request with no impersonation or silent claim', async () => {
    request.mockResolvedValue({ ...row, origin: 'mentor' })
    setup(<HelpComposer scope={scope} surface="admin" teams={[{ id: 21, label: 'Bench A' }]} categories={[{ key: 'pcb', label: 'PCB' }]} />)
    fireEvent.change(screen.getByLabelText('What do you need help with?'), { target: { value: 'Check our sensor wiring' } })
    fireEvent.click(screen.getByRole('button', { name: 'Request help' }))
    await waitFor(() => expect(request).toHaveBeenCalledTimes(1))
    const [path, options] = request.mock.calls[0]
    const body = JSON.parse(options.body)
    expect(path).toBe('/admin/events/42/help/')
    expect(body.team_id).toBe(21); expect(body.expected_version).toBe(0)
    expect(body).not.toHaveProperty('origin'); expect(body).not.toHaveProperty('claimed_by')
    expect(options.headers['Idempotency-Key']).toBe(body.operation_id)
  })

  it('keeps entered help text after a conflict', async () => {
    request.mockRejectedValue(new Error('The queue changed'))
    setup(<HelpComposer scope={scope} surface="member" teams={[{ id: 21, label: 'Bench A' }]} categories={[{ key: 'pcb', label: 'PCB' }]} />)
    fireEvent.change(screen.getByLabelText('What do you need help with?'), { target: { value: 'Keep this draft' } })
    fireEvent.click(screen.getByRole('button', { name: 'Request help' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('The queue changed')
    expect(screen.getByLabelText('What do you need help with?')).toHaveValue('Keep this draft')
  })

  it('reuses the operation UUID for an unchanged network retry', async () => {
    request.mockRejectedValue(new Error('Temporary failure'))
    function Retry() {
      const command = useProgrammeCommand(scope, 'member')
      return <button onClick={() => command.mutate({ path: '/help/601/cancel/', version: 1 })}>Retry</button>
    }
    setup(<Retry />)
    fireEvent.click(screen.getByText('Retry'))
    await waitFor(() => expect(request).toHaveBeenCalledTimes(1))
    fireEvent.click(screen.getByText('Retry'))
    await waitFor(() => expect(request).toHaveBeenCalledTimes(2))
    expect(JSON.parse(request.mock.calls[0][1].body).operation_id).toBe(JSON.parse(request.mock.calls[1][1].body).operation_id)
  })
})
