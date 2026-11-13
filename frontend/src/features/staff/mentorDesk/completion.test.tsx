import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, expect, it, vi } from 'vitest'
import type { ReactNode } from 'react'
import { expectNoA11yViolations } from '../../../test/axe'
const { request } = vi.hoisted(() => ({ request: vi.fn() }))
vi.mock('../../../lib/api', async () => ({ ...await vi.importActual<typeof import('../../../lib/api')>('../../../lib/api'), staffRequest: request, memberRequest: request }))
import { PostingEditor } from './PostingEditor'
import { ShiftEditor, type ShiftConfig } from './ShiftEditor'
import { MentorSettingsPanel, HelpCategoryEditor } from './MentorSettingsPanel'
import { MentorAttentionPanel } from './MentorAttentionPanel'
import { RoleLifecycleActions } from './RoleLifecycleActions'
import { RoleOwnerActions } from '../../events/contributions/RoleOwnerActions'
import { MentorAssignmentLifecycle } from './MentorAssignmentLifecycle'
import { MentorRoundSetup } from './MentorRoundSetup'

const scope = { accountId: 17, makerspaceId: 9, eventId: 42 }
const aggregate = { id: 81, event_id: 42, version: 4, state: 'approved' as const, allowed_actions: [] }
function mount(node: ReactNode) {
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>{node}</QueryClientProvider>)
}
beforeEach(() => { request.mockReset() })

