import { useRef } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { CommandSession, readMember } from './transport'
import type { Page, ProgrammeContext, Team } from './types'

export function useTeams(context: ProgrammeContext, accountId: number) {
  const client = useQueryClient(), commands = useRef(new CommandSession())
  const base = context.routes.member_base
  const key = ['event-teams', accountId, context.makerspace.id, context.event.id] as const
  const teams = useQuery({ queryKey: [...key, 'mine'], queryFn: () => readMember<Page<Team>>(base + '/teams/'),
    staleTime: 0, gcTime: 0, retry: false, enabled: context.eligibility.eligible })
  const action = useMutation({ mutationFn: ({ suffix, body, method = 'POST' }: {
    suffix: string; body: Record<string, unknown>; method?: 'POST' | 'PATCH'
  }) => commands.current.send<Record<string, unknown>>(base + suffix, method, body),
    onSuccess: async () => { await Promise.all([client.invalidateQueries({ queryKey: key }),
      client.invalidateQueries({ queryKey: ["event-admission", accountId] }),
      client.invalidateQueries({ queryKey: ["team-finder", accountId] })]) } })
  return { key, teams, action }
}
