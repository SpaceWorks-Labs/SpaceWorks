import { useState } from 'react'
import { ActionControl, Card, Pagination, StatusPill } from '../../../components/ui'
import { errorText, useProgrammeCommand, useProgrammeList } from '../../events/contributions/api'
import type { Aggregate, EventScope } from '../../events/contributions/types'

interface Mapping extends Aggregate { mentor_assignment_id: number; team_id: number }
/** G mounts with assignment-management authority after C2 route registration. */
export function MentorAssignmentLifecycle({ scope }: { scope: EventScope }) {
  const [page, setPage] = useState(1)
  const query = useProgrammeList<Mapping>(scope, 'admin', '/mentor-assignments/', page)
  const command = useProgrammeCommand(scope, 'admin')
  return <section aria-label="Assignment lifecycle" className="grid gap-3"><h2 className="title-section">Current team assignments</h2>
    {query.isPending ? <p role="status">Loading assignments…</p> : null}
    {query.error || command.error ? <p role="alert" className="text-danger">{errorText(query.error ?? command.error)}</p> : null}
    {query.data?.results.map(row => <Card key={row.id}><div className="flex flex-wrap items-center justify-between gap-3"><div><h3 className="font-semibold">Team {row.team_id} · Mentor {row.mentor_assignment_id}</h3><StatusPill label={row.state} tone="neutral" /></div>
      <div className="flex gap-2">{(row.state === 'proposed' ? ['activate', 'end'] : row.state === 'active' ? ['end'] : []).map(action => <ActionControl key={action} action={{ label: action === 'activate' ? 'Activate assignment' : 'End assignment', pending: command.isPending,
        onClick: () => command.mutate({ path: `/mentor-assignments/${row.id}/${action}/`, version: row.version }) }} />)}</div>
    </div></Card>)}
    <Pagination page={page} totalPages={Math.ceil((query.data?.count ?? 0) / 24)} onChange={setPage} />
  </section>
}
