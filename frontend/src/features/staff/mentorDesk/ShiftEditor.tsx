import { useState } from 'react'
import { Card, Field } from '../../../components/ui'
import { errorText, useProgrammeCommand } from '../../events/contributions/api'
import type { EventScope, Shift } from '../../events/contributions/types'
import { SetupText, Toggle, ids, iso, localDate, tags, edited } from './setupFields'

export interface ShiftConfig extends Shift {
  signup_deadline: string; mentor_assignment_id: number | null; grace_minutes: number
  approval_required: boolean; waitlist_enabled: boolean; permission_preset: string[]
  requirements: { training_ids?: number[]; briefing_ids?: number[]; host_waiver_required?: boolean }
}
export function ShiftEditor({ scope, initial, onSaved }: { scope: EventScope; initial?: ShiftConfig; onSaved: () => void }) {
  const command = useProgrammeCommand(scope, 'admin')
  const [posting, setPosting] = useState(String(initial?.posting_id ?? ''))
  const [kind, setKind] = useState(initial?.kind ?? 'volunteer')
  const [mentor, setMentor] = useState(String(initial?.mentor_assignment_id ?? ''))
  const [task, setTask] = useState(initial?.task ?? '')
  const [zone, setZone] = useState(initial?.zone ?? '')
  const [start, setStart] = useState(localDate(initial?.starts_at))
  const [end, setEnd] = useState(localDate(initial?.ends_at))
  const [deadline, setDeadline] = useState(localDate(initial?.signup_deadline))
  const [capacity, setCapacity] = useState(String(initial?.capacity ?? 0))
  const [grace, setGrace] = useState(String(initial?.grace_minutes ?? 15))
  const [waitlist, setWaitlist] = useState(initial?.waitlist_enabled ?? true)
  const [approval, setApproval] = useState(initial?.approval_required ?? true)
  const [training, setTraining] = useState(initial?.requirements.training_ids?.join(', ') ?? '')
  const [briefing, setBriefing] = useState(initial?.requirements.briefing_ids?.join(', ') ?? '')
  const [waiver, setWaiver] = useState(initial?.requirements.host_waiver_required ?? false)
  const [permissions, setPermissions] = useState(initial?.permission_preset.join(', ') ?? '')
  const [state, setState] = useState(initial?.state ?? 'open')
  const [cancel, setCancel] = useState(false)
  const [reason, setReason] = useState('')
  const [error, setError] = useState<unknown>(null)
  return <Card><h2 className="title-section">{initial ? 'Edit shift or office hours' : 'Create shift or office hours'}</h2>
    <form className="mt-4 grid gap-4" onSubmit={event => {
      event.preventDefault(); setError(null)
      try {
        const postingId = ids(posting)
        if (postingId.length !== 1) throw new Error('Choose one posting ID.')
        command.mutate({ path: initial ? `/shifts/${initial.id}/` : '/shifts/', method: initial ? 'PATCH' : 'POST', version: initial?.version ?? 0,
          fields: edited(initial, { posting_id: postingId[0], kind, mentor_assignment_id: kind === 'office_hours' ? Number(mentor) : null,
            task, zone, starts_at: iso(start), ends_at: iso(end), signup_deadline: iso(deadline), capacity: Number(capacity), grace_minutes: Number(grace),
            waitlist_enabled: waitlist, approval_required: approval, state, permission_preset: tags(permissions),
            requirements: { training_ids: ids(training), briefing_ids: ids(briefing), host_waiver_required: waiver },
            ...(initial && kind === 'office_hours' && cancel ? { cancel_bookings: true, reason } : {}) }) }, { onSuccess: onSaved })
      } catch (cause) { setError(cause) }
    }}>
      <SetupText label="Posting ID" type="number" value={posting} onChange={setPosting} required />
      <Field label="Shift kind"><select className="desk-input min-h-11" value={kind} onChange={event => setKind(event.target.value as typeof kind)}><option value="volunteer">Volunteer duty</option><option value="office_hours">Office hours · one place per team</option></select></Field>
      {kind === 'office_hours' ? <SetupText label="Mentor role assignment ID" type="number" value={mentor} onChange={setMentor} required /> : null}
      <SetupText label="Task" value={task} onChange={setTask} required /><SetupText label="Zone" value={zone} onChange={setZone} />
      <SetupText label="Shift starts (your local time)" type="datetime-local" value={start} onChange={setStart} required />
      <SetupText label="Shift ends (your local time)" type="datetime-local" value={end} onChange={setEnd} required />
      <SetupText label="Signup deadline (your local time)" type="datetime-local" value={deadline} onChange={setDeadline} required />
      <SetupText label="Capacity (0 is unlimited)" type="number" value={capacity} onChange={setCapacity} />
      <SetupText label="Grace minutes (0–60)" type="number" value={grace} onChange={setGrace} />
      <Toggle checked={waitlist} onChange={setWaitlist}>Enable waitlist</Toggle><Toggle checked={approval} onChange={setApproval}>Approve signups individually</Toggle>
      <Toggle checked={waiver} onChange={setWaiver}>Host waiver required</Toggle>
      <SetupText label="Required training IDs" value={training} onChange={setTraining} /><SetupText label="Required briefing IDs" value={briefing} onChange={setBriefing} />
      <SetupText label="Duty permissions, separated by commas" value={permissions} onChange={setPermissions} />
      <Field label="Shift state"><select className="desk-input min-h-11" value={state} onChange={event => setState(event.target.value)}><option value="open">Open</option><option value="closed">Closed</option></select></Field>
      {initial && kind === 'office_hours' ? <><Toggle checked={cancel} onChange={setCancel}>Cancel existing team bookings and notify teams before rescheduling</Toggle>
        {cancel ? <Field label="Reschedule reason"><textarea className="desk-input" required maxLength={2000} value={reason} onChange={event => setReason(event.target.value)} /></Field> : null}</> : null}
      {error || command.error ? <p role="alert" className="text-danger">{errorText(error ?? command.error)}</p> : null}
      <button type="submit" className="desk-button-primary min-h-11" disabled={command.isPending}>{command.isPending ? 'Saving…' : 'Save shift'}</button>
    </form></Card>
}
