import { fireEvent, render, renderHook, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { staffRequest, StructuredApiError } from '../../../lib/api'
import { HackathonConfigPanel } from './HackathonConfigPanel'
import { mlhPresetsPath, readMlhPresets, useMlhPresets } from './mlhPresets'

vi.mock('../../../lib/api', async original => ({ ...await original<typeof import('../../../lib/api')>(), staffRequest: vi.fn(), memberRequest: vi.fn() }))
vi.mock('./RubricEditor', () => ({ RubricEditor: () => <div>rubric editor</div> }))

const schema = { schema_version: 2 as const, form_id: 'mlh-application', revision: 3, questions: [{ id: 'build', type: 'long_text', label: 'What will you build?' }] }
const preset = { id: 'mlh-2026', label: 'MLH application', schema }
const config = { id: 1, event_id: 42, version: 5, state: 'open', enabled: true, review_mode: 'rolling', review_count: 2, rsvp_days: 4,
  team_mode: 'individual_then_team', team_min: 1, team_max: 4, finder_enabled: false, blind_review: false, team_eligibility: 'confirmed',
  attendance_required: true, late_policy: 'reject', submission_grace_minutes: 0, review_rubric: { revision: 1, criteria: [] }, application_form: [],
  offer_capacity: null, coc: { body: 'Be kind.' }, counts: null, allowed_actions: [], optional_mlh_schema: {} }
const client = () => new QueryClient({ defaultOptions: { queries: { retry: false } } })
const wrapper = ({ children }: { children: ReactNode }) => <QueryClientProvider client={client()}>{children}</QueryClientProvider>

beforeEach(() => { vi.mocked(staffRequest).mockReset() })

describe('MLH presets (EP-9)', () => {
  it('reads a list or a page and drops malformed rows', () => {
    expect(readMlhPresets([preset, { id: 'bad', label: 'Bad', schema: { schema_version: 1 } }])).toEqual([preset])
    expect(readMlhPresets({ results: [preset] })).toEqual([preset])
    expect(readMlhPresets({ detail: 'nope' })).toEqual([])
  })

  it('loads the presets from the server and falls back to none when the route is missing', async () => {
    vi.mocked(staffRequest).mockResolvedValueOnce([preset] as never)
    const loaded = renderHook(() => useMlhPresets(42, true), { wrapper })
    await waitFor(() => expect(loaded.result.current).toEqual([preset]))
    expect(staffRequest).toHaveBeenCalledWith(mlhPresetsPath(42))

    vi.mocked(staffRequest).mockRejectedValueOnce(new StructuredApiError(404, { detail: 'Not found.' }))
    const missing = renderHook(() => useMlhPresets(43, true), { wrapper })
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith(mlhPresetsPath(43)))
    expect(missing.result.current).toEqual([])
  })

  it('lets staff turn on MLH sharing by choosing a preset and saving it', async () => {
    vi.mocked(staffRequest).mockImplementation(async (path: string) =>
      (path.includes('submission-stages') ? { stages: [{ id: 1 }] } : config) as never)
    render(<QueryClientProvider client={client()}>
      <HackathonConfigPanel eventId={42} FormEditor={() => <div>form editor</div>} mlhPresets={[preset]} /></QueryClientProvider>)
    fireEvent.change(await screen.findByLabelText('Application preset'), { target: { value: 'mlh-2026' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save admission settings' }))
    await waitFor(() => expect(vi.mocked(staffRequest).mock.calls.some(([, o]) => o?.method === 'PATCH')).toBe(true))
    const body = JSON.parse(String(vi.mocked(staffRequest).mock.calls.find(([, o]) => o?.method === 'PATCH')![1]?.body))
    expect(body).toMatchObject({ optional_mlh_schema: schema, application_form: schema })
  })

  it('explains when no preset is available', async () => {
    vi.mocked(staffRequest).mockImplementation(async (path: string) => (path.includes('submission-stages') ? { stages: [] } : config) as never)
    render(<QueryClientProvider client={client()}>
      <HackathonConfigPanel eventId={42} FormEditor={() => <div>form editor</div>} mlhPresets={[]} /></QueryClientProvider>)
    expect(await screen.findByText(/No MLH presets are available on this server/)).toBeTruthy()
  })
})
