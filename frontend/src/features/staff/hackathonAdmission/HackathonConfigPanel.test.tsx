import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { staffRequest } from '../../../lib/api'
import { HackathonConfigPanel } from './HackathonConfigPanel'

vi.mock('../../../lib/api', async original => ({ ...await original<typeof import('../../../lib/api')>(), staffRequest: vi.fn(), memberRequest: vi.fn() }))
vi.mock('./RubricEditor', () => ({ RubricEditor: () => <div>rubric editor</div> }))
vi.mock('./MlhPresetPicker', () => ({ MlhPresetPicker: () => <div>mlh picker</div> }))

const config = (over = {}) => ({ id: 1, event_id: 42, version: 5, state: 'open', enabled: true, review_mode: 'rolling', review_count: 2, rsvp_days: 4,
  team_mode: 'individual_then_team', team_min: 1, team_max: 4, finder_enabled: false, blind_review: false, team_eligibility: 'confirmed',
  attendance_required: true, late_policy: 'reject', submission_grace_minutes: 0, review_rubric: { revision: 1, criteria: [] }, application_form: [],
  offer_capacity: null, coc: { body: 'Be kind.' }, counts: { offered: 3, confirmed: 2, hard_spots_left: null }, allowed_actions: [],
  submission_opens_at: null, submission_deadline: null, ...over })

function mount(opts: { stages?: number; cfg?: object | Error } = {}) {
  vi.mocked(staffRequest).mockReset().mockImplementation(async (path: string, init?: RequestInit) => {
    if (path.includes('submission-stages')) return { stages: Array.from({ length: opts.stages ?? 1 }, (_, i) => ({ id: i })) } as never
    if (init?.method === 'PATCH') return config() as never
    if (opts.cfg instanceof Error) throw opts.cfg
    return (opts.cfg ?? config()) as never
  })
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <HackathonConfigPanel eventId={42} FormEditor={() => <div>form editor</div>} mlhPresets={[]} /></QueryClientProvider>)
}
const saveButton = () => screen.getByRole('button', { name: 'Save admission settings' })
beforeEach(() => vi.clearAllMocks())

describe('HackathonConfigPanel', () => {
  it('loads the config into the form with Save disabled until something changes', async () => {
    mount()
    expect(await screen.findByLabelText('Days to RSVP after release')).toHaveValue(4)
    expect(screen.getByLabelText('Code of conduct')).toHaveValue('Be kind.')
    expect(screen.getByText(/3 offers · 2 confirmed/)).toBeTruthy()
    expect(saveButton()).toBeDisabled()
    expect(screen.queryByText('You have unsaved changes.')).toBeNull()
  })

  it('PATCHes edited fields with the loaded version, an idempotency key, and no coc_body when conduct is unchanged', async () => {
    mount()
    const rsvp = await screen.findByLabelText('Days to RSVP after release')
    fireEvent.change(rsvp, { target: { value: '7' } })
    fireEvent.change(screen.getByLabelText(/Offer ceiling/), { target: { value: '60' } })
    expect(screen.getByText('You have unsaved changes.')).toBeTruthy()
    fireEvent.click(saveButton())
    await waitFor(() => expect(vi.mocked(staffRequest).mock.calls.some(([, o]) => o?.method === 'PATCH')).toBe(true))
    const [path, init] = vi.mocked(staffRequest).mock.calls.find(([, o]) => o?.method === 'PATCH')!
    expect(path).toBe('/admin/events/42/hackathon/')
    const body = JSON.parse(String(init?.body))
    expect(body).toMatchObject({ rsvp_days: 7, offer_capacity: 60, expected_version: 5 })
    expect(body).not.toHaveProperty('coc_body')
    expect(body).not.toHaveProperty('counts')
    expect((init?.headers as Record<string, string>)['Idempotency-Key']).toBe(body.operation_id)
  })

  it('sends coc_body only when the code of conduct text changed', async () => {
    mount()
    fireEvent.change(await screen.findByLabelText('Code of conduct'), { target: { value: 'Be excellent.' } })
    fireEvent.click(saveButton())
    await waitFor(() => expect(vi.mocked(staffRequest).mock.calls.some(([, o]) => o?.method === 'PATCH')).toBe(true))
    const init = vi.mocked(staffRequest).mock.calls.find(([, o]) => o?.method === 'PATCH')![1]
    expect(JSON.parse(String(init?.body)).coc_body).toBe('Be excellent.')
  })

  it('leaves submission windows to the stage planner when the event has several stages', async () => {
    mount({ stages: 2 })
    await screen.findByLabelText('Days to RSVP after release')
    await waitFor(() => expect(screen.queryByLabelText('Late submission policy')).toBeNull())
    expect(screen.queryByLabelText('Submission deadline (UTC)')).toBeNull()
    expect(screen.getByLabelText('Applications open (UTC)')).toBeTruthy()
    expect(screen.getByText(/several submission stages/)).toBeTruthy()
  })

  it('shows the load error with a retry', async () => {
    mount({ cfg: new Error('Config unavailable.') })
    expect(await screen.findByText(/Config unavailable/)).toBeTruthy()
  })
})
