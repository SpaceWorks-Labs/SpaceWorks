import { useRef } from 'react';
import { useMutation, useQuery, useQueryClient, type QueryClient } from '@tanstack/react-query';
import { staffRequest } from '../../../lib/api';
import { CommandSession } from '../../events/hackathonAdmission/transport';
import { sessionScope } from './sessionScope';

export type OrganiserTeam = { id: number; event_id: number; name: string; state: string; version: number; member_count: number;
  eligibility_issue: boolean; roster_hash?: string; allowed_actions?: string[] };
export type OrganiserTeamMember = { member_id: number; is_leader: boolean; display_name: string };
export type OrganiserTeamCommand = 'rename' | 'move-member' | 'delete' | 'restore';

/** C6 organiser moderation: rename, move a member, delete and restore (`events.team_moderation`). */
export function useOrganiserTeamCommand(eventId: number) {
  const session = useRef(new CommandSession()); const client = useQueryClient();
  return useMutation({ retry: false,
    mutationFn: ({ team, command, body = {} }: { team: Pick<OrganiserTeam, 'id' | 'version'>; command: OrganiserTeamCommand; body?: Record<string, unknown> }) =>
      session.current.send<OrganiserTeam>(`/api/v1/admin/events/${eventId}/teams/${team.id}/${command}/`, 'POST',
        { expected_version: team.version, ...body }, true),
    onSuccess: () => client.invalidateQueries({ queryKey: ['programme-teams', eventId] }) });
}

/** The undo of a delete. Plain function, not a hook: the toast outlives the card that deleted the team. */
export async function restoreTeam(client: QueryClient, eventId: number, team: Pick<OrganiserTeam, 'id' | 'version'>) {
  const restored = await new CommandSession().send<OrganiserTeam>(`/api/v1/admin/events/${eventId}/teams/${team.id}/restore/`, 'POST',
    { expected_version: team.version }, true);
  await client.invalidateQueries({ queryKey: ['programme-teams', eventId] });
  return restored;
}

/** The active roster of one team, read when the organiser opens "Move a member". */
export function useOrganiserTeamMembers(eventId: number, teamId: number | null) {
  return useQuery({ queryKey: ['programme-teams', eventId, 'detail', teamId, ...sessionScope()], enabled: teamId !== null, gcTime: 0, retry: false,
    queryFn: () => staffRequest<OrganiserTeam & { members?: OrganiserTeamMember[] }>(`/admin/events/${eventId}/teams/${teamId}/`) });
}
