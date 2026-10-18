import { useRef } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { staffRequest } from '../../../lib/api'
import { CommandSession } from '../../events/hackathonAdmission/transport'
import type { Page } from '../../events/hackathonAdmission/types'
import type { Config, ReviewApplication } from './types'

export function useAdmissionAdmin(eventId: number, page = 1) {
  const base = '/api/v1/admin/events/' + eventId
  const key = ['staff-event-admission', eventId] as const
  const client = useQueryClient(), commands = useRef(new CommandSession())
  const applications = useQuery({ queryKey: [...key, 'applications', page], queryFn: () => staffRequest<Page<ReviewApplication>>(
    '/admin/events/' + eventId + '/applications/?page=' + page), staleTime: 0, gcTime: 0, retry: false })
  const action = useMutation({ mutationFn: ({ suffix, body, method = 'POST' }: {
    suffix: string; body: Record<string, unknown>; method?: 'POST' | 'PATCH'
  }) => commands.current.send<Record<string, unknown>>(base + suffix, method, body, true),
    onSuccess: () => client.invalidateQueries({ queryKey: key }) })
  return { applications, action, base, key }
}
export function useHackathonConfig(eventId: number) {
  return useQuery({ queryKey: ['staff-event-admission', eventId, 'config'],
    queryFn: () => staffRequest<Config>('/admin/events/' + eventId + '/hackathon/'), staleTime: 0, gcTime: 0, retry: false })
}
