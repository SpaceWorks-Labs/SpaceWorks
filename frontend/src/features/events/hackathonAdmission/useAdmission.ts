import { t } from "@lingui/core/macro";
import { sessionScope } from '../../staff/eventProgramme/sessionScope'
import { useRef } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { parseProgrammeContext } from '../contracts/parsers'
import { StructuredApiError } from '../../../lib/api'
import { CommandSession, readMember } from './transport'
import type { Application, Prefill, ProgrammeContext } from './types'

export function useAdmission(publicToken: string, accountId: number) {
  const queryClient = useQueryClient()
  const commands = useRef(new CommandSession())
  const key = ['event-admission', accountId, publicToken, ...sessionScope()] as const
  const context = useQuery({ queryKey: [...key, 'context'], queryFn: async () => parseProgrammeContext(
    await readMember<unknown>('/api/v1/public/event-programmes/' + publicToken + '/context/')),
    enabled: accountId > 0, staleTime: 0, gcTime: 0, retry: false })
  const applicationRoute = context.data?.routes.application?.url
  const application = useQuery({ queryKey: [...key, 'application'], queryFn: () => readMember<Application>(applicationRoute!),
    enabled: Boolean(applicationRoute), staleTime: 0, gcTime: 0, retry: false,
    refetchInterval: query => ['submitted', 'offered', 'waitlisted'].includes(query.state.data?.state ?? '') ? 30000 : false })
  const form = context.data?.application_form
  const prefill = useQuery({ queryKey: [...key, 'prefill', form && !Array.isArray(form) ? form.revision : 1,
      context.data?.event.event_date_revision], queryFn: async () => {
    const current = context.data!, descriptor = current.application_form
    if (!descriptor || Array.isArray(descriptor)) return undefined
    const { memberRequest } = await import('../../../lib/api')
    return memberRequest<Prefill>(current.routes.prefill!.url.slice('/api/v1'.length), { method: 'POST', body: JSON.stringify({
      context: { event_id: current.event.id, makerspace_id: current.makerspace.id, subject_kind: 'application' },
      form_id: descriptor.form_id, form_revision: descriptor.revision, event_date_revision: current.event.event_date_revision }) })
  }, enabled: Boolean(context.data?.routes.prefill && form && !Array.isArray(form) && context.data?.saved_details.readiness === 'ready'),
    staleTime: 0, gcTime: 0, retry: false })
  const mutation = useMutation({ mutationFn: ({ route, method = 'POST', body }: {
    route: keyof ProgrammeContext['routes']; method?: 'POST' | 'PATCH'; body: Record<string, unknown>
  }) => {
    const target = context.data?.routes[route]
    if (!target || typeof target === 'string') throw new Error(t`This event action is unavailable.`)
    return commands.current.send<Application>(target.url, method, body)
  }, onSuccess: async () => {
    await Promise.all([queryClient.invalidateQueries({ queryKey: key }),
      queryClient.invalidateQueries({ queryKey: ["event-teams", accountId] }),
      queryClient.invalidateQueries({ queryKey: ["team-finder", accountId] })])
  }, onError: error => {
    if (error instanceof StructuredApiError && ['host_waiver_required', 'coc_revision_changed',
      'form_revision_changed', 'event_date_revision_changed', 'event_date_changed', 'stale_version'].includes(error.code ?? '')) {
      void queryClient.invalidateQueries({ queryKey: key })
    }
  } })
  return { context, application, prefill, mutation }
}
