import { useState } from 'react'
import { Card, Field } from '../../../components/ui'
import type { EventScope } from '../../events/contributions/types'
import { errorText, useProgrammeCommand } from '../../events/contributions/api'
import { SetupText } from './setupFields'

export function MentorConflictForm({ scope, assignmentId, initial }: { scope: EventScope; assignmentId: number; initial?: { team_id: number; kind: string; version: number; reason: string } }) {
  const command = useProgrammeCommand(scope, 'admin')
  const [team, setTeam] = useState(String(initial?.team_id ?? ''))
  const [reason, setReason] = useState(initial?.reason ?? '')
  const [active, setActive] = useState(true)
  return <Card><h2 className="title-section">Declare a team conflict</h2><form className="mt-4 grid gap-4" onSubmit={event => {
    event.preventDefault(); command.mutate({ path: '/mentor-conflicts/', version: initial?.version ?? 0,
      fields: { mentor_assignment_id: assignmentId, team_id: Number(team), kind: initial?.kind ?? 'declared', active, reason } })
  }}>
    <SetupText label="Conflicting team ID" type="number" value={team} onChange={setTeam} required />
    <Field label="Private conflict reason"><textarea className="desk-input" maxLength={2000} required value={reason} onChange={event => setReason(event.target.value)} /></Field>
    {initial ? <Field label="Conflict state"><select className="desk-input min-h-11" value={String(active)} onChange={event => setActive(event.target.value === 'true')}><option value="true">Active conflict</option><option value="false">End declared conflict</option></select></Field> : null}
    {command.error ? <p role="alert" className="text-danger">{errorText(command.error)}</p> : null}
    {command.isSuccess ? <p role="status">Conflict declaration saved.</p> : null}
    <button type="submit" className="desk-button-primary min-h-11" disabled={command.isPending}>Save conflict declaration</button>
  </form></Card>
}