it('uses the shared form-builder schema and retains a posting after a failed save', async () => {
  request.mockRejectedValue(new Error('Issuer authority changed'))
  const view = mount(<PostingEditor scope={scope} onSaved={vi.fn()} renderFormBuilder={({ onChange }) => <button type="button" onClick={() => onChange({ version: 2, questions: [] })}>Use shared form revision</button>} />)
  fireEvent.change(screen.getByLabelText('Posting title'), { target: { value: 'Bench crew' } })
  fireEvent.change(screen.getByLabelText('Applications open (your local time)'), { target: { value: '2026-12-01T09:00' } })
  fireEvent.change(screen.getByLabelText('Applications close (your local time)'), { target: { value: '2026-12-01T18:00' } })
  fireEvent.click(screen.getByRole('button', { name: 'Use shared form revision' }))
  fireEvent.click(screen.getByRole('button', { name: 'Save posting' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Issuer authority changed')
  expect(screen.getByLabelText('Posting title')).toHaveValue('Bench crew')
  expect(JSON.parse(request.mock.calls[0][1].body).form_schema).toEqual({ version: 2, questions: [] })
  expect(JSON.parse(request.mock.calls[0][1].body)).not.toHaveProperty('age_limit')
  await expectNoA11yViolations(view.container)
})

it('requires an explicit reason when cancelling office-hour bookings to reschedule', async () => {
  request.mockResolvedValue(aggregate)
  const row: ShiftConfig = { ...aggregate, id: 90, state: 'open', posting_id: 12, kind: 'office_hours',
    starts_at: '2026-12-01T05:00:00Z', ends_at: '2026-12-01T05:20:00Z', signup_deadline: '2026-12-01T04:00:00Z',
    task: 'PCB office hours', zone: 'B4', capacity: 2, available: 1, signup: null, mentor_assignment_id: 81,
    grace_minutes: 15, approval_required: false, waitlist_enabled: false, requirements: {}, permission_preset: [] }
  mount(<ShiftEditor scope={scope} initial={row} onSaved={vi.fn()} />)
  fireEvent.click(screen.getByLabelText('Cancel existing team bookings and notify teams before rescheduling'))
  expect(screen.getByLabelText('Reschedule reason')).toBeRequired()
  fireEvent.change(screen.getByLabelText('Reschedule reason'), { target: { value: 'Mentor travel delay' } })
  fireEvent.click(screen.getByRole('button', { name: 'Save shift' }))
  await waitFor(() => expect(request).toHaveBeenCalledTimes(1))
  const body = JSON.parse(request.mock.calls[0][1].body)
  expect(body.cancel_bookings).toBe(true)
  expect(body.reason).toBe('Mentor travel delay')
  expect(request.mock.calls[0][1].method).toBe('PATCH')
})

it('edits mentor capacity with a version and keeps input when rejected', async () => {
  request.mockResolvedValueOnce({ ...aggregate, state: 'active', assignment_id: 81, skills: ['pcb'], affiliation: '', availability: [], max_active_teams: 4 })
    .mockRejectedValue(new Error('End assignments before reducing capacity'))
  mount(<MentorSettingsPanel scope={scope} assignmentId={81} />)
  const input = await screen.findByLabelText('Maximum active teams (1–100)')
  fireEvent.change(input, { target: { value: '1' } })
  fireEvent.click(screen.getByRole('button', { name: 'Save mentor settings' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('End assignments')
  expect(input).toHaveValue(1)
  expect(JSON.parse(request.mock.calls[1][1].body)).toMatchObject({ max_active_teams: 1, expected_version: 4 })
})

it('configures bounded help expiry and open limits', async () => {
  request.mockResolvedValue(aggregate)
  mount(<HelpCategoryEditor scope={scope} />)
  fireEvent.change(screen.getByLabelText('Category key'), { target: { value: 'pcb' } })
  fireEvent.change(screen.getByLabelText('Category label'), { target: { value: 'PCB help' } })
  fireEvent.change(screen.getByLabelText('Claim lease minutes (1–60)'), { target: { value: '15' } })
  fireEvent.click(screen.getByRole('button', { name: 'Save help category' }))
  await waitFor(() => expect(request).toHaveBeenCalledTimes(1))
  expect(JSON.parse(request.mock.calls[0][1].body)).toMatchObject({ claim_minutes: 15, expiry_minutes: 240, open_limit: 1 })
})

it('keeps diagnostic comparison private to full event reports and mutes only own nudges', async () => {
  const analytics = { scope: 'own', per_round: [], attention: [], nudges: [], generosity: [{ mentor_assignment_id: 82, n: 99, mean: 4, z_score: 1 }], attention_preference: { version: 0, muted_until: null } }
  request.mockImplementation((path: string) => Promise.resolve(path.endsWith('/mentor-analytics/') ? analytics : aggregate))
  const view = mount(<MentorAttentionPanel scope={scope} />)
  await screen.findByText('Nudge preferences')
  expect(screen.queryByText('Private generosity diagnostic')).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Save nudge preference' }))
  await waitFor(() => expect(request.mock.calls.some(([path]) => path.endsWith('/mentor-attention/mute/'))).toBe(true))
  const body = JSON.parse(request.mock.calls.find(([path]) => path.endsWith('/mentor-attention/mute/'))![1].body)
  expect(body).toMatchObject({ expected_version: 0, minutes: 30 })
  await expectNoA11yViolations(view.container)
  view.unmount()
})

it('cannot reconfirm imported authority by skipping a fresh owner application', async () => {
  request.mockResolvedValue(aggregate)
  const view = mount(<RoleLifecycleActions scope={scope} row={{ ...aggregate, role: 'volunteer', posting_id: 12, save_intent: null, imported_inert: true }} />)
  expect(screen.queryByRole('button', { name: 'Admit contributor' })).not.toBeInTheDocument()
  fireEvent.change(screen.getByLabelText('Reason for application 81'), { target: { value: 'Confirm local requirements' } })
  fireEvent.click(screen.getByRole('button', { name: 'Request imported role reconfirmation' }))
  await waitFor(() => expect(request).toHaveBeenCalledTimes(1))
  expect(request.mock.calls[0][0]).toBe('/admin/events/42/roles/81/reconfirm/')
  expect(JSON.parse(request.mock.calls[0][1].body)).not.toHaveProperty('state')
  await expectNoA11yViolations(view.container)
})

it('keeps invitation decline on the owner member surface', async () => {
  request.mockResolvedValue({ ...aggregate, state: 'declined' })
  mount(<RoleOwnerActions scope={scope} row={{ ...aggregate, state: 'proposed', allowed_actions: ['decline'], role: 'volunteer', posting_id: 12, save_intent: null }} completionReady onSaved={vi.fn()} />)
  fireEvent.click(screen.getByRole('button', { name: 'Decline role invitation' }))
  await waitFor(() => expect(request).toHaveBeenCalledTimes(1))
  expect(request.mock.calls[0][0]).toBe('/member/makerspaces/9/events/42/role-applications/81/decline/')
  expect(JSON.parse(request.mock.calls[0][1].body)).not.toHaveProperty('member_id')
})

it('activates a proposed mapping with its own version', async () => {
  const mapping = { ...aggregate, state: 'proposed', mentor_assignment_id: 81, team_id: 21 }
  request.mockImplementation((path: string) => Promise.resolve(path.includes('?page=') ? { count: 1, next: null, previous: null, results: [mapping] } : { ...mapping, state: 'active' }))
  mount(<MentorAssignmentLifecycle scope={scope} />)
  fireEvent.click(await screen.findByRole('button', { name: 'Activate assignment' }))
  await waitFor(() => expect(request.mock.calls.some(([path]) => path.endsWith('/mentor-assignments/81/activate/'))).toBe(true))
  const body = JSON.parse(request.mock.calls.find(([path]) => path.endsWith('/activate/'))![1].body)
  expect(body.expected_version).toBe(4)
})

it('configures help triggers using shared-form question references', async () => {
  request.mockResolvedValue(aggregate)
  const view = mount(<MentorRoundSetup scope={scope} renderFormBuilder={() => <p>Shared form builder</p>} />)
  fireEvent.change(screen.getByLabelText('Round key'), { target: { value: 'progress' } })
  fireEvent.change(screen.getByLabelText('Round label'), { target: { value: 'Progress' } })
  fireEvent.change(screen.getByLabelText('Round opens (local time)'), { target: { value: '2026-12-01T09:00' } })
  fireEvent.change(screen.getByLabelText('Round closes (local time)'), { target: { value: '2026-12-01T10:00' } })
  fireEvent.click(screen.getByRole('button', { name: 'Add help trigger' }))
  for (const [label, value] of [['Trigger 1 key', 'followup'], ['Trigger 1 question ID', 'needs_help'], ['Trigger 1 help category key', 'pcb']]) {
    fireEvent.change(screen.getByLabelText(label), { target: { value } })
  }
  fireEvent.click(screen.getByRole('button', { name: 'Save round' }))
  await waitFor(() => expect(request).toHaveBeenCalledTimes(1))
  expect(JSON.parse(request.mock.calls[0][1].body).help_trigger_rules).toEqual([{ key: 'followup', question_id: 'needs_help', op: 'eq', value: true, type_key: 'pcb' }])
  await expectNoA11yViolations(view.container)
})
