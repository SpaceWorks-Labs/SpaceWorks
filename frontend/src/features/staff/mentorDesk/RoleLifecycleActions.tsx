import { useState } from 'react'
import { ActionControl, Field } from '../../../components/ui'
import type { EventScope, RoleApplication } from '../../events/contributions/types'
import { errorText, useProgrammeCommand } from '../../events/contributions/api'

/** G mounts after registering the C2 completion contracts. */
export function RoleLifecycleActions({ scope, row }: { scope: EventScope; row: RoleApplication & { imported_inert?: boolean } }) {
  const command = useProgrammeCommand(scope, 'admin')
  const [reason, setReason] = useState('')
  const [reference, setReference] = useState('')
  const [kind, setKind] = useState('training')
  const [ticket, setTicket] = useState('')
  const [capacityPolicy, setCapacityPolicy] = useState('event_capacity')
  const actions = row.imported_inert ? ['reconfirm'] : row.state === 'approved' ? ['complete', 'reopen-answers'] : ['proposed', 'applied'].includes(row.state) ? ['reject', 'reopen-answers'] : []
  return <div className="mt-4 grid gap-3">
    <Field label={`Reason for application ${row.id}`}><textarea className="desk-input" maxLength={2000} value={reason} onChange={event => setReason(event.target.value)} /></Field>
    <div className="flex flex-wrap gap-2">{actions.map(action => <ActionControl key={action} action={{ label: ({ complete: 'Complete role', 'reopen-answers': 'Reopen answers as a new revision', reconfirm: 'Request imported role reconfirmation', reject: 'Decline application' })[action] ?? action,
      pending: command.isPending, disabled: !reason.trim(), disabledReason: !reason.trim() ? 'Add a reason first.' : undefined,
      onClick: () => command.mutate({ path: `/roles/${row.id}/${action}/`, version: row.version, fields: { reason } }) }} />)}</div>
    <details><summary className="min-h-11 cursor-pointer py-3 font-semibold">Training or briefing exception</summary>
      <p className="mb-3 text-sm text-muted">Waiver and code-of-conduct evidence remain required.</p>
      <Field label={`Exception kind for application ${row.id}`}><select className="desk-input min-h-11" value={kind} onChange={event => setKind(event.target.value)}><option value="training">Training</option><option value="briefing">Briefing</option></select></Field>
      <Field label={`Requirement ID for application ${row.id}`}><input className="desk-input" type="number" min={1} value={reference} onChange={event => setReference(event.target.value)} /></Field>
      <ActionControl action={{ label: 'Record requirement exception', pending: command.isPending, disabled: !reason.trim() || !reference,
        onClick: () => command.mutate({ path: `/roles/${row.id}/requirement-overrides/`, version: row.version, fields: { reason, kind, reference_id: Number(reference) } }) }} />
    </details>
    {row.state === 'approved' && !row.imported_inert ? <details><summary className="min-h-11 cursor-pointer py-3 font-semibold">Admit with a contributor ticket</summary>
      <Field label={`Contributor ticket type for application ${row.id}`}><input className="desk-input" type="number" min={1} value={ticket} onChange={event => setTicket(event.target.value)} /></Field>
      <Field label={`Capacity policy for application ${row.id}`}><select className="desk-input min-h-11" value={capacityPolicy} onChange={event => setCapacityPolicy(event.target.value)}><option value="event_capacity">Count against event capacity</option><option value="reserved_contributor_capacity">Use configured contributor capacity</option></select></Field>
      <ActionControl action={{ label: 'Admit contributor', pending: command.isPending, disabled: !ticket,
        onClick: () => command.mutate({ path: `/roles/${row.id}/admit/`, version: row.version, fields: { ticket_type_id: Number(ticket), capacity_policy: capacityPolicy } }) }} />
    </details> : null}
    {command.error ? <p role="alert" className="text-danger">{errorText(command.error)}</p> : null}
  </div>
}
