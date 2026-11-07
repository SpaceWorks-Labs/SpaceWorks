import { t } from "@lingui/core/macro";
import { useState } from 'react'
import { Card, Field, ActionControl } from '../../../components/ui'
import { errorText, useProgrammeCommand } from '../../events/contributions/api'
import type { Aggregate, EventScope } from '../../events/contributions/types'
import { SetupText, Toggle, iso, localDate, tags, edited } from './setupFields'
import type { RoleFormBuilder } from './PostingEditor'
import { RoundHelpTriggers, type HelpTrigger } from './RoundHelpTriggers'

interface RoundConfig extends Aggregate {
  index: number; key: string; label: string; opens_at: string; closes_at: string
  form_schema: Record<string, unknown>; note_keys: string[]; rating_keys: string[]
  allow_fresh_eyes_override: boolean; allow_conflict_override: boolean; practice_run_id: string | null
  help_trigger_rules: HelpTrigger[]
}
export function MentorRoundSetup({ scope, initial, renderFormBuilder }: { scope: EventScope; initial?: RoundConfig; renderFormBuilder: RoleFormBuilder }) {
  const command = useProgrammeCommand(scope, 'admin')
  const [index, setIndex] = useState(String(initial?.index ?? 1))
  const [key, setKey] = useState(initial?.key ?? '')
  const [label, setLabel] = useState(initial?.label ?? '')
  const [opens, setOpens] = useState(localDate(initial?.opens_at))
  const [closes, setCloses] = useState(localDate(initial?.closes_at))
  const [schema, setSchema] = useState(initial?.form_schema ?? {})
  const [notes, setNotes] = useState(initial?.note_keys.join(', ') ?? '')
  const [ratings, setRatings] = useState(initial?.rating_keys.join(', ') ?? '')
  const [fresh, setFresh] = useState(initial?.allow_fresh_eyes_override ?? false)
  const [conflict, setConflict] = useState(initial?.allow_conflict_override ?? false)
  const [practice, setPractice] = useState(initial?.practice_run_id ?? '')
  const [triggers, setTriggers] = useState(initial?.help_trigger_rules ?? [])
  const [error, setError] = useState<unknown>(null)
  return <Card><h2 className="title-section">{t`Mentor round setup`}</h2><form className="mt-4 grid gap-4" onSubmit={event => {
    event.preventDefault(); setError(null)
    try { command.mutate({ path: initial ? `/mentor-rounds/${initial.id}/` : '/mentor-rounds/', method: initial ? 'PATCH' : 'POST', version: initial?.version ?? 0,
      fields: edited(initial, { index: Number(index), key, label, opens_at: iso(opens), closes_at: iso(closes), form_schema: schema,
        note_keys: tags(notes), rating_keys: tags(ratings), allow_fresh_eyes_override: fresh, allow_conflict_override: conflict, practice_run_id: practice || null, help_trigger_rules: triggers }) }) }
    catch (cause) { setError(cause) }
  }}>
    <SetupText label={t`Round index`} type="number" value={index} onChange={setIndex} required /><SetupText label={t`Round key`} value={key} onChange={setKey} required />
    <SetupText label={t`Round label`} value={label} onChange={setLabel} required />
    <SetupText label={t`Round opens (local time)`} type="datetime-local" value={opens} onChange={setOpens} required /><SetupText label={t`Round closes (local time)`} type="datetime-local" value={closes} onChange={setCloses} required />
    {renderFormBuilder({ schema, onChange: setSchema, disabled: command.isPending })}
    <SetupText label={t`Factual note keys`} value={notes} onChange={setNotes} /><SetupText label={t`Private rating keys`} value={ratings} onChange={setRatings} />
    <RoundHelpTriggers rules={triggers} onChange={setTriggers} />
    <Toggle checked={fresh} onChange={setFresh}>{t`Permit fresh-eyes exceptions with a reason`}</Toggle><Toggle checked={conflict} onChange={setConflict}>{t`Permit round visit conflict exceptions with a reason`}</Toggle>
    <p className="text-sm text-muted">{t`Judging conflicts remain mandatory regardless of a round visit exception.`}</p>
    <Field label={t`Practice run UUID (blank for production)`}><input className="desk-input" value={practice} onChange={event => setPractice(event.target.value)} /></Field>
    {error || command.error ? <p role="alert" className="text-danger">{errorText(error ?? command.error)}</p> : null}
    <button type="submit" className="desk-button-primary min-h-11" disabled={command.isPending}>{t`Save round`}</button>
  </form>{initial ? <div className="mt-4 flex flex-wrap gap-2">{(initial.state === 'draft' ? ['open', 'skip'] : initial.state === 'live' ? ['close'] : []).map(action => <ActionControl key={action} action={{ label: `${action[0].toUpperCase()}${action.slice(1)} round`, pending: command.isPending,
    onClick: () => command.mutate({ path: `/mentor-rounds/${initial.id}/${action}/`, version: initial.version }) }} />)}</div> : null}</Card>
}
