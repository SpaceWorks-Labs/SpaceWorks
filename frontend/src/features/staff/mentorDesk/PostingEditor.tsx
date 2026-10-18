import { useState, type ReactNode } from 'react'
import { Card, Field } from '../../../components/ui'
import type { Aggregate, EventScope } from '../../events/contributions/types'
import { errorText, useProgrammeCommand } from '../../events/contributions/api'
import { SetupText, Toggle, ids, iso, localDate, tags, edited } from './setupFields'

export interface PostingConfig extends Aggregate {
  title: string; role: 'mentor' | 'volunteer'; description: string; briefing: string; skills: string[]
  visibility: string; approval_required: boolean; opens_at: string; closes_at: string
  requirements: { training_ids?: number[]; briefing_ids?: number[]; host_waiver_required?: boolean }
  permission_preset: string[]; form_schema: Record<string, unknown>
}
export type RoleFormBuilder = (input: { schema: Record<string, unknown>; onChange: (schema: Record<string, unknown>) => void; disabled: boolean }) => ReactNode

export function PostingEditor({ scope, initial, renderFormBuilder, onSaved }: {
  scope: EventScope; initial?: PostingConfig; renderFormBuilder: RoleFormBuilder; onSaved: () => void
}) {
  const command = useProgrammeCommand(scope, 'admin')
  const [title, setTitle] = useState(initial?.title ?? '')
  const [role, setRole] = useState(initial?.role ?? 'volunteer')
  const [description, setDescription] = useState(initial?.description ?? '')
  const [briefing, setBriefing] = useState(initial?.briefing ?? '')
  const [skills, setSkills] = useState(initial?.skills.join(', ') ?? '')
  const [visibility, setVisibility] = useState(initial?.visibility ?? 'public')
  const [approval, setApproval] = useState(initial?.approval_required ?? true)
  const [opens, setOpens] = useState(localDate(initial?.opens_at))
  const [closes, setCloses] = useState(localDate(initial?.closes_at))
  const [state, setState] = useState(initial?.state ?? 'draft')
  const [training, setTraining] = useState(initial?.requirements.training_ids?.join(', ') ?? '')
  const [briefings, setBriefings] = useState(initial?.requirements.briefing_ids?.join(', ') ?? '')
  const [waiver, setWaiver] = useState(initial?.requirements.host_waiver_required ?? false)
  const [permissions, setPermissions] = useState(initial?.permission_preset ?? [])
  const [schema, setSchema] = useState(initial?.form_schema ?? {})
  const [error, setError] = useState<unknown>(null)
  const available = role === 'mentor' ? ['mentor_queue'] : ['check_in', 'publish_schedule']
  return <Card><h2 className="title-section">{initial ? 'Edit contributor posting' : 'Create contributor posting'}</h2>
    <form className="mt-4 grid gap-4" onSubmit={event => {
      event.preventDefault(); setError(null)
      try {
        command.mutate({ path: initial ? `/volunteer-postings/${initial.id}/` : '/volunteer-postings/', method: initial ? 'PATCH' : 'POST', version: initial?.version ?? 0,
          fields: edited(initial, { role, title, description, briefing, skills: tags(skills), visibility, approval_required: approval, opens_at: iso(opens), closes_at: iso(closes),
            requirements: { training_ids: ids(training), briefing_ids: ids(briefings), host_waiver_required: waiver },
            state, permission_preset: permissions.filter(x => available.includes(x)), form_schema: schema }) }, { onSuccess: onSaved })
      } catch (cause) { setError(cause) }
    }}>
      <SetupText label="Posting title" value={title} onChange={setTitle} required />
      <Field label="Contributor role"><select className="desk-input min-h-11" value={role} disabled={!!initial} onChange={event => { setRole(event.target.value as typeof role); setPermissions([]) }}><option value="volunteer">Volunteer</option><option value="mentor">Mentor</option></select></Field>
      <Field label="Description"><textarea className="desk-input" maxLength={10000} value={description} onChange={event => setDescription(event.target.value)} /></Field>
      <Field label="Briefing"><textarea className="desk-input" maxLength={10000} value={briefing} onChange={event => setBriefing(event.target.value)} /></Field>
      <SetupText label="Skills, separated by commas" value={skills} onChange={setSkills} />
      <Field label="Visibility"><select className="desk-input min-h-11" value={visibility} onChange={event => setVisibility(event.target.value)}><option value="public">Public</option><option value="members">Members</option><option value="audience_organizations">Audience organizations</option></select></Field>
      <SetupText label="Applications open (your local time)" type="datetime-local" value={opens} onChange={setOpens} required />
      <SetupText label="Applications close (your local time)" type="datetime-local" value={closes} onChange={setCloses} required />
      <Toggle checked={approval} onChange={setApproval}>Organizer approval required</Toggle>
      <Toggle checked={waiver} onChange={setWaiver}>Host waiver required</Toggle>
      <SetupText label="Required training IDs" value={training} onChange={setTraining} />
      <SetupText label="Required briefing IDs" value={briefings} onChange={setBriefings} />
      <fieldset><legend className="font-semibold">Permissions on approval</legend>{available.map(permission => <Toggle key={permission} checked={permissions.includes(permission)} onChange={checked => setPermissions(checked ? [...permissions, permission] : permissions.filter(x => x !== permission))}>{permission.replace(/_/g, ' ')}</Toggle>)}</fieldset>
      {renderFormBuilder({ schema, onChange: setSchema, disabled: command.isPending })}
      <Field label="Posting state"><select className="desk-input min-h-11" value={state} onChange={event => setState(event.target.value)}><option value="draft">Draft</option><option value="open">Open</option><option value="closed">Closed</option></select></Field>
      {error || command.error ? <p role="alert" className="text-danger">{errorText(error ?? command.error)}</p> : null}
      <button className="desk-button-primary min-h-11" disabled={command.isPending} type="submit">{command.isPending ? 'Saving…' : 'Save posting'}</button>
    </form></Card>
}
