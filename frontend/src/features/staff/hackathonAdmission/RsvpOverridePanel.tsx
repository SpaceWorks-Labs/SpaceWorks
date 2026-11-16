import { t } from "@lingui/core/macro";
import { useRef, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Card, ErrorText } from '../../../components/ui'
import { CommandSession } from '../../events/hackathonAdmission/transport'

export function RsvpOverridePanel({ eventId, applicationId, version }: { eventId: number; applicationId: number; version: number }) {
  const commands = useRef(new CommandSession()), client = useQueryClient()
  const [deadline, setDeadline] = useState(''), [reason, setReason] = useState('participant_requested')
  const [decision, setDecision] = useState('accept')
  const action = useMutation({ mutationFn: (extend: boolean) => commands.current.send('/api/v1/admin/events/' + eventId
    + '/applications/' + applicationId + (extend ? '/extend-rsvp/' : '/rsvp-on-behalf/'), 'POST', {
      expected_version: version, reason_code: reason, ...(extend ? { rsvp_due_at: new Date(deadline + 'Z').toISOString() } : { decision }) }, true),
    onSuccess: () => client.invalidateQueries({ queryKey: ['staff-event-admission', eventId] }) })
  return <Card><section className="grid gap-3" aria-label={t`RSVP overrides`}><h2 className="title-section">{t`RSVP assistance`}</h2>
    <p className="text-sm text-muted">{t`An override records your reason and notifies the participant. It cannot bypass confirmed-seat capacity.`}</p>
    <label className="grid gap-1 text-sm text-ink">{t`Reason`}<select className="desk-input" value={reason} onChange={e => setReason(e.target.value)}>
      <option value="participant_requested">{t`Participant requested assistance`}</option><option value="organizer_extension">{t`Organizer extended the deadline`}</option></select></label>
    <label className="grid gap-1 text-sm text-ink">{t`New deadline (UTC)`}<input type="datetime-local" className="desk-input" value={deadline} onChange={e => setDeadline(e.target.value)} /></label>
    <button className="desk-button justify-self-start" type="button" disabled={!deadline || action.isPending} onClick={() => action.mutate(true)}>{t`Extend RSVP deadline`}</button>
    <label className="grid gap-1 text-sm text-ink">{t`Participant decision`}<select className="desk-input" value={decision} onChange={e => setDecision(e.target.value)}>
      <option value="accept">{t`Accept`}</option><option value="decline">{t`Decline`}</option><option value="waitlist">{t`Choose waitlist`}</option></select></label>
    <button className="desk-button justify-self-start" type="button" disabled={action.isPending} onClick={() => action.mutate(false)}>{t`Record RSVP on behalf`}</button>
    {action.error ? <ErrorText message={action.error.message} /> : null}
  </section></Card>
}
