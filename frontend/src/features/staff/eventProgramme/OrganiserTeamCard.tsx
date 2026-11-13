import { plural, t } from "@lingui/core/macro";
import { useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { ArrowRightLeft, Pencil, Trash2 } from 'lucide-react';
import { ConfirmDialog, StatusPill } from '../../../components/ui';
import { toast } from '../../../components/ui/toastStore';
import { commandErrorText } from '../../events/programmeCommandErrors';
import { MoveMemberDialog, RenameTeamDialog } from './OrganiserTeamDialogs';
import { restoreTeam, useOrganiserTeamCommand, type OrganiserTeam } from './organiserTeamApi';

const UNDO_WINDOW_MS = 5 * 60 * 1000;
const stateLabel = (state: string) => ({ forming: t`Forming`, locked: t`Locked`, disbanded: t`Disbanded` } as Record<string, string>)[state] ?? state;

/** One team for the organiser; with `events.team_moderation` on: rename, move a member, delete (five-minute undo). */
export function OrganiserTeamCard({ eventId, team, teams, moderation }: { eventId: number; team: OrganiserTeam; teams: OrganiserTeam[]; moderation: boolean }) {
  const command = useOrganiserTeamCommand(eventId); const client = useQueryClient();
  const [dialog, setDialog] = useState<'rename' | 'move' | 'delete' | null>(null);
  const close = () => { command.reset(); setDialog(null); };
  const remove = () => command.mutate({ team, command: 'delete' }, { onSuccess: deleted => {
    setDialog(null);
    toast(t`${team.name} deleted. You can undo this for five minutes.`, { duration: UNDO_WINDOW_MS, undoKey: `event-team-${team.id}`,
      undo: () => restoreTeam(client, eventId, deleted).catch(error => { throw new Error(commandErrorText(error)); }) });
  } });
  const live = team.state !== 'disbanded';
  return <article className="grid gap-3 rounded-control border border-line bg-panel p-4">
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div className="grid gap-1"><h4 className="font-semibold text-ink">{team.name}</h4>
        <p className="text-sm text-muted">{plural(team.member_count, { one: '# member', other: '# members' })}</p></div>
      <StatusPill label={stateLabel(team.state)} tone={team.state === 'locked' ? 'success' : team.state === 'disbanded' ? 'neutral' : 'accent'} />
    </div>
    {team.eligibility_issue ? <p className="text-sm text-warn-ink">{t`Review this team's eligibility.`}</p> : null}
    {moderation && live ? <div className="flex flex-wrap gap-2">
      <button type="button" className="desk-button inline-flex min-h-11 items-center gap-2" onClick={() => setDialog('rename')}>
        <Pencil aria-hidden="true" className="size-4" />{t`Rename`}</button>
      {team.state === 'forming' ? <button type="button" className="desk-button inline-flex min-h-11 items-center gap-2" onClick={() => setDialog('move')}>
        <ArrowRightLeft aria-hidden="true" className="size-4" />{t`Move a member`}</button> : null}
      <button type="button" className="desk-button-danger-outline inline-flex min-h-11 items-center gap-2" onClick={() => setDialog('delete')}>
        <Trash2 aria-hidden="true" className="size-4" />{t`Delete team`}</button>
    </div> : null}
    {dialog === 'rename' ? <RenameTeamDialog team={team} pending={command.isPending} error={command.error} onCancel={close}
      onSave={name => command.mutate({ team, command: 'rename', body: { name } }, { onSuccess: () => { setDialog(null); toast(t`Team renamed to ${name}.`); } })} /> : null}
    {dialog === 'move' ? <MoveMemberDialog eventId={eventId} team={team} targets={teams} pending={command.isPending} error={command.error} onCancel={close}
      onMove={(memberId, target) => command.mutate({ team, command: 'move-member', body: { member_id: memberId, to_team_id: target.id } },
        { onSuccess: () => { setDialog(null); toast(t`Member moved to ${target.name}.`); } })} /> : null}
    <ConfirmDialog open={dialog === 'delete'} tone="danger" title={t`Delete ${team.name}?`} confirmLabel={t`Delete team`} pending={command.isPending}
      message={command.error ? commandErrorText(command.error) : t`Every member leaves the team and its invitation links stop working. You can undo this for five minutes. A team with a project submission cannot be deleted.`}
      onCancel={close} onConfirm={remove} />
  </article>;
}
