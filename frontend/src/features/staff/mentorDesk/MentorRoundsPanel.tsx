import { formatLocale } from "../../../lib/format";
import { t } from "@lingui/core/macro";
import { useEffect, useState, type ReactNode } from 'react'
import { ListLayout } from '../../../components/layouts'
import { mentorVisitStateLabel } from '../lifecycleLabels'
import { ActionControl, Card, Field, StatusPill } from '../../../components/ui'
import type { Aggregate, EventScope } from '../../events/contributions/types'
import { errorText, useProgrammeCommand, useProgrammeDetail } from '../../events/contributions/api'
import { clearRoundDrafts, readRoundDraft, saveRoundDraft } from './roundDrafts'

interface Lease extends Aggregate { lease_uuid: string; generation: number; expires_at: string; team_id: number }
interface TeamVisit { team_id: number; team_alias: string; visit_state: string; lease: Lease | null; prior_notes: Array<{ round_id: number; notes: Record<string, unknown>; away: boolean }> }
interface Round extends Aggregate { label: string; closes_at: string; form_schema: unknown; teams?: TeamVisit[]; next_team_ids?: number[] }
export type RoundFormRenderer = (input: { schema: unknown; answers: Record<string, unknown>; onChange: (value: Record<string, unknown>) => void; disabled: boolean }) => ReactNode

function asLease(value: Aggregate): Lease {
  const lease = value as Lease
  if (typeof lease.lease_uuid !== 'string' || !Number.isSafeInteger(lease.generation) || !lease.expires_at) throw new Error(t`The visit lease was not returned. Refresh this round.`)
  return lease
}

