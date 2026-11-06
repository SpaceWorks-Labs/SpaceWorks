import { t } from "@lingui/core/macro";
import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { DetailLayout } from '../../../components/layouts'
import { ActionControl, Card, Field } from '../../../components/ui'
import { basePath, errorText, requestFor, useProgrammeCommand } from '../../events/contributions/api'
import type { EventScope } from '../../events/contributions/types'
import { MentorAssignmentLifecycle } from './MentorAssignmentLifecycle'

interface Preview { assignments: Array<{ team_id: number; mentor_assignment_id: number }>; unsatisfied_team_ids: number[] }
export function MentorAssignmentsPanel({ scope, eventVersion, teams, mentors, completionReady = false }: {
  scope: EventScope; eventVersion: number; teams: Array<{ id: number; label: string }>; mentors: Array<{ id: number; label: string }>; completionReady?: boolean
}) {
  const [mode, setMode] = useState('round_robin')
  const [selected, setSelected] = useState<number[]>([])
  const [manual, setManual] = useState<Record<number, number>>({})
  const [previewIdentity, setPreviewIdentity] = useState('')
  const fields = { team_ids: selected, mode, manual: mode === 'manual' ? selected.map(team_id => ({ team_id, mentor_assignment_id: manual[team_id] })) : [] }
  const identity = JSON.stringify(fields)
  const preview = useMutation({ mutationFn: () => {
    const operation = crypto.randomUUID()
    return requestFor('admin')<Preview>(`${basePath(scope, 'admin')}/mentor-assignments/preview/`, { method: 'POST',
      headers: { 'Idempotency-Key': operation }, body: JSON.stringify({ ...fields, operation_id: operation, expected_version: eventVersion }) })
  }, onSuccess: () => setPreviewIdentity(identity) })
  const assign = useProgrammeCommand(scope, 'admin')
  return <DetailLayout title={t`Mentor assignments`} state={{ status: 'ready' }} main={<><Card>
    <p className="mb-4 text-sm text-muted">{t`Preview excludes unavailable mentors, conflicts, and full workloads. Committing rechecks the current roster.`}</p>
    <Field label={t`Assignment mode`}><select className="desk-input" value={mode} onChange={event => setMode(event.target.value)}>
      <option value="round_robin">{t`Balanced round-robin`}</option><option value="skill_match">{t`Match skills, then balance load`}</option><option value="manual">{t`Choose mentors manually`}</option></select></Field>
    <fieldset className="my-4 grid gap-3"><legend className="mb-2 font-semibold">{t`Teams to cover`}</legend>{teams.map(team => <div key={team.id} className="grid gap-2 sm:grid-cols-2">
      <label className="flex min-h-11 items-center gap-3"><input type="checkbox" checked={selected.includes(team.id)} onChange={event => setSelected(event.target.checked ? [...selected, team.id] : selected.filter(id => id !== team.id))} />{team.label}</label>
      {mode === 'manual' && selected.includes(team.id) ? <Field label={t`Mentor for ${team.label}`}><select className="desk-input" value={manual[team.id] ?? ''} onChange={event => setManual({ ...manual, [team.id]: Number(event.target.value) })}>
        <option value="">{t`Select mentor`}</option>{mentors.map(mentor => <option key={mentor.id} value={mentor.id}>{mentor.label}</option>)}</select></Field> : null}
    </div>)}</fieldset>
    {(preview.error || assign.error) ? <p role="alert" className="mb-3 text-danger">{errorText(preview.error ?? assign.error)}</p> : null}
    {preview.data && previewIdentity === identity ? <div role="status" className="mb-4 text-sm"><p>{t`${preview.data.assignments.length} teams covered · ${preview.data.unsatisfied_team_ids.length} still need a mentor`}</p>
      <ul>{preview.data.assignments.map(item => <li key={item.team_id}>{teams.find(x => x.id === item.team_id)?.label} → {mentors.find(x => x.id === item.mentor_assignment_id)?.label ?? t`Mentor ${item.mentor_assignment_id}`}</li>)}</ul></div> : null}
    <div className="flex flex-wrap gap-3"><ActionControl action={{ label: t`Preview assignments`, pending: preview.isPending, disabled: !selected.length,
      disabledReason: !selected.length ? 'Select at least one team.' : undefined, onClick: () => preview.mutate() }} />
      {preview.data && previewIdentity === identity ? <ActionControl primary action={{ label: t`Assign mentors`, pending: assign.isPending,
        confirm: { title: t`Assign these mentors?`, message: t`Current availability and conflicts will be checked again.` },
        onClick: () => assign.mutate({ path: '/mentor-assignments/assign/', version: eventVersion, fields }, { onSuccess: () => { preview.reset(); setSelected([]) } }) }} /> : null}</div>
  </Card>{completionReady ? <MentorAssignmentLifecycle scope={scope} /> : null}</>} />
}
