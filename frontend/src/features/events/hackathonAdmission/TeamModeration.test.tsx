import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, within } from '@testing-library/react';
import { LeaveTeamButton, TeamRoster } from './TeamModeration';
import type { Team } from './types';

const team = { id: 4, event_id: 2, version: 3, state: 'forming', name: 'Makers', leader_member_id: 10, team_mode: 'teams',
  seeking_members: false, finder_intro: '', skills: [], eligibility_issue: false, roster_hash: '', join_requests: [],
  allowed_actions: ['leave', 'comment', 'edit', 'handover', 'remove_member', 'cancel_registration'],
  members: [{ id: 1, member_id: 10, joined_at: '', profile: { display_name: 'Lead' } }, { id: 2, member_id: 11, joined_at: '', profile: { display_name: 'Ravi' } }],
} as unknown as Team;

describe('member team moderation (C3/C4)', () => {
  it('lets the leader hand over and remove only after confirming', async () => {
    const handover = vi.fn(), remove = vi.fn();
    render(<TeamRoster team={team} pending={false} onHandover={handover} onRemove={remove} />);
    expect(screen.getAllByRole('button', { name: /Make leader/ })).toHaveLength(1);
    fireEvent.click(screen.getByRole('button', { name: 'Make leader…' }));
    fireEvent.click(within(await screen.findByRole('dialog')).getByRole('button', { name: 'Hand over' }));
    expect(handover).toHaveBeenCalledWith(11);
    fireEvent.click(screen.getByRole('button', { name: 'Remove…' }));
    fireEvent.click(within(await screen.findByRole('dialog')).getByRole('button', { name: 'Remove member' }));
    expect(remove).toHaveBeenCalledWith(11);
  });

  it('offers no leader actions without the server granting them', () => {
    render(<TeamRoster team={{ ...team, allowed_actions: ['leave', 'comment'] }} pending={false} onHandover={vi.fn()} onRemove={vi.fn()} />);
    expect(screen.queryByRole('button', { name: /Make leader/ })).toBeNull();
    expect(screen.queryByRole('button', { name: /Remove/ })).toBeNull();
  });

  it('leaves and, only when ticked, cancels the registration too', async () => {
    const leave = vi.fn();
    render(<LeaveTeamButton team={team} pending={false} onLeave={leave} />);
    fireEvent.click(screen.getByRole('button', { name: 'Leave team…' }));
    const dialog = await screen.findByRole('dialog');
    fireEvent.click(within(dialog).getByRole('checkbox', { name: /Also cancel my registration/ }));
    fireEvent.click(within(dialog).getByRole('button', { name: 'Leave and cancel my registration' }));
    expect(leave).toHaveBeenCalledWith(true);
  });

  it('leaves straight away when cancelling the registration is not offered', () => {
    const leave = vi.fn();
    render(<LeaveTeamButton team={{ ...team, allowed_actions: ['leave'] }} pending={false} onLeave={leave} />);
    fireEvent.click(screen.getByRole('button', { name: 'Leave team' }));
    expect(leave).toHaveBeenCalledWith(false);
  });
});
