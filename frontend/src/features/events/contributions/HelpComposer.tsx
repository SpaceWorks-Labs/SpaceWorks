import { t } from "@lingui/core/macro";
import { useState } from 'react'
import { Card, Field } from '../../../components/ui'
import type { EventScope } from './types'
import { errorText, useProgrammeCommand, type Surface } from './api'

export function HelpComposer({ scope, surface, teams, categories }: {
  scope: EventScope; surface: Surface; teams: Array<{ id: number; label: string }>; categories: Array<{ key: string; label: string }>
}) {
  const [team, setTeam] = useState(teams[0]?.id ?? 0)
  const [category, setCategory] = useState(categories[0]?.key ?? '')
  const [summary, setSummary] = useState('')
  const [table, setTable] = useState('')
  const command = useProgrammeCommand(scope, surface)
  // No teams means a drop-in request on an event without hackathon teams (#128 C-36, E2-f).
  const dropIn = teams.length === 0
  return <Card><form className="grid gap-4" onSubmit={event => {
    event.preventDefault()
    command.mutate({ path: '/help/', version: 0, fields: { ...(dropIn ? {} : { team_id: team }), type_key: category, summary, zone: table ? { table } : {} } },
      { onSuccess: () => { setSummary(''); setTable('') } })
  }}>
    <h2 className="title-section">{surface === 'admin' ? t`Raise help for a team` : t`Ask a mentor`}</h2>
    <p className="text-sm text-muted">{t`Describe the problem for your mentor. Your description stays inside the event; chat alerts carry the category only.`}</p>
    {dropIn ? null : <Field label={t`Team`}><select className="desk-input" value={team} onChange={event => setTeam(Number(event.target.value))} required>
      <option value={0} disabled>{t`Select your team`}</option>{teams.map(row => <option key={row.id} value={row.id}>{row.label}</option>)}</select></Field>}
    <Field label={t`Help category`}><select className="desk-input" value={category} onChange={event => setCategory(event.target.value)} required>
      <option value="" disabled>{t`Select category`}</option>{categories.map(row => <option key={row.key} value={row.key}>{row.label}</option>)}</select></Field>
    <Field label={t`What do you need help with?`}><textarea className="desk-input min-h-28" maxLength={2000} value={summary} onChange={event => setSummary(event.target.value)} required /></Field>
    <Field label={t`Table or bench`} hint={t`Optional. Use your event's table label.`}><input className="desk-input" maxLength={40} value={table} onChange={event => setTable(event.target.value)} /></Field>
    {command.error ? <p role="alert" className="text-danger">{errorText(command.error)}</p> : null}
    <button type="submit" className="desk-button-primary min-h-11" disabled={command.isPending || (!dropIn && !team) || !category}>{command.isPending ? t`Sending…` : t`Request help`}</button>
  </form></Card>
}
