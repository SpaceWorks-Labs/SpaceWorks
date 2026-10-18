import { useState } from 'react'
import { HandHeart, Clock3, GraduationCap } from 'lucide-react'
import { ListLayout } from '../../../components/layouts'
import { ActionControl, Card, StatusPill } from '../../../components/ui'
import { errorText, useProgrammeCommand, useProgrammeList } from './api'
import type { EventScope, Posting, RoleApplication, Signup } from './types'

export function ContributionsPage({ scope, onApply, onOpenApplication }: {
  scope: EventScope; onApply: (posting: Posting) => void; onOpenApplication: (application: RoleApplication) => void
}) {
  const [tab, setTab] = useState('opportunities')
  const [page, setPage] = useState(1)
  const postings = useProgrammeList<Posting>(scope, 'member', '/role-postings/', page, false, tab === 'opportunities')
  const applications = useProgrammeList<RoleApplication>(scope, 'member', '/role-applications/', page, false, tab === 'applications')
  const shifts = useProgrammeList<Signup>(scope, 'member', '/shift-signups/', page, false, tab === 'shifts')
  const command = useProgrammeCommand(scope, 'member')
  const query = tab === 'opportunities' ? postings : tab === 'applications' ? applications : shifts
  const rows = query.data?.results ?? []
  return <ListLayout header={{ eyebrow: 'Make it happen', title: 'Contribute',
    subtitle: 'Share your time or experience. Find a role and follow your application here.' }}
    state={query.isPending ? { status: 'loading' } : query.isError ? { status: 'error', error: errorText(query.error), onRetry: () => { void query.refetch() } } : { status: 'ready' }}
    tabs={[{ key: 'opportunities', label: 'Roles needed' }, { key: 'applications', label: 'My applications' }, { key: 'shifts', label: 'My shifts' }]}
    activeTab={tab} onTabChange={key => { setTab(key); setPage(1) }} isEmpty={!rows.length}
    empty={{ message: tab === 'opportunities' ? 'No open roles right now. Check back closer to the event.' : 'Your applications and shifts will appear here.' }}
    pagination={{ page, pageSize: 24, count: query.data?.count ?? 0, onChange: setPage }}
    body={{ kind: 'rows', rows: <>
      {command.error ? <p role="alert" className="text-danger">{errorText(command.error)}</p> : null}
      {tab === 'opportunities' ? postings.data?.results.map(row => <Card key={row.id}>
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex min-w-0 gap-3">{row.role === 'mentor' ? <GraduationCap aria-hidden="true" className="size-5 shrink-0 text-muted" /> : <HandHeart aria-hidden="true" className="size-5 shrink-0 text-muted" />}
            <div><h2 className="title-section">{row.title}</h2><p className="mt-1 text-sm text-muted">{row.description}</p></div></div>
          <ActionControl action={{ label: 'View role and apply', onClick: () => onApply(row) }} />
        </div></Card>) : null}
      {tab === 'applications' ? applications.data?.results.map(row => <Card key={row.id}>
        <div className="flex flex-wrap items-center justify-between gap-4"><div><h2 className="title-section capitalize">{row.role.replace(/_/g, ' ')}</h2>
          <StatusPill label={row.state} tone={row.state === 'approved' ? 'success' : 'neutral'} /></div>
          <ActionControl action={{ label: 'View application', onClick: () => onOpenApplication(row) }} /></div></Card>) : null}
      {tab === 'shifts' ? shifts.data?.results.map(row => <Card key={row.id}>
        <div className="flex flex-wrap items-center justify-between gap-4"><div><h2 className="title-section flex items-center gap-2"><Clock3 aria-hidden="true" className="size-5" />Shift {row.shift_id}</h2>
          <p className="text-sm text-muted">{row.attendance?.replace(/_/g, ' ') ?? row.state}{row.verified_minutes !== null ? ` · ${row.verified_minutes} verified minutes` : ''}</p></div>
          <div className="flex flex-wrap gap-2">{row.allowed_actions.map(action => <ActionControl key={action} action={{
            label: action.replace(/-/g, ' '), pending: command.isPending,
            confirm: action === 'withdraw' ? { title: 'Withdraw from shift?', message: 'Your place can be offered to another volunteer.' } : undefined,
            onClick: () => command.mutate({ path: `/shift-signups/${row.id}/${action}/`, version: row.version }),
          }} />)}</div></div></Card>) : null}
    </> }} />
}
