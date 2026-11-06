import { t } from "@lingui/core/macro";
import { useState } from 'react'
import { LifeBuoy } from 'lucide-react'
import { ListLayout } from '../../../components/layouts'
import { ActionControl, Card, StatusPill } from '../../../components/ui'
import type { EventScope, HelpRequest } from './types'
import { errorText, useProgrammeCommand, useProgrammeList, type Surface } from './api'

export function HelpQueue({ scope, surface = 'member', onOpen }: {
  scope: EventScope; surface?: Surface; onOpen: (request: HelpRequest) => void
}) {
  const [page, setPage] = useState(1)
  const query = useProgrammeList<HelpRequest>(scope, surface, '/help/', page, true)
  const command = useProgrammeCommand(scope, surface)
  return <ListLayout header={{ title: surface === 'member' ? t`Your team’s help` : t`Mentor Desk`,
    subtitle: surface === 'member' ? t`Track your requests, add a comment, or cancel when you have solved it.` : t`Pick up a request when you are ready. Release it if another mentor should take over.` }}
    state={query.isPending ? { status: 'loading' } : query.isError ? { status: 'error', error: errorText(query.error), onRetry: () => { void query.refetch() } } : { status: 'ready' }}
    isEmpty={!query.data?.results.length} empty={{ message: surface === 'member' ? t`No help requests yet.` : t`No requests need your attention right now.` }}
    pagination={{ page, pageSize: 24, count: query.data?.count ?? 0, onChange: setPage }}
    body={{ kind: 'rows', rows: <>
      <p role="status" aria-live="polite" className="text-sm text-muted">{t`${query.data?.count ?? 0} requests · Updates every 15 seconds while this page is visible`}</p>
      {command.error ? <p role="alert" className="text-danger">{errorText(command.error)}</p> : null}
      {query.data?.results.map(row => <Card key={row.id}><div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex min-w-0 gap-3"><LifeBuoy aria-hidden="true" className="size-5 shrink-0 text-muted" />
          <div><h2 className="title-section">{row.category ?? t`Help request`}{row.team_alias ? ` · ${row.team_alias}` : ''}</h2>
            <p className="text-sm text-muted">{row.zone?.table ? t`Table ${row.zone.table}` : row.zone?.zone ?? ''}</p>
            {row.position != null ? <p className="text-sm text-muted">{t`Queue position: ${row.position}`}</p> : null}
            {row.wait_estimate ? <p className="text-sm text-muted">{row.wait_estimate}</p> : null}</div></div>
        <div className="flex flex-wrap items-center gap-2"><StatusPill label={row.state} tone={row.state === 'claimed' ? 'info' : 'neutral'} />
          {row.allowed_actions.includes('claim') ? <ActionControl primary action={{ label: t`Claim request`, pending: command.isPending,
            onClick: () => command.mutate({ path: `/help/${row.id}/claim/`, version: row.version }) }} /> : null}
          {surface === 'member' || row.allowed_actions.some(x => ['comment', 'resolve', 'release', 'assign'].includes(x))
            ? <ActionControl action={{ label: t`Open request`, onClick: () => onOpen(row) }} /> : null}
        </div></div></Card>)}
    </> }} />
}
