import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
const { request } = vi.hoisted(() => ({ request: vi.fn() }))
vi.mock('../../../lib/api', async () => ({ ...await vi.importActual<typeof import('../../../lib/api')>('../../../lib/api'), staffRequest: request }))
import { MentorAssignmentsPanel } from './MentorAssignmentsPanel'
import { TeamImportPanel } from './TeamImportPanel'
import { saveRoundDraft } from './roundDrafts'
import { expectNoA11yViolations } from '../../../test/axe'

const scope = { accountId: 17, makerspaceId: 9, eventId: 42 }
function wrapper(children: React.ReactNode) {
  return render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>{children}</QueryClientProvider>)
}
beforeEach(() => { request.mockReset() })

describe('Mentor Desk controls', () => {
  it('requires an explicit preview before committing assignments', async () => {
    request.mockResolvedValue({ assignments: [{ team_id: 21, mentor_assignment_id: 81 }], unsatisfied_team_ids: [] })
    const view = wrapper(<MentorAssignmentsPanel scope={scope} eventVersion={4} teams={[{ id: 21, label: 'Bench A' }]} mentors={[{ id: 81, label: 'Mentor A' }]} />)
    expect(screen.queryByRole('button', { name: 'Assign mentors' })).not.toBeInTheDocument()
    fireEvent.click(screen.getByLabelText('Bench A'))
    fireEvent.click(screen.getByRole('button', { name: 'Preview assignments' }))
    expect(await screen.findByText('Bench A → Mentor A')).toBeVisible()
    expect(request.mock.calls[0][0]).toBe('/admin/events/42/mentor-assignments/preview/')
    expect(JSON.parse(request.mock.calls[0][1].body).team_ids).toEqual([21])
    fireEvent.change(screen.getByLabelText('Assignment mode'), { target: { value: 'skill_match' } })
    expect(screen.queryByRole('button', { name: 'Assign mentors' })).not.toBeInTheDocument()
    await expectNoA11yViolations(view.container)
  })

  it('defaults imports to practice and uploads a bounded mapping file', async () => {
    request.mockResolvedValue({ id: 1, event_id: 42, version: 1, state: 'preview', allowed_actions: [],
      preview_token: '11111111-1111-4111-8111-111111111111', mapping_sha256: 'a'.repeat(64),
      expires_at: '2027-01-01T00:00:00Z', practice_run_id: 'practice', mapping_count: 1 })
    wrapper(<TeamImportPanel scope={scope} />)
    expect(screen.getByLabelText('Practice session')).toBeChecked()
    fireEvent.change(screen.getByLabelText('Team mapping file'), { target: { files: [new File(['team_id,member_ids,alias\n21,17,Bench A'], 'teams.csv', { type: 'text/csv' })] } })
    fireEvent.click(screen.getByRole('button', { name: 'Validate and preview' }))
    await waitFor(() => expect(request).toHaveBeenCalledTimes(1))
    const data = request.mock.calls[0][1].body as FormData
    expect(data.get('practice_run_id')).toBeTruthy()
    expect(data.get('expected_version')).toBe('0')
    expect(request.mock.calls[0][0]).toBe('/admin/events/42/teams-import/preview/')
  })

  it('refuses expired and oversized drafts before opening storage or making any request', async () => {
    await expect(saveRoundDraft('session', 21, '2000-01-01T00:00:00Z', {})).rejects.toThrow(/closed/)
    await expect(saveRoundDraft('session', 21, '2099-01-01T00:00:00Z', { note: 'x'.repeat(65_000) })).rejects.toThrow(/64 KB/)
    expect(request).not.toHaveBeenCalled()
  })
})
