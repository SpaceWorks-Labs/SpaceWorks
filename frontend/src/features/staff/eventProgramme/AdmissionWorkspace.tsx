import { useState } from 'react'
import { ErrorBlock, Pagination } from '../../../components/ui'
import { AdmissionPanel } from '../hackathonAdmission/AdmissionPanel'
import { ReviewWorkbench } from '../hackathonAdmission/ReviewWorkbench'
import { RsvpOverridePanel } from '../hackathonAdmission/RsvpOverridePanel'
import { useHackathonConfig } from '../hackathonAdmission/useAdmissionAdmin'
import { useEventStaffGrants } from '../eventStaffGrantsApi'
import type { StaffEvent } from '../eventsApi'
import { useSearchParams } from 'react-router-dom'

export function AdmissionWorkspace({ event, canManage }: { event: StaffEvent; canManage: boolean }) {
  const [page, setPage] = useState(1), [params, setParams] = useSearchParams()
  const config = useHackathonConfig(event.id, canManage)
  const grants = useEventStaffGrants({ kind: 'event', id: event.id }, page, canManage)
  const [subject, setSubject] = useState<{ id: number; version: number } | null>(null)
  const review = Number(params.get('applicationReview'))
  const openReview = (id: number | null) => setParams(previous => { const next = new URLSearchParams(previous); if (id) next.set('applicationReview', String(id)); else next.delete('applicationReview'); return next })
  if (review > 0) return <div className="grid gap-4"><button className="desk-button" onClick={() => openReview(null)}>Back to applications</button><ReviewWorkbench eventId={event.id} reviewId={review} /></div>
  if (canManage && config.error) return <ErrorBlock error={config.error} onRetry={() => void config.refetch()} />
  if (canManage && !config.data) return <p role="status">Loading admission settings…</p>
  return <div className="grid gap-5">
    <AdmissionPanel eventId={event.id} configVersion={config.data?.version ?? 0} canManage={canManage} reviewers={(grants.data?.results ?? [])
      .filter(row => row.permissions.includes('review_applications')).map(row => ({ id: row.user, label: `Reviewer ${row.user}` }))} onReview={openReview}
      onSelectApplication={canManage ? setSubject : undefined} />
    {grants.error ? <ErrorBlock error={grants.error} onRetry={() => void grants.refetch()} /> : null}
    <Pagination page={page} count={grants.data?.count ?? 0} pageSize={24} totalPages={Math.ceil((grants.data?.count ?? 0) / 24)} onChange={setPage} />
    {subject ? <RsvpOverridePanel eventId={event.id} applicationId={subject.id} version={subject.version} /> : null}
  </div>
}
