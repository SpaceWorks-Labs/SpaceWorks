import { t } from "@lingui/core/macro";
import { useState } from 'react'
import { ListLayout } from '../../../components/layouts'
import { ActionControl, Card } from '../../../components/ui'
import type { EventScope, Shift } from '../../events/contributions/types'
import { errorText, useProgrammeDetail, useProgrammeList } from '../../events/contributions/api'
import { PostingEditor, type PostingConfig, type RoleFormBuilder } from './PostingEditor'
import { ShiftEditor, type ShiftConfig } from './ShiftEditor'

export function ContributorSetupPanel({ scope, renderFormBuilder }: { scope: EventScope; renderFormBuilder: RoleFormBuilder }) {
  const [tab, setTab] = useState('postings')
  const [page, setPage] = useState(1)
  const [selected, setSelected] = useState<number | 'new' | null>(null)
  const postings = useProgrammeList<PostingConfig>(scope, 'admin', '/volunteer-postings/', page, false, tab === 'postings')
  const shifts = useProgrammeList<Shift>(scope, 'admin', '/shifts/', page, false, tab === 'shifts')
  const shift = useProgrammeDetail<ShiftConfig>(scope, 'admin', `/shifts/${selected}/`, tab === 'shifts' && typeof selected === 'number')
  const query = tab === 'postings' ? postings : shifts
  const posting = postings.data?.results.find(row => row.id === selected)
  return <ListLayout header={{ title: t`Contributor setup`, subtitle: t`Configure applications, requirements and duty capacity.`,
    primary: { label: tab === 'postings' ? t`New posting` : t`New shift`, onClick: () => setSelected('new') } }}
    tabs={[{ key: 'postings', label: t`Postings` }, { key: 'shifts', label: t`Shifts and office hours` }]} activeTab={tab}
    onTabChange={key => { setTab(key); setSelected(null); setPage(1) }}
    state={query.isPending ? { status: 'loading' } : query.isError ? { status: 'error', error: errorText(query.error), onRetry: () => { void query.refetch() } } : { status: 'ready' }}
    empty={{ message: t`Create a posting, then add its shifts.` }} isEmpty={selected === null && !query.data?.results.length}
    pagination={{ page, pageSize: 24, count: query.data?.count ?? 0, onChange: value => { setPage(value); setSelected(null) } }}
    body={{ kind: 'rows', rows: <>
      {selected !== null ? <div className="mb-4"><ActionControl action={{ label: t`Close editor`, onClick: () => setSelected(null) }} /></div> : null}
      {tab === 'postings' && selected !== null && (selected === 'new' || posting) ? <PostingEditor key={selected} scope={scope} initial={posting} renderFormBuilder={renderFormBuilder} onSaved={() => setSelected(null)} /> : null}
      {tab === 'shifts' && selected !== null ? selected === 'new' ? <ShiftEditor key="new" scope={scope} onSaved={() => setSelected(null)} />
        : shift.data ? <ShiftEditor key={`${selected}:${shift.data.version}`} scope={scope} initial={shift.data} onSaved={() => setSelected(null)} />
          : <p role={shift.error ? 'alert' : 'status'}>{shift.error ? errorText(shift.error) : t`Loading shift…`}</p> : null}
      {query.data?.results.map(row => <Card key={row.id}><div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="title-section">{'title' in row ? row.title : row.task}</h2>
        <ActionControl action={{ label: t`Edit ${'title' in row ? row.title : row.task}`, onClick: () => setSelected(row.id) }} />
      </div></Card>)}
    </> }} />
}
