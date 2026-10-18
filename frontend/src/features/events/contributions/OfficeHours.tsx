import { useState } from 'react'
import { ListLayout } from '../../../components/layouts'
import { ActionControl, Card } from '../../../components/ui'
import type { Booking, EventScope, Shift } from './types'
import { errorText, useProgrammeCommand, useProgrammeList } from './api'

export function OfficeHours({ scope, teamId }: { scope: EventScope; teamId: number }) {
  const [tab, setTab] = useState('slots')
  const [page, setPage] = useState(1)
  const slots = useProgrammeList<Shift>(scope, 'member', '/office-hours/', page, false, tab === 'slots')
  const bookings = useProgrammeList<Booking>(scope, 'member', '/office-hours/bookings/', page, false, tab === 'bookings')
  const query = tab === 'slots' ? slots : bookings
  const command = useProgrammeCommand(scope, 'member')
  return <ListLayout header={{ title: 'Mentor office hours', subtitle: 'Book one place for your whole team. Any current team member can cancel it before the slot starts.' }}
    tabs={[{ key: 'slots', label: 'Available slots' }, { key: 'bookings', label: 'Team bookings' }]} activeTab={tab}
    onTabChange={key => { setTab(key); setPage(1) }}
    state={query.isPending ? { status: 'loading' } : query.isError ? { status: 'error', error: errorText(query.error), onRetry: () => { void query.refetch() } } : { status: 'ready' }}
    isEmpty={!query.data?.results.length} empty={{ message: tab === 'slots' ? 'No office hours are open yet.' : 'Your team has no bookings.' }}
    pagination={{ page, pageSize: 24, count: query.data?.count ?? 0, onChange: setPage }}
    body={{ kind: 'rows', rows: <>{command.error ? <p role="alert" className="text-danger">{errorText(command.error)}</p> : null}
      {tab === 'slots' ? slots.data?.results.map(row => <Card key={row.id}><div className="flex flex-wrap justify-between gap-4"><div>
        <h2 className="title-section">{row.task}</h2><p className="text-sm text-muted">{new Date(row.starts_at).toLocaleString()} – {new Date(row.ends_at).toLocaleTimeString()}</p>
        <p className="text-sm text-muted">{row.available === null ? 'Team places available' : `${row.available} team places available`}</p></div>
        <ActionControl action={{ label: 'Book for our team', pending: command.isPending, disabled: row.available === 0,
          disabledReason: row.available === 0 ? 'This slot is full.' : undefined,
          onClick: () => command.mutate({ path: `/office-hours/${row.id}/bookings/`, version: row.version, fields: { team_id: teamId } }) }} />
      </div></Card>) : bookings.data?.results.map(row => <Card key={row.id}><div className="flex flex-wrap justify-between gap-4"><div>
        <h2 className="title-section">Office hours · Slot {row.slot_id}</h2><p className="text-sm text-muted">{row.state}</p></div>
        {row.allowed_actions.includes('cancel') ? <ActionControl action={{ label: 'Cancel team booking', pending: command.isPending,
          confirm: { title: 'Cancel your team’s booking?', message: 'The place will be available to other teams.' },
          onClick: () => command.mutate({ path: `/office-hours/bookings/${row.id}/cancel/`, version: row.version }) }} /> : null}
      </div></Card>)}
    </> }} />
}
