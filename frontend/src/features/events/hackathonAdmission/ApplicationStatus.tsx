import { formatDateTime } from "../../../lib/format";
import { t } from "@lingui/core/macro";
import { useQuery } from '@tanstack/react-query'
import { Clock, Users } from 'lucide-react'
import { useParams } from 'react-router-dom'
import { useChargesOn } from '../../../lib/charges'
import { DetailLayout } from '../../../components/layouts'
import { Card, ErrorText, StatusBadge } from '../../../components/ui'
import { readMember } from './transport'
import { AnswerDateReview } from './AnswerDateReview'
import { HostConsentRepair } from './HostConsentRepair'
import type { Application } from './types'
import { applicationStateLabel } from './labels'

export function ApplicationStatus({ application, pending, error, onAction, onRepair, onReapply, onDateReview }: {
  application: Application; pending: boolean; error: Error | null
  onDateReview: (body: Record<string, unknown>) => void
  onRepair: (body: Record<string, unknown>) => void; onReapply: () => void
  onAction: (action: 'accept' | 'decline' | 'waitlist' | 'withdraw') => void
}) {
  const intent = useQuery({ queryKey: ['saved-detail-intent', application.save_intent?.operation_id],
    queryFn: () => readMember<{ state: string }>(application.save_intent!.status_url), enabled: Boolean(application.save_intent),
    refetchInterval: q => q.state.data?.state === 'pending' ? 2000 : false, staleTime: 0, gcTime: 0, retry: false })
  const offered = application.state === 'offered'
  const showPrice = useChargesOn('events', useParams().slug) // #184: free events show no quote
  return <DetailLayout title={t`Your application`} state={{ status: 'ready' }} status={<StatusBadge status={application.state} label={applicationStateLabel(application.state)} />}
    main={<div className="grid gap-4">
      {error ? <ErrorText message={error.message} /> : null}
      <Card><div className="flex items-start gap-3 text-ink"><Clock aria-hidden="true" className="size-5 shrink-0" /><div>
        <h2 className="title-section">{offered ? t`A place is on offer` : application.state === 'confirmed' ? t`Your place is confirmed` : t`Application progress`}</h2>
        <p className="mt-1 text-sm text-muted">{offered ? t`Reply before the deadline. Offers can exceed the number of confirmed seats; a seat is reserved when your RSVP completes.`
          : application.state === 'submitted' ? t`Your application is with the event team. A decision appears here after it is released.`
          : application.state === 'waitlisted' ? t`You are on the waitlist. We will let you know when a place can be offered.` : t`Your latest application state is shown above.`}</p>
        {application.rsvp_due_at ? <p className="mt-2 text-sm">{t`Reply by ${formatDateTime(application.rsvp_due_at)}.`}</p> : null}
      </div></div></Card>
      <AnswerDateReview application={application} pending={pending} onReview={onDateReview} />
      <HostConsentRepair application={application} pending={pending} onRepair={onRepair} />
      {application.allowed_actions.includes("edit") ? <button className="desk-button" type="button" disabled={pending} onClick={onReapply}>{application.state === 'submitted' ? t`Edit application answers` : t`Start reapplication`}</button> : null}
      {application.rsvp_accepted_at && offered ? <p className="flex items-center gap-2 text-sm text-ink"><Users aria-hidden="true" className="size-5" />{t`Your reply is saved. Your whole team must accept before confirmation.`}</p> : null}
      {offered ? <div className="flex flex-wrap gap-3">
        <button className="desk-button-primary" type="button" disabled={pending || Boolean(application.rsvp_accepted_at)} onClick={() => onAction('accept')}>{t`Accept offer`}</button>
        <button className="desk-button" type="button" disabled={pending} onClick={() => onAction('decline')}>{t`Decline offer`}</button>
        <button className="desk-button" type="button" disabled={pending} onClick={() => onAction('waitlist')}>{t`Choose waitlist`}</button>
      </div> : null}
      {application.allowed_actions.includes('withdraw') ? <button className="desk-button-danger-outline justify-self-start" type="button" disabled={pending}
        onClick={() => onAction('withdraw')}>{t`Withdraw application`}</button> : null}
      {showPrice && application.admission.quote ? <p className="text-sm text-ink">{t`Ticket quote: ${application.admission.quote.currency} ${application.admission.quote.amount}. Charges are recorded when your place is confirmed.`}</p> : null}
      {application.save_intent ? <p role="status" className="text-sm text-muted">{t`Saved details: ${intent.data?.state ?? application.save_intent.state}.`}{['conflict', 'failed'].includes(intent.data?.state ?? '') ? t` Your application succeeded. Review your Saved details to resolve the separate save.` : ''}</p> : null}
      {intent.error ? <ErrorText message={t`Your application succeeded. Saved-detail status is temporarily unavailable.`} /> : null}
    </div>} />
}
