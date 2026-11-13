import { t } from "@lingui/core/macro";
import { useState } from 'react'
import { DetailLayout } from '../../../components/layouts'
import { Card, Field } from '../../../components/ui'
import type { Aggregate, EventScope } from '../../events/contributions/types'
import { errorText, useProgrammeCommand, useProgrammeDetail } from '../../events/contributions/api'
import { SetupText, tags, iso, localDate, edited } from './setupFields'

interface Profile extends Aggregate { assignment_id: number; skills: string[]; availability: Array<{ starts_at: string; ends_at: string }>; affiliation: string; max_active_teams: number }
function ProfileEditor({ scope, row }: { scope: EventScope; row: Profile }) {
  const command = useProgrammeCommand(scope, 'admin')
  const [skills, setSkills] = useState(row.skills.join(', '))
  const [affiliation, setAffiliation] = useState(row.affiliation)
  const [capacity, setCapacity] = useState(String(row.max_active_teams))
  const [windows, setWindows] = useState(row.availability.map(value => ({ starts_at: localDate(value.starts_at), ends_at: localDate(value.ends_at) })))
  const [error, setError] = useState<unknown>(null)
  return <form className="grid gap-4" onSubmit={event => { event.preventDefault(); setError(null)
    try { command.mutate({ path: `/mentor-profiles/${row.assignment_id}/`, method: 'PATCH', version: row.version,
      fields: edited(row, { skills: tags(skills), affiliation, max_active_teams: Number(capacity), availability: windows.map(value => ({ starts_at: iso(value.starts_at), ends_at: iso(value.ends_at) })) }) }) }
    catch (cause) { setError(cause) }
  }}>
    <SetupText label={t`Mentor skills, separated by commas`} value={skills} onChange={setSkills} />
    <SetupText label={t`Private affiliation`} value={affiliation} onChange={setAffiliation} />
    <SetupText label={t`Maximum active teams (1–100)`} type="number" value={capacity} onChange={setCapacity} />
    <fieldset className="grid gap-3"><legend className="mb-2 font-semibold">{t`Availability windows`}</legend>
      {windows.map((window, index) => <div key={index} className="grid gap-2 sm:grid-cols-3">
        <SetupText label={t`Window ${index + 1} starts (local time)`} type="datetime-local" value={window.starts_at} onChange={value => setWindows(windows.map((item, i) => i === index ? { ...item, starts_at: value } : item))} required />
        <SetupText label={t`Window ${index + 1} ends (local time)`} type="datetime-local" value={window.ends_at} onChange={value => setWindows(windows.map((item, i) => i === index ? { ...item, ends_at: value } : item))} required />
        <button type="button" className="desk-button min-h-11" onClick={() => setWindows(windows.filter((_, i) => i !== index))}>{t`Remove window ${index + 1}`}</button>
      </div>)}
      <button type="button" className="desk-button min-h-11" disabled={windows.length >= 50} onClick={() => setWindows([...windows, { starts_at: '', ends_at: '' }])}>{t`Add availability window`}</button>
    </fieldset>
    {error || command.error ? <p role="alert" className="text-danger">{errorText(error ?? command.error)}</p> : null}
    {command.isSuccess ? <p role="status">{t`Mentor settings saved.`}</p> : null}
    <button type="submit" className="desk-button-primary min-h-11" disabled={command.isPending}>{t`Save mentor settings`}</button>
  </form>
}

export function MentorSettingsPanel({ scope, assignmentId }: { scope: EventScope; assignmentId: number }) {
  const query = useProgrammeDetail<Profile>(scope, 'admin', `/mentor-profiles/${assignmentId}/`)
  return <DetailLayout title={t`Mentor settings`} state={query.isPending ? { status: 'loading' } : query.isError ? { status: 'error', error: errorText(query.error), onRetry: () => { void query.refetch() } } : { status: 'ready' }}
    main={<Card>{query.data ? <ProfileEditor key={query.data.id} scope={scope} row={query.data} /> : null}</Card>} />
}

export function HelpCategoryEditor({ scope, initial }: { scope: EventScope; initial?: Aggregate & { key: string; label: string; skill_tags: string[]; priority: number; open_limit: number; claim_minutes: number; expiry_minutes: number; organizer_contact_action: string } }) {
  const command = useProgrammeCommand(scope, 'admin')
  const [key, setKey] = useState(initial?.key ?? '')
  const [label, setLabel] = useState(initial?.label ?? '')
  const [skills, setSkills] = useState(initial?.skill_tags.join(', ') ?? '')
  const [priority, setPriority] = useState(String(initial?.priority ?? 0))
  const [limit, setLimit] = useState(String(initial?.open_limit ?? 1))
  const [claim, setClaim] = useState(String(initial?.claim_minutes ?? 10))
  const [expiry, setExpiry] = useState(String(initial?.expiry_minutes ?? 240))
  const [contact, setContact] = useState(initial?.organizer_contact_action ?? '')
  return <Card><h2 className="title-section">{t`Help category`}</h2><form className="mt-4 grid gap-4" onSubmit={event => {
    event.preventDefault(); command.mutate({ path: initial ? `/help-types/${initial.id}/` : '/help-types/', method: initial ? 'PATCH' : 'POST', version: initial?.version ?? 0,
      fields: edited(initial, { key, label, skill_tags: tags(skills), priority: Number(priority), open_limit: Number(limit), claim_minutes: Number(claim), expiry_minutes: Number(expiry), organizer_contact_action: contact }) })
  }}>
    <SetupText label={t`Category key`} value={key} onChange={setKey} required /><SetupText label={t`Category label`} value={label} onChange={setLabel} required />
    <SetupText label={t`Category skills`} value={skills} onChange={setSkills} /><SetupText label={t`Priority (0–100)`} type="number" value={priority} onChange={setPriority} />
    <SetupText label={t`Open requests per team (1–10)`} type="number" value={limit} onChange={setLimit} /><SetupText label={t`Claim lease minutes (1–60)`} type="number" value={claim} onChange={setClaim} />
    <SetupText label={t`Request expiry minutes (15–10080)`} type="number" value={expiry} onChange={setExpiry} />
    <Field label={t`Private organizer contact action`}><textarea className="desk-input" maxLength={300} value={contact} onChange={event => setContact(event.target.value)} /></Field>
    {command.error ? <p role="alert" className="text-danger">{errorText(command.error)}</p> : null}
    {command.isSuccess ? <p role="status">{t`Help category saved.`}</p> : null}
    <button type="submit" className="desk-button-primary min-h-11" disabled={command.isPending}>{t`Save help category`}</button>
  </form></Card>
}
