import { t } from "@lingui/core/macro";
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { memberRequest } from '../../../lib/api'
import { ErrorBlock } from '../../../components/ui'
import type { EventScope } from '../contributions/types'
import { HelpComposer } from '../contributions/HelpComposer'
import { HelpDetail } from '../contributions/HelpDetail'
import { HelpQueue } from '../contributions/HelpQueue'
import { OfficeHours } from '../contributions/OfficeHours'
import { LogoLoader } from '../../../components/LogoLoader'

/** Mentor Desk on an event without hackathon teams (#128 C-36, E2-f): a confirmed attendee asks on their own. */
export function DropInJourney({ scope, section }: { scope: EventScope; section: string }) {
  const [helpId, setHelpId] = useState<number | null>(null)
  const categories = useQuery({ queryKey: ['member', scope.accountId, 'help-topics', scope.makerspaceId, scope.eventId], gcTime: 0,
    queryFn: () => memberRequest<{ results: { key: string; label: string }[] }>(`/member/makerspaces/${scope.makerspaceId}/events/${scope.eventId}/help-topics/`),
    enabled: section === 'help', retry: false })
  if (section === 'office-hours') return <OfficeHours scope={scope} />
  if (helpId) return <HelpDetail scope={scope} helpId={helpId} onClose={() => setHelpId(null)} />
  return <div className="grid gap-6">
    <HelpQueue scope={scope} surface="member" onOpen={row => setHelpId(row.id)} />
    {categories.error ? <ErrorBlock error={categories.error} onRetry={() => void categories.refetch()} />
      : categories.data?.results.length ? <HelpComposer scope={scope} surface="member" teams={[]} categories={categories.data.results} />
        : categories.isPending ? <LogoLoader label={t`Loading help topics…`} size={48} className="min-h-16 py-3" /> : <p className="text-sm text-muted">{t`No help topics are available for this event.`}</p>}
  </div>
}
