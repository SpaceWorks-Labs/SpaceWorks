import { useEffect, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { memberRequest, staffRequest, StructuredApiError } from '../../../lib/api'
import type { Aggregate, EventScope, Page } from './types'
import { parseAggregate, parsePage } from './types'

export type Surface = 'member' | 'admin'
export function programmeKey(scope: EventScope, surface: Surface) {
  return ['events-programme-c', scope.accountId, scope.makerspaceId, scope.eventId, surface] as const
}
export function basePath(scope: EventScope, surface: Surface) {
  return surface === 'member' ? `/member/makerspaces/${scope.makerspaceId}/events/${scope.eventId}` : `/admin/events/${scope.eventId}`
}
export function requestFor(surface: Surface) { return surface === 'member' ? memberRequest : staffRequest }
export function errorText(error: unknown) {
  if (error instanceof StructuredApiError && ['stale_version', 'lease_lost'].includes(error.code ?? '')) {
    return 'This changed in another session. Refresh, review the current state, and try again. Your text is still here.'
  }
  return error instanceof Error ? error.message : 'Could not complete this action. Try again.'
}

function useVisible() {
  const [visible, setVisible] = useState(document.visibilityState !== 'hidden')
  useEffect(() => {
    const update = () => setVisible(document.visibilityState !== 'hidden')
    document.addEventListener('visibilitychange', update)
    return () => document.removeEventListener('visibilitychange', update)
  }, [])
  return visible
}

export function useProgrammeList<T extends Aggregate>(scope: EventScope, surface: Surface, path: string, page = 1, live = false, enabled = true) {
  const visible = useVisible()
  return useQuery({
    queryKey: [...programmeKey(scope, surface), path, page], enabled, gcTime: 0,
    queryFn: async () => parsePage(await requestFor(surface)<Page<T>>(`${basePath(scope, surface)}${path}?page=${page}`)),
    refetchInterval: query => live && visible ? Math.min(120_000, 15_000 * 2 ** query.state.fetchFailureCount) : false,
    refetchIntervalInBackground: false, retry: false,
  })
}

export function useProgrammeDetail<T extends Aggregate>(scope: EventScope, surface: Surface, path: string, enabled = true, live = false) {
  const visible = useVisible()
  return useQuery({ queryKey: [...programmeKey(scope, surface), path], enabled, retry: false, gcTime: 0,
    refetchInterval: query => live && visible ? Math.min(120_000, 15_000 * 2 ** query.state.fetchFailureCount) : false,
    refetchIntervalInBackground: false,
    queryFn: async () => parseAggregate(await requestFor(surface)<T>(`${basePath(scope, surface)}${path}`)) })
}

export interface CommandInput { path: string; version: number; fields?: Record<string, unknown>; method?: 'POST' | 'PATCH' }
export function useProgrammeCommand(scope: EventScope, surface: Surface) {
  const cache = useQueryClient()
  const last = useRef<{ identity: string; operation: string } | null>(null)
  return useMutation({ retry: false,
    mutationFn: async ({ path, version, fields = {}, method = 'POST' }: CommandInput) => {
      const identity = JSON.stringify([programmeKey(scope, surface), path, version, fields, method])
      if (last.current?.identity !== identity) last.current = { identity, operation: crypto.randomUUID() }
      const operation = last.current.operation
      return requestFor(surface)<Aggregate>(`${basePath(scope, surface)}${path}`, {
        method, headers: { 'Idempotency-Key': operation },
        body: JSON.stringify({ ...fields, operation_id: operation, expected_version: version }),
      })
    },
    onSuccess: async () => {
      last.current = null
      await cache.invalidateQueries({ queryKey: programmeKey(scope, surface) })
    },
    onError: async error => {
      if (error instanceof StructuredApiError && error.status === 409) {
        await cache.invalidateQueries({ queryKey: programmeKey(scope, surface) })
      }
    },
  })
}
