import { act, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, expect, it, vi } from 'vitest'

const api = vi.hoisted(() => ({ getAccessToken: vi.fn(), refreshAccessToken: vi.fn(), publicV1Request: vi.fn(), memberRequest: vi.fn() }))
vi.mock('../../../lib/api', async original => ({ ...await original<typeof import('../../../lib/api')>(), ...api }))
vi.mock('../../members/MemberAuthPanel', () => ({ MemberAuthPanel: () => <p>Programme member sign-in panel</p> }))
vi.mock('../../../components/photo-crop/PhotoPicker', () => ({ PhotoPicker: () => null }))
import { JoinPage } from './JoinPage'

const programme = { name: 'Synthetic programme', organization_name: 'Synthetic organization', description: '',
  photo_mode: 'none', registration_open: true, questions: [], requires_approval: true }
function show() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(<QueryClientProvider client={client}><MemoryRouter initialEntries={['/o/synthetic/ids/acceptance']}>
    <Routes><Route path="/o/:organizationSlug/ids/:programmeSlug" element={<JoinPage />} /></Routes>
  </MemoryRouter></QueryClientProvider>)
}
beforeEach(() => { vi.clearAllMocks(); api.getAccessToken.mockReturnValue(null) })

it('restores the person cookie before the first personalized programme read on reload', async () => {
  let finish!: (value: boolean) => void
  api.refreshAccessToken.mockReturnValue(new Promise<boolean>(resolve => { finish = resolve }))
  api.publicV1Request.mockResolvedValue({ ...programme, state: 'approved' })
  show()
  expect(api.publicV1Request).not.toHaveBeenCalled()
  expect(screen.queryByText('Programme member sign-in panel')).toBeNull()
  await waitFor(() => expect(api.refreshAccessToken).toHaveBeenCalledWith('person'))
  await act(async () => { finish(true) })
  expect(await screen.findByRole('heading', { name: 'Approved — see your card' })).toBeVisible()
  expect(api.publicV1Request).toHaveBeenCalledWith('/public/organizations/synthetic/id-programmes/acceptance')
})

it('keeps the platform session separate and shows anonymous sign-in after a refused person refresh', async () => {
  api.getAccessToken.mockImplementation(context => context === 'platform' ? 'existing-platform-session' : null)
  api.refreshAccessToken.mockResolvedValue(false)
  api.publicV1Request.mockResolvedValue({ ...programme, state: 'signed_out' })
  show()
  expect(await screen.findByText('Programme member sign-in panel')).toBeVisible()
  expect(api.getAccessToken.mock.calls.every(([context]) => context === 'person')).toBe(true)
  expect(api.refreshAccessToken).toHaveBeenCalledExactlyOnceWith('person')
  expect(api.memberRequest).not.toHaveBeenCalled()
})

it('settles a failed refresh as anonymous instead of trapping the public programme loading', async () => {
  api.refreshAccessToken.mockRejectedValue(new Error('Unavailable refresh'))
  api.publicV1Request.mockResolvedValue({ ...programme, state: 'signed_out' })
  show()
  expect(await screen.findByText('Programme member sign-in panel')).toBeVisible()
})

it('uses an existing person session without refreshing another account context', async () => {
  api.getAccessToken.mockReturnValue('existing-person-session')
  api.publicV1Request.mockResolvedValue({ ...programme, state: 'waiting' })
  show()
  expect(await screen.findByRole('heading', { name: 'Waiting for approval' })).toBeVisible()
  expect(api.refreshAccessToken).not.toHaveBeenCalled()
})
