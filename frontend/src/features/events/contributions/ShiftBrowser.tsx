import { useState } from 'react'
import { ListLayout } from '../../../components/layouts'
import { ActionControl, Card } from '../../../components/ui'
import { errorText, useProgrammeCommand, useProgrammeList } from './api'
import type { EventScope, RoleApplication, Shift } from './types'

export function ShiftBrowser({ scope, assignments }: { scope: EventScope; assignments: RoleApplication[] }) {
  const [page, setPage] = useState(1)
  const query = useProgrammeList<Shift>(scope, 'member', '/shifts/', page)
  const command = useProgrammeCommand(scope, 'member')
  return <ListLayout header={{ title: 'Volunteer shifts', subtitle: 'Choose a duty that fits your availability. Overlapping approved duties cannot be booked.' }}
    state={query.isPending ? { status: 'loading' } : query.isError ? { status: 'error', error: errorText(query.error), onRetry: () => { void query.refetch() } } : { status: 'ready' }}
    isEmpty={!query.data?.results.length} empty={{ message: 'No shifts are open yet.' }}
    pagination={{ page, pageSize: 24, count: query.data?.count ?? 0, onChange: setPage }}
    body={{ kind: 'rows', rows: <>{command.error ? <p role="alert" className="text-danger">{errorText(command.error)}</p> : null}
      {query.data?.results.map(row => {
        const assignment = assignments.find(x => x.posting_id === row.posting_id && ['approved', 'applied'].includes(x.state))
        return <Card key={row.id}><div className="flex flex-wrap items-center justify-between gap-4"><div>
          <h2 className="title-section">{row.task}</h2><p className="text-sm text-muted">{new Date(row.starts_at).toLocaleString()} – {new Date(row.ends_at).toLocaleString()}</p>
          <p className="text-sm text-muted">{row.zone}{row.available === null ? ' · Places available' : ` · ${row.available} places available`}</p>
          {row.signup ? <p className="mt-2 text-sm">Your signup: {row.signup.state}</p> : null}</div>
          {!row.signup ? <ActionControl action={{ label: 'Apply to shift', pending: command.isPending,
            disabled: !assignment, disabledReason: !assignment ? 'Apply to this volunteer role first.' : undefined,
            onClick: () => { if (assignment) command.mutate({ path: `/shifts/${row.id}/apply/`, version: row.version, fields: { role_assignment_id: assignment.id } }) } }} /> : null}
        </div></Card>
      })}</> }} />
}
