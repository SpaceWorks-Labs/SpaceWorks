import type { ReactNode } from 'react'
import { useQuery } from '@tanstack/react-query'
import { memberRequest } from '../../../lib/api'
import { parseProgrammeContext } from '../contracts/parsers'
import { programmeHref } from './routeNames'
import { sessionScope } from '../../staff/eventProgramme/sessionScope'

/** A live context prevents the ordinary registration form bypassing hackathon admission. */
export function PublicProgrammeEntry({ publicToken, slug, features, children, versionedForm = false }: {
  publicToken: string; slug: string; features: readonly string[] | undefined; children: ReactNode; versionedForm?: boolean
}) {
  const enabled = (features?.includes('events.hackathons') ?? false) || versionedForm
  const context = useQuery({ queryKey: ['public-programme-entry', slug, publicToken, ...sessionScope()], enabled,
    queryFn: async () => parseProgrammeContext(await memberRequest(`/public/event-programmes/${encodeURIComponent(publicToken)}/context/`)),
    retry: false, staleTime: 0, gcTime: 0 })
  if (!features) return <p role="status">Loading event options…</p>
  if (!enabled || (context.data?.programme.kind === 'ordinary' && !versionedForm)) return children
  return <div className="grid gap-3"><p className="text-sm text-muted">Review this event’s application and programme using your member account.</p>
    <a className="desk-button-brand" href={programmeHref(publicToken, 'application', slug)}>Open application and programme</a>
    {context.isPending ? <p role="status" className="text-sm">Checking the current programme…</p> : null}
  </div>
}
