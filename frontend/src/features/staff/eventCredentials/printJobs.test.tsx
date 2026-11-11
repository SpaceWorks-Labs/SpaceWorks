import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderHook, act } from '@testing-library/react'
import { expect, it, vi } from 'vitest'
import type { ReactNode } from 'react'
import { useDeskPrint } from './api'
import { staffRequest, staffRequestBlob } from '../../../lib/api'

vi.mock('../../../lib/api', async original => ({ ...await original<typeof import('../../../lib/api')>(), staffRequest: vi.fn(), staffRequestBlob: vi.fn() }))
it('follows a queued job to its authenticated download instead of rejecting 202', async () => {
  vi.mocked(staffRequest).mockResolvedValueOnce({ job_id: 9, state: 'queued', status_url: '/api/v1/admin/events/42/badges/print-jobs/9/' })
    .mockResolvedValueOnce({ job_id: 9, state: 'ready', row_failures: [], expires_at: '2026-12-01T12:00:00Z' })
  const pdf = new Blob(['pdf'], { type: 'application/pdf' })
  vi.mocked(staffRequestBlob).mockResolvedValue(pdf)
  const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } })
  const { result, unmount } = renderHook(() => useDeskPrint(42), { wrapper: ({ children }: { children: ReactNode }) => <QueryClientProvider client={client}>{children}</QueryClientProvider> })
  await act(async () => {
    const output = await result.current.mutateAsync({ registration_ids: [17], expected_version: 4, template_revision: 3, stock: 'cr80-landscape', include_photo: false })
    expect(output.blob).toBe(pdf)
  })
  expect(vi.mocked(staffRequest).mock.calls[0][1]?.headers).toHaveProperty('Idempotency-Key')
  expect(staffRequest).toHaveBeenCalledWith('/admin/events/42/badges/print-jobs/9/', expect.objectContaining({ signal: expect.any(AbortSignal) }))
  expect(staffRequestBlob).toHaveBeenCalledWith('/admin/events/42/badges/print-jobs/9/download/', expect.objectContaining({ signal: expect.any(AbortSignal) }))
  unmount(); client.clear()
})
