import { t } from "@lingui/core/macro";
import { useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { DetailLayout } from '../../../components/layouts'
import { Card, ErrorText, StatusBadge } from '../../../components/ui'
import { CommandSession, readStaff } from '../../events/hackathonAdmission/transport'
import type { ReviewAssignment } from './types'

export function ReviewWorkbench({ eventId, reviewId }: { eventId: number; reviewId: number }) {
  const base = '/api/v1/admin/events/' + eventId + '/application-reviews/' + reviewId + '/'
  const client = useQueryClient(), commands = useRef(new CommandSession())
  const [scores, setScores] = useState<Record<string, number>>({}), [notes, setNotes] = useState('')
  const [recusal, setRecusal] = useState('declared'), [recusedReview, setRecusedReview] = useState<number | null>(null)
  const review = useQuery({ queryKey: ['application-review', eventId, reviewId], queryFn: () => readStaff<ReviewAssignment>(base),
    staleTime: 0, gcTime: 0, retry: false, enabled: recusedReview !== reviewId })
  const save = useMutation({ mutationFn: (recuse: boolean) => commands.current.send<ReviewAssignment>(base, 'PATCH', {
    expected_version: review.data!.version, ...(recuse ? { recusal_code: recusal } : { scores, notes }) }, true),
    onSuccess: (result) => {
      client.setQueryData(['application-review', eventId, reviewId], result)
      if (result.state === 'recused') { setRecusedReview(reviewId); setScores({}); setNotes('') }
      return client.invalidateQueries({ queryKey: ['staff-event-admission', eventId] })
    } })
  const current = review.data, editable = current?.allowed_actions.includes('submit')
  return <DetailLayout title={t`Review an application`} state={review.isLoading ? { status: 'loading' } : review.error
    ? { status: 'error', error: review.error.message, onRetry: () => { void review.refetch() } } : { status: 'ready' }}
    status={current ? <StatusBadge status={current.state} label={current.state} /> : undefined}
    main={<div className="grid gap-5">
      {current?.state === 'recused' ? <p role="status" className="text-sm text-ink">{t`Your recusal is recorded. This application has been removed from your review.`}</p> : null}
      {save.error ? <ErrorText message={save.error.message} /> : null}
      {current?.applications.map(application => <Card key={application.id}><h2 className="title-section">{application.alias}</h2>
        {application.blind_notice ? <p className="mt-2 text-sm text-muted">{application.blind_notice}</p> : null}
        <dl className="mt-4 grid gap-3">{application.answers.map(answer => <div key={answer.id}><dt className="text-sm font-semibold text-ink">{answer.label}</dt>
          <dd className="whitespace-pre-wrap break-words text-sm text-ink">{typeof answer.value === 'string' ? answer.value : JSON.stringify(answer.value)}</dd></div>)}</dl>
      </Card>)}
      {editable ? <form className="grid gap-4" onSubmit={event => { event.preventDefault(); save.mutate(false) }}>
        {current?.rubric.criteria.map(criterion => <fieldset disabled={save.isPending} className="grid gap-2 rounded-xl border border-line p-4" key={criterion.key}>
          <legend className="title-section px-2">{criterion.label}</legend>{[1, 2, 3, 4, 5].map(score => <label key={score} className="flex min-h-11 items-center gap-3 text-sm text-ink">
            <input type="radio" required name={criterion.key} checked={scores[criterion.key] === score} onChange={() => setScores({ ...scores, [criterion.key]: score })} />
            <span>{score} · {criterion.anchors[String(score)]}</span></label>)}
        </fieldset>)}
        <label className="grid gap-1 text-sm text-ink">{t`Private review notes`}<textarea maxLength={5000} className="desk-input" value={notes} onChange={event => setNotes(event.target.value)} /></label>
        <button className="desk-button-primary justify-self-start" type="submit" disabled={save.isPending}>{t`Submit review`}</button>
      </form> : null}
      {editable ? <Card><div className="grid gap-3"><label className="grid gap-1 text-sm text-ink">{t`Conflict`}<select className="desk-input" value={recusal} onChange={event => setRecusal(event.target.value)}>
          <option value="declared">{t`Declared conflict`}</option><option value="self">{t`My own application`}</option><option value="team">{t`My team`}</option><option value="affiliation">{t`Affiliation`}</option></select></label>
        <button className="desk-button justify-self-start" type="button" disabled={save.isPending} onClick={() => save.mutate(true)}>{t`Recuse from this application`}</button></div></Card> : null}
      <p className="text-sm text-muted">{t`Other reviewers' scores remain private until the round closes. Recuse whenever you have a conflict.`}</p>
    </div>} />
}
