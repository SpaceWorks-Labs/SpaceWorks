import { t } from "@lingui/core/macro";
import { useEffect, useState } from 'react'
import { Card } from '../../../components/ui'
import type { Application } from './types'

export function AnswerDateReview({ application, pending, onReview }: { application: Application; pending: boolean
  onReview: (body: Record<string, unknown>) => void }) {
  const review = application.answer_review
  const [confirmed, setConfirmed] = useState(false)
  useEffect(() => setConfirmed(false), [review?.event_date_revision, review?.as_of_date])
  if (!review?.date_review_required) return null
  const ages = application.answers.filter(answer => answer.type === 'age_at_event')
  return <Card><section className="grid gap-3" aria-label={t`Review event date`}><h2 className="title-section">{t`Review your answers for the event date`}</h2>
    <p className="text-sm text-ink">{t`Your answers use ${review.as_of_date}`}{review.locked ? t` (the locked event-start date)` : ' as the event-start date'}.</p>
    {ages.map(answer => <p className="text-sm text-ink" key={String(answer.id)}>{t`Age at event start: ${String(answer.value)} as of ${review.as_of_date}.`}</p>)}
    <label className="flex min-h-11 items-center gap-3 text-sm text-ink"><input type="checkbox" checked={confirmed}
      onChange={event => setConfirmed(event.target.checked)} />{t`I have reviewed my answers for this date.`}</label>
    <button className="desk-button-primary justify-self-start" type="button" disabled={!confirmed || pending} onClick={() => onReview({
      expected_version: application.version, event_date_revision: review.event_date_revision, as_of_date: review.as_of_date, confirmed: true })}>{t`Confirm date review`}</button>
  </section></Card>
}