export function MentorRoundsPanel({ scope, roundId, sessionId, renderForm }: {
  scope: EventScope; roundId: number; sessionId: string; renderForm: RoundFormRenderer
}) {
  const query = useProgrammeDetail<Round>(scope, 'admin', `/mentor-rounds/${roundId}/`, true, true)
  const command = useProgrammeCommand(scope, 'admin')
  const { mutate: sendCommand } = command
  const [selected, setSelected] = useState<TeamVisit | null>(null)
  const [lease, setLease] = useState<Lease | null>(null)
  const [answers, setAnswers] = useState<Record<string, unknown>>({})
  const [reason, setReason] = useState('')
  const [away, setAway] = useState(false)
  const [nominate, setNominate] = useState(false)
  const [draftError, setDraftError] = useState<unknown>(null)
  const [nominated, setNominated] = useState<number[]>([])
  const row = query.data
  const draftScope = `mentor:${sessionId}:${scope.accountId}:${scope.makerspaceId}:${scope.eventId}:${roundId}`
  useEffect(() => () => { void clearRoundDrafts(draftScope).catch(() => {}) }, [draftScope])
  useEffect(() => {
    if (row?.state !== 'live') return
    const timeout = window.setTimeout(() => { void clearRoundDrafts(draftScope).catch(setDraftError) }, Math.max(0, Date.parse(row.closes_at) - Date.now()))
    return () => window.clearTimeout(timeout)
  }, [row?.closes_at, row?.state, draftScope])
  useEffect(() => {
    if (!lease || command.isPending || row?.state !== 'live') return
    const timer = window.setInterval(() => {
      if (document.visibilityState === 'hidden' || Date.parse(lease.expires_at) <= Date.now()) return
      sendCommand({ path: `/mentor-rounds/${roundId}/teams/${lease.team_id}/heartbeat/`, version: lease.version,
        fields: { lease_uuid: lease.lease_uuid, generation: lease.generation } }, { onSuccess: value => setLease(asLease(value)) })
    }, 30_000)
    return () => window.clearInterval(timer)
  }, [lease, sendCommand, command.isPending, roundId, row?.state])
  const choose = async (team: TeamVisit) => {
    setSelected(team); setLease(team.lease); setAnswers({}); setDraftError(null); setAway(false); setNominate(false)
    try { setAnswers(await readRoundDraft(draftScope, team.team_id) ?? {}) } catch (error) { setDraftError(error) }
  }
  const liveLease = lease && Date.parse(lease.expires_at) > Date.now() && row?.state === 'live'
  return <ListLayout header={{ title: row?.label ?? t`Mentor round`, subtitle: t`Use fresh eyes where possible. A saved draft still needs a live visit lease before submission.` }}
    state={query.isPending ? { status: 'loading' } : query.isError ? { status: 'error', error: errorText(query.error), onRetry: () => { void query.refetch() } } : { status: 'ready' }}
    empty={{ message: t`No teams are available in this round.` }} isEmpty={!row?.teams?.length}
    body={{ kind: 'rows', rows: <>
      {(command.error || draftError) ? <p role="alert" className="text-danger">{errorText(command.error ?? draftError)}</p> : null}
      {selected && row ? <Card><h2 className="title-section">{selected.team_alias}</h2>
        <p role="status" className="my-2 text-sm text-muted">{liveLease ? t`Visit active until ${new Date(lease.expires_at).toLocaleTimeString(formatLocale())}` : t`Claim a visit before submitting. Your saved text stays here.`}</p>
        {selected.prior_notes.map(note => <div key={note.round_id} className="my-3 text-sm text-muted">{Object.entries(note.notes).map(([key, value]) => <p key={key}>{key}: {String(value)}</p>)}</div>)}
        <Field label={t`Reason for a fresh-eyes or conflict exception`} hint={t`Only used when the organizer permits this exception.`}><textarea className="desk-input" maxLength={2000} value={reason} onChange={event => setReason(event.target.value)} /></Field>
        {renderForm({ schema: row.form_schema, answers, onChange: setAnswers, disabled: command.isPending })}
        <label className="my-4 flex min-h-11 items-center gap-3"><input type="checkbox" checked={away} onChange={event => setAway(event.target.checked)} />{t`Team is away from its spot`}</label>
        <label className="my-4 flex min-h-11 items-center gap-3"><input type="checkbox" checked={nominate} disabled={away} onChange={event => setNominate(event.target.checked)} />{t`Nominate this team for a private follow-up shortlist`}</label>
        <div className="mt-4 flex flex-wrap gap-2">
          {!liveLease ? <ActionControl action={{ label: t`Claim visit`, pending: command.isPending, onClick: () => command.mutate({ path: `/mentor-rounds/${roundId}/teams/${selected.team_id}/claim/`, version: row.version, fields: { override_reason: reason } }, { onSuccess: value => setLease(asLease(value)) }) }} /> : <>
            <ActionControl primary action={{ label: t`Submit visit`, pending: command.isPending, onClick: () => command.mutate({ path: `/mentor-rounds/${roundId}/teams/${selected.team_id}/submit/`, version: lease.version,
              fields: { lease_uuid: lease.lease_uuid, generation: lease.generation, answers, away, nominate: nominate && !away } }, { onSuccess: () => { setLease(null); setSelected(null); void clearRoundDrafts(draftScope).catch(setDraftError) } }) }} />
            <ActionControl action={{ label: t`Release visit`, pending: command.isPending, onClick: () => command.mutate({ path: `/mentor-rounds/${roundId}/teams/${selected.team_id}/release/`, version: lease.version, fields: { lease_uuid: lease.lease_uuid, generation: lease.generation } }, { onSuccess: () => setLease(null) }) }} /></>}
          <ActionControl action={{ label: t`Save draft on this device`, onClick: () => { void saveRoundDraft(draftScope, selected.team_id, row.closes_at, answers).catch(setDraftError) } }} />
        </div></Card> : null}
      {row?.teams?.map(team => <Card key={team.team_id}><div className="flex flex-wrap items-center justify-between gap-3"><h2 className="title-section">{team.team_alias}</h2><StatusPill label={mentorVisitStateLabel(team.visit_state)} tone="neutral" />
        {team.visit_state === 'done' && row ? <ActionControl action={{ label: nominated.includes(team.team_id) ? t`Nominated` : t`Nominate ${team.team_alias}`,
          pending: command.isPending, disabled: nominated.includes(team.team_id), disabledReason: nominated.includes(team.team_id) ? t`You nominated this team in this round.` : undefined,
          onClick: () => command.mutate({ path: `/mentor-rounds/${roundId}/nominations/`, version: row.version, fields: { team_id: team.team_id } },
            { onSuccess: () => setNominated(ids => [...ids, team.team_id]) }) }} /> : null}
        <ActionControl action={{ label: t`Open visit`, disabled: team.visit_state === 'done' || (team.visit_state === 'busy' && !team.lease), disabledReason: team.visit_state === 'done' ? t`This round visit is complete.` : team.visit_state === 'busy' && !team.lease ? t`Another mentor has this visit.` : undefined, onClick: () => { void choose(team) } }} />
      </div></Card>)}
    </> }} />
}
