import { describe, expect, it, vi, beforeEach } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { TeamPage } from './TeamPage';
import type { ProgrammeContext, Team } from './types';

const { mutate, state } = vi.hoisted(() => ({ mutate: vi.fn(), state: { team: null as unknown } }));
vi.mock('./useTeams', () => ({
  useTeams: () => ({ key: [], teams: { isLoading: false, error: null, data: { results: [state.team] }, refetch: vi.fn() },
    action: { mutate, isPending: false, error: null } }),
}));
vi.mock('./TeamComments', () => ({ TeamComments: () => null }));

const team = (actions: string[]) => ({ id: 4, event_id: 2, version: 7, state: 'forming', name: 'Makers', leader_member_id: 10,
  team_mode: 'individual_then_team', seeking_members: true, finder_intro: '', skills: [], eligibility_issue: false, roster_hash: '',
  allowed_actions: actions, members: [{ id: 1, member_id: 10, joined_at: '', profile: { display_name: 'Lead' } }],
  join_requests: [{ id: 21, profile: { display_name: 'Ravi' } }] }) as unknown as Team;
const context = { programme: { team_mode: 'individual_then_team' }, routes: { member_base: '/m' }, eligibility: { eligible: true },
  makerspace: { id: 1 }, event: { id: 2 } } as unknown as ProgrammeContext;
const page = () => render(<MemoryRouter><TeamPage context={context} accountId={3} inviteUrl={() => ''} /></MemoryRouter>);

beforeEach(() => mutate.mockReset());

describe('join requests', () => {
  it('lets the leader decline a request, sending the request id with the team version', () => {
    state.team = team(['leave', 'comment', 'accept', 'decline']);
    page();
    fireEvent.click(screen.getByRole('button', { name: 'Decline join request' }));
    expect(mutate).toHaveBeenCalledWith({ suffix: '/teams/4/decline-request/', body: { expected_version: 7, request_id: 21 }, method: 'POST' },
      expect.anything());
  });

  it('offers no decline when the server does not grant it', () => {
    state.team = team(['leave', 'comment']);
    page();
    expect(screen.queryByRole('button', { name: 'Decline join request' })).toBeNull();
  });

  it('shows the team state in words, not the raw code', () => {
    state.team = team(['leave']);
    page();
    expect(screen.getByText('Forming')).toBeInTheDocument();
  });
});
