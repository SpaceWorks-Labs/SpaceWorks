import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { beforeEach, expect, it, vi } from 'vitest'

const { request } = vi.hoisted(() => ({ request: vi.fn() }))
vi.mock('../../../lib/api', () => ({ staffRequest: request, staffRequestBlob: vi.fn() }))
vi.mock('./EventCardApproval', () => ({ EventCardApproval: () => null }))
vi.mock('./EventCardExtras', () => ({ EventCardExtras: () => null }))
vi.mock('../../../components/card-designer/CardDesigner', async () => {
  const { usePublishDesign } = await import('../../../components/card-designer/designerApi')
  return { CardDesigner: ({ designId }: { designId: number }) => {
    const publish = usePublishDesign(designId)
    return <button type="button" onClick={() => publish.mutate({})}>Publish in the designer</button>
  } }
})

import { EventCardsPanel } from './EventCardsPanel'

beforeEach(() => { vi.clearAllMocks() })

it('enables issuance after publishing through the canonical design mutation even when pair data is stale', async () => {
  let published = false
  const draft = { id: 42, published_at: null, can_edit: true }
  request.mockImplementation(async (path: string) => {
    if (path === '/admin/events/7/card-designs') return { event_card: draft }
    if (path === '/admin/card-designs/42/publish') { published = true; return { ...draft, published_at: '2026-11-07T00:00:00Z' } }
    if (path === '/admin/card-designs/42') return { ...draft, published_at: published ? '2026-11-07T00:00:00Z' : null }
    if (path === '/admin/events/7/id-cards' || path === '/admin/events/7/card-jobs') return []
    throw new Error(`Unexpected private card test path: ${path}`)
  })
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(<QueryClientProvider client={client}><EventCardsPanel eventId={7} features={['events.id_cards']} /></QueryClientProvider>)
  const issue = await screen.findByRole('button', { name: 'Issue cards now' })
  expect(issue).toBeDisabled()
  fireEvent.click(screen.getByRole('radio', { name: 'Card design' }))
  fireEvent.click(screen.getByRole('button', { name: 'Publish in the designer' }))
  await waitFor(() => expect(client.getQueryData<{ published_at: string | null }>(['card-design', 42])?.published_at).toBeTruthy())
  expect(client.getQueryData<{ event_card: typeof draft }>(['event-card-designs', 7])?.event_card.published_at).toBeNull()
  fireEvent.click(screen.getByRole('radio', { name: 'ID cards' }))
  await waitFor(() => expect(screen.getByRole('button', { name: 'Issue cards now' })).toBeEnabled())
  expect(screen.queryByText('Publish the card design to start issuing cards.')).toBeNull()
})
