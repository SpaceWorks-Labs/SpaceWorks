import { t } from "@lingui/core/macro";
import { useState } from 'react'
import { mentorLifecycleLabel } from '../lifecycleLabels'
import { ActionControl, Card, Pagination, StatusPill } from '../../../components/ui'
import { errorText, useProgrammeCommand, useProgrammeList } from '../../events/contributions/api'
import type { Aggregate, EventScope } from '../../events/contributions/types'
import { LogoLoader } from '../../../components/LogoLoader'

interface Mapping extends Aggregate { mentor_assignment_id: number; team_id: number }
/** G mounts with assignment-management authority after C2 route registration. */
export function MentorAssignmentLifecycle({ scope }: { scope: EventScope }) {
  const [page, setPage] = useState(1)
  const query = useProgrammeList<Mapping>(scope, 'admin', '/mentor-assignments/', page)
  const command = useProgrammeCommand(scope, 'admin')
  return <section aria-label={t`Assignment lifecycle`} className="grid gap-3"><h2 className="title-section">{t`Current team assignments`}</h2>
    {query.isPending ? <LogoLoader label={t`Loading assignments…`} size={48} className="min-h-16 py-3" /> : null}
    {query.error || command.error ? <p role="alert" className="text-danger">{errorText(query.error ?? command.error)}</p> : null}
    {query.data?.results.map(row => <Card key={row.id}><div className="flex flex-wrap items-center justify-between gap-3"><div><h3 className="font-semibold">{t`Team ${row.team_id} · Mentor ${row.mentor_assignment_id}`}</h3><StatusPill label={mentorLifecycleLabel(row.state)} tone="neutral" /></div>
      <div className="flex gap-2">{(row.state === 'proposed' ? ['activate', 'end'] : row.state === 'active' ? ['end'] : []).map(action => <ActionControl key={action} action={{ label: action === 'activate' ? t`Activate assignment` : t`End assignment`, pending: command.isPending,
        onClick: () => command.mutate({ path: `/mentor-assignments/${row.id}/${action}/`, version: row.version }) }} />)}</div>
    </div></Card>)}
    <Pagination page={page} totalPages={Math.ceil((query.data?.count ?? 0) / 24)} onChange={setPage} />
  </section>
}
