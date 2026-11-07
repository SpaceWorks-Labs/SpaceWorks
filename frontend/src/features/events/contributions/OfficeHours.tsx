import { formatLocale } from "../../../lib/format";
import { t } from "@lingui/core/macro";
import { useState } from 'react'
import { ListLayout } from '../../../components/layouts'
import { ActionControl, Card } from '../../../components/ui'
import type { Booking, EventScope, Shift } from './types'
import { errorText, useProgrammeCommand, useProgrammeList } from './api'

/** Team bookings at a hackathon; without `teamId` a drop-in attendee books for themself (#128 C-36, E2-f). */
export function OfficeHours({ scope, teamId }: { scope: EventScope; teamId?: number }) {
  const who = teamId ? 'team' : 'own'
  const [tab, setTab] = useState('slots')
  const [page, setPage] = useState(1)
  const slots = useProgrammeList<Shift>(scope, 'member', '/office-hours/', page, false, tab === 'slots')
  const bookings = useProgrammeList<Booking>(scope, 'member', '/office-hours/bookings/', page, false, tab === 'bookings')
  const query = tab === 'slots' ? slots : bookings
  const command = useProgrammeCommand(scope, 'member')
  return <ListLayout header={{ title: t`Mentor office hours`, subtitle: who === 'team'
      ? t`Book one place for your whole team. Any current team member can cancel it before the slot starts.`
      : t`Book a place with a mentor for yourself. You can cancel it before the slot starts.` }}
    tabs={[{ key: 'slots', label: t`Available slots` }, { key: 'bookings', label: who === 'team' ? t`Team bookings` : t`My bookings` }]} activeTab={tab}
    onTabChange={key => { setTab(key); setPage(1) }}
    state={query.isPending ? { status: 'loading' } : query.isError ? { status: 'error', error: errorText(query.error), onRetry: () => { void query.refetch() } } : { status: 'ready' }}
    isEmpty={!query.data?.results.length} empty={{ message: tab === 'slots' ? t`No office hours are open yet.` : who === 'team' ? t`Your team has no bookings.` : t`You have no bookings.` }}
    pagination={{ page, pageSize: 24, count: query.data?.count ?? 0, onChange: setPage }}
    body={{ kind: 'rows', rows: <>{command.error ? <p role="alert" className="text-danger">{errorText(command.error)}</p> : null}
      {tab === 'slots' ? slots.data?.results.map(row => <Card key={row.id}><div className="flex flex-wrap justify-between gap-4"><div>
        <h2 className="title-section">{row.task}</h2><p className="text-sm text-muted">{new Date(row.starts_at).toLocaleString(formatLocale())} – {new Date(row.ends_at).toLocaleTimeString(formatLocale())}</p>
        <p className="text-sm text-muted">{row.available === null ? t`Places available` : t`${row.available} places available`}</p></div>
        <ActionControl action={{ label: who === 'team' ? t`Book for our team` : t`Book a place`, pending: command.isPending, disabled: row.available === 0,
          disabledReason: row.available === 0 ? 'This slot is full.' : undefined,
          onClick: () => command.mutate({ path: `/office-hours/${row.id}/bookings/`, version: row.version, fields: teamId ? { team_id: teamId } : {} }) }} />
      </div></Card>) : bookings.data?.results.map(row => <Card key={row.id}><div className="flex flex-wrap justify-between gap-4"><div>
        <h2 className="title-section">{t`Office hours · Slot ${row.slot_id}`}</h2><p className="text-sm text-muted">{row.state}</p></div>
        {row.allowed_actions.includes('cancel') ? <ActionControl action={{ label: who === 'team' ? t`Cancel team booking` : t`Cancel booking`, pending: command.isPending,
          confirm: { title: who === 'team' ? t`Cancel your team’s booking?` : t`Cancel your booking?`, message: t`The place will be available to others.` },
          onClick: () => command.mutate({ path: `/office-hours/bookings/${row.id}/cancel/`, version: row.version }) }} /> : null}
      </div></Card>)}
    </> }} />
}
