import { useState } from 'react'
import { ListLayout } from '../../../components/layouts'
import { Card, ErrorText, StatusBadge } from '../../../components/ui'
import { AdmissionArtwork } from '../../events/hackathonAdmission/AdmissionArtwork'
import { DecisionBatchPanel } from './DecisionBatchPanel'
import { useAdmissionAdmin } from './useAdmissionAdmin'
import type { DecisionSelection, ReviewApplication } from './types'

export function AdmissionPanel({ eventId, configVersion, reviewers, onReview, onSelectApplication, canManage = false }: {
  eventId: number; configVersion: number; reviewers: Array<{ id: number; label: string }>
  onReview: (reviewId: number) => void
  onSelectApplication?: (subject: { id: number; version: number }) => void
  canManage?: boolean
}) {
  const [page, setPage] = useState(1), [selected, setSelected] = useState<Record<string, DecisionSelection>>({})
  const [resumeBatchId, setResumeBatchId] = useState<number | null>(null)
  const [outcome, setOutcome] = useState<DecisionSelection['outcome']>('offer')
  const [reviewerIds, setReviewerIds] = useState<number[]>([])
  const { applications, action } = useAdmissionAdmin(eventId, page)
  const key = (app: ReviewApplication) => app.cohort_id ? 'cohort:' + app.cohort_id : 'application:' + app.id
  const choose = (app: ReviewApplication, checked: boolean) => {
    const next = { ...selected }
    if (checked) next[key(app)] = { ...(app.cohort_id ? { cohort_id: app.cohort_id } : { application_id: app.id }),
      expected_version: app.cohort_id ? app.cohort_version! : app.version, outcome, reason_code: 'review_complete' }
    else delete next[key(app)]
    setSelected(next)
  }
  return <ListLayout header={{ title: 'Hackathon applications' }} state={applications.isLoading ? { status: 'loading' } : applications.error
    ? { status: 'error', error: applications.error.message, onRetry: () => { void applications.refetch() } } : { status: 'ready' }}
    empty={{ message: 'No applications yet.' }} pagination={{ page, pageSize: 24, count: applications.data?.count ?? 0, onChange: setPage }}
    body={{ kind: 'rows', rows: <>
      {action.error ? <ErrorText message={action.error.message} /> : null}
      {canManage ? <Card><div className="grid gap-3"><label className="grid gap-1 text-sm text-ink">Decision for newly selected subjects
        <select className="desk-input" value={outcome} onChange={e => setOutcome(e.target.value as DecisionSelection['outcome'])}>
          <option value="offer">Offer</option><option value="waitlist">Waitlist</option><option value="reject">Reject</option></select></label>
        <fieldset className="grid gap-1"><legend className="text-sm font-semibold text-ink">Eligible reviewers</legend>{reviewers.map(reviewer => <label key={reviewer.id} className="flex min-h-11 items-center gap-3 text-sm text-ink">
          <input type="checkbox" checked={reviewerIds.includes(reviewer.id)} onChange={e => setReviewerIds(e.target.checked ? [...reviewerIds, reviewer.id] : reviewerIds.filter(id => id !== reviewer.id))} />{reviewer.label}</label>)}</fieldset>
        <button className="desk-button justify-self-start" type="button" disabled={action.isPending || !reviewerIds.length || !Object.keys(selected).length}
          onClick={() => action.mutate({ suffix: '/application-review/assign/', body: { expected_version: configVersion,
            reviewer_ids: reviewerIds, subjects: Object.values(selected).map(s => s.cohort_id ? { cohort_id: s.cohort_id } : { application_id: s.application_id }) } })}>Assign reviewers</button>
      </div></Card> : null}
      {applications.data?.count === 0 ? <><AdmissionArtwork kind="applications" /><p className="text-sm text-muted">Applications will appear here after participants submit.</p></> : null}
      {applications.data?.results.map(application => <Card key={application.id}><div className="flex flex-wrap items-center justify-between gap-3">
        <label className="flex min-h-11 items-center gap-3 text-sm text-ink">{canManage ? <input type="checkbox" checked={Boolean(selected[key(application)])}
          disabled={!['submitted', 'waitlisted', 'rejected'].includes(application.state)} onChange={e => choose(application, e.target.checked)} /> : null}
          <span>{application.alias}{application.cohort_id ? ' · Team application' : ''}</span></label>
        <StatusBadge status={application.state} label={application.state} />
        {onSelectApplication ? <button className="desk-button" onClick={() => onSelectApplication({ id: application.id, version: application.version })}>RSVP tools</button> : null}
        {canManage && application.draft_batch_id ? <button type="button" className="desk-button" onClick={() => setResumeBatchId(application.draft_batch_id!)}>Resume private batch #{application.draft_batch_id}</button> : null}
        {application.review_id ? <button type="button" className="desk-button" onClick={() => onReview(application.review_id!)}>Open my review</button> : null}
      </div></Card>)}
      {canManage ? <DecisionBatchPanel resumeBatchId={resumeBatchId} eventId={eventId} selections={Object.values(selected)} onReleased={() => setSelected({})} /> : null}
    </> }} />
}
