import { t } from "@lingui/core/macro";
import { useState } from 'react'
import { DetailLayout } from '../../../components/layouts'
import { ErrorText, StatusBadge } from '../../../components/ui'
import { AdmissionArtwork } from './AdmissionArtwork'
import { TeamComments } from './TeamComments'
import { TeamEditor } from './TeamEditor'
import { LeaveTeamButton, TeamRoster } from './TeamModeration'
import { teamStateLabel } from './labels'
import { commandErrorText } from '../programmeCommandErrors'
import { useTeams } from './useTeams'
import type { ProgrammeContext } from './types'

export function TeamPage({ context, accountId, inviteUrl }: { context: ProgrammeContext; accountId: number
  inviteUrl: (teamId: number, token: string, version: number) => string }) {
  const { teams, action } = useTeams(context, accountId)
  const [invite, setInvite] = useState('')
  const team = teams.data?.results[0]
  const send = (suffix: string, body: Record<string, unknown> = {}, method: 'POST' | 'PATCH' = 'POST', onDone?: () => void) => action.mutate({
    suffix: '/teams/' + (team ? team.id + '/' : '') + suffix,
    body: { expected_version: team?.version ?? 0, ...body }, method }, { onSuccess: () => onDone?.() })
  return <DetailLayout title={team?.name ?? t`Your hackathon team`} state={teams.isLoading ? { status: 'loading' }
    : teams.error ? { status: 'error', error: teams.error.message, onRetry: () => { void teams.refetch() } } : { status: 'ready' }}
    status={team ? <StatusBadge status={team.state} label={teamStateLabel(team.state)} /> : undefined}
    main={<div className="grid gap-5">
      {action.error ? <ErrorText message={commandErrorText(action.error)} /> : null}
      {!team ? <><AdmissionArtwork kind="teams" />
        {context.programme.team_mode === 'solo' ? <p className="text-sm text-ink">{t`Your one-person team appears after you confirm your place.`}</p>
          : <TeamEditor pending={action.isPending} onSave={body => send('', body)} />}</> : <>
        {team.eligibility_issue ? <p role="alert" className="rounded-xl border border-danger-line bg-panel p-3 text-sm text-danger">{t`A roster member is no longer eligible. Ask the event team to review this locked roster.`}</p> : null}
        <TeamRoster team={team} pending={action.isPending} onHandover={id => send('handover/', { new_leader_id: id })}
          onRemove={id => send('remove-member/', { member_id: id })} />
        {team.allowed_actions.includes('edit') ? <TeamEditor key={team.version} team={team} pending={action.isPending} onSave={body => send('', body, 'PATCH')} /> : null}
        <div className="flex flex-wrap gap-2">
          {team.allowed_actions.includes('invite') ? <button className="desk-button" type="button" disabled={action.isPending} onClick={() => action.mutate({
            suffix: '/teams/' + team.id + '/invite/', body: { expected_version: team.version, rotate: true } }, { onSuccess: value => {
              if (typeof value.token === 'string') setInvite(inviteUrl(team.id, value.token, Number(value.team_version)))
            } })}>{t`Create invitation link`}</button> : null}
          {team.allowed_actions.includes('invite') ? <button className="desk-button" type="button" disabled={action.isPending} onClick={() => action.mutate({ suffix: '/teams/' + team.id + '/invite/', body: { expected_version: team.version, revoke_only: true } }, { onSuccess: () => setInvite('') })}>{t`Revoke invitation links`}</button> : null}
          {team.allowed_actions.includes('lock') ? <button className="desk-button-primary" type="button" disabled={action.isPending}
            onClick={() => send('lock/')}>{team.team_mode === 'team_together' ? t`Seal and submit team application` : t`Lock roster`}</button> : null}
          {team.allowed_actions.includes('leave') ? <LeaveTeamButton team={team} pending={action.isPending}
            onLeave={cancel => send('leave/', cancel ? { cancel_registration: true } : {})} /> : null}
          {team.allowed_actions.includes('cancel') ? <button className="desk-button-danger-outline" type="button" disabled={action.isPending} onClick={() => send('cancel/', { reason_code: 'team_disbanded' })}>{t`Disband team`}</button> : null}
        </div>
        {invite ? <label className="grid gap-1 text-sm text-ink">{t`Private invitation link`}<input readOnly className="desk-input" value={invite} onFocus={e => e.target.select()} /></label> : null}
        {team.join_requests.length ? <section aria-label={t`Join requests`} className="grid gap-2"><h2 className="title-section">{t`Join requests`}</h2>{team.join_requests.map(request =>
          <div key={request.id} className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-line p-3 text-sm text-ink">
            <span>{request.profile?.display_name || t`Participant`}</span><span className="flex flex-wrap gap-2">
              <button className="desk-button" type="button" disabled={action.isPending}
                onClick={() => send('accept/', { request_id: request.id })}>{t`Accept join request`}</button>
              {team.allowed_actions.includes('decline') ? <button className="desk-button-danger-outline" type="button" disabled={action.isPending}
                onClick={() => send('decline-request/', { request_id: request.id })}>{t`Decline join request`}</button> : null}</span></div>)}</section> : null}
        <TeamComments base={context.routes.member_base} team={team} pending={action.isPending} onSend={(body, onDone) => send('comments/', { body }, 'POST', onDone)} />
      </>}
    </div>} />
}
