import { LogoLoader } from "../../../components/LogoLoader";
import { t } from "@lingui/core/macro";
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
  if (!features) return <LogoLoader label={t`Loading event options…`} />
  if (!enabled || (context.data?.programme.kind === 'ordinary' && !versionedForm)) return children
  return <div className="grid gap-3"><p className="text-sm text-muted">{t`Review this event’s application and programme using your member account.`}</p>
    <a className="desk-button-brand" href={programmeHref(publicToken, 'application', slug)}>{t`Open application and programme`}</a>
    {context.isPending ? <LogoLoader label={t`Checking the current programme…`} size={48} className="min-h-16 py-3" /> : null}
  </div>
}
