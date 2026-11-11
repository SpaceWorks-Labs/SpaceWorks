import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import fixtures from '../hackathonGallery/domain-fixtures.test.json'
import { PublicProgrammePage } from './PublicProgrammePage'

const { tenantPublicRequest, tenantPublicRequestBlob } = vi.hoisted(() => ({ tenantPublicRequest: vi.fn(), tenantPublicRequestBlob: vi.fn() }))
vi.mock('../../../lib/api', async () => ({ ...await vi.importActual<typeof import('../../../lib/api')>('../../../lib/api'),
  tenantPublicRequest, tenantPublicRequestBlob,
  bootstrapTenant: async () => ({ makerspace: { id: 1, name: 'Forge Lab' }, branding: {}, theme: {}, modules: ['events'], features: ['events.project_gallery'] }) }))
vi.mock('../../../lib/tenant', () => ({
  useTenant: () => ({ mode: 'central', slug: 'forge' }),
  useTenantPath: (slug: string) => (part = '') => `/m/${slug}${part ? `/${part}` : ''}`,
}))

const entry = fixtures.gallery_entry
function show(path: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[path]}><Routes>
    <Route path="/m/:slug/events/:publicToken/gallery" element={<PublicProgrammePage />} />
    <Route path="/m/:slug/events/:publicToken/gallery/:entryPublicId" element={<PublicProgrammePage />} />
    <Route path="/m/:slug/events/:publicToken/results" element={<PublicProgrammePage results />} />
  </Routes></MemoryRouter></QueryClientProvider>)
}
beforeEach(() => { tenantPublicRequest.mockReset(); tenantPublicRequestBlob.mockReset() })

describe('public project gallery (DY-03)', () => {
  it('renders inside the public layout with the tenant header, not the member shell', async () => {
    tenantPublicRequest.mockResolvedValue({ count: 1, next: null, previous: null, results: [entry] })
    show('/m/forge/events/tok/gallery')
    expect(await screen.findByRole('heading', { level: 1, name: 'Event projects' })).toBeVisible()
    expect(await screen.findByText(entry.title)).toBeVisible()
    // Public chrome: the makerspace's public navigation, a sign-in link and the public footer.
    expect(screen.getByRole('link', { name: 'Sign in' })).toHaveAttribute('href', '/m/forge/member')
    expect(screen.getByRole('navigation', { name: 'Footer' })).toBeInTheDocument()
    const crumbs = screen.getByRole('navigation', { name: 'Breadcrumb' })
    expect(within(crumbs).getByRole('link', { name: 'All events' })).toHaveAttribute('href', '/m/forge/events')
    // No member-shell surfaces leak onto a public page.
    expect(screen.queryByRole('button', { name: /Space Works/ })).toBeNull()
    expect(screen.getAllByRole('main')).toHaveLength(1)
    expect(tenantPublicRequest).toHaveBeenCalledWith('forge', '/public/event-programmes/tok/gallery/?page=1', { cache: 'no-store' })
  })

  it('keeps the privacy gates: downloads recheck consent through the live route, never a cached URL', async () => {
    tenantPublicRequest.mockResolvedValue(entry)
    tenantPublicRequestBlob.mockResolvedValue(new Blob(['x']))
    const created = vi.fn(() => 'blob:x'); const revoked = vi.fn()
    Object.assign(URL, { createObjectURL: created, revokeObjectURL: revoked })
    show(`/m/forge/events/tok/gallery/${entry.public_id}`)
    const download = await screen.findByRole('button', { name: /Download/ })
    fireEvent.click(download)
    await waitFor(() => expect(tenantPublicRequestBlob).toHaveBeenCalledTimes(1))
    const [slug, path] = tenantPublicRequestBlob.mock.calls[0]
    expect(slug).toBe('forge')
    expect(path).toMatch(/^\/public\/event-programmes\/tok\/gallery\/assets\/[^/]+\/$/)
    expect(path).not.toContain('download_url')
    for (const image of document.querySelectorAll('img[src]')) expect(image).toHaveAttribute('referrerpolicy', 'no-referrer')
  })

  it('puts results in the same public layout', async () => {
    tenantPublicRequest.mockResolvedValue({ event_id: 4, version: 1, published_at: '2026-10-01T10:00:00Z', awards: [] })
    show('/m/forge/events/tok/results')
    expect(await screen.findByText('No public awards')).toBeVisible()
    expect(screen.getByRole('link', { name: 'Sign in' })).toBeInTheDocument()
    expect(within(screen.getByRole('navigation', { name: 'Breadcrumb' })).getByText('Results')).toBeInTheDocument()
  })
})
