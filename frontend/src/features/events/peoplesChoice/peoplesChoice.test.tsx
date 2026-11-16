import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { PeoplesChoiceAward } from './PeoplesChoiceAward';
import { PeoplesChoiceBanner, VoteButton, type PeoplesChoiceVoting } from './PeoplesChoiceVoting';
import { parsePublic } from './api';
import { fromLocalInput, toLocalInput } from '../../staff/hackathonJudging/PeoplesChoicePanel';

const ENTRY = '6f1c1d5e-1b7a-4a4f-9b5e-2d1c3b4a5f60';
const OTHER = '0a1b2c3d-4e5f-4a6b-8c7d-9e0f1a2b3c4d';
const open = { event_id: 4, state: 'open' as const, audience: 'members' as const, opens_at: null, closes_at: null, award: null };

function voting(overrides: Partial<PeoplesChoiceVoting> = {}): PeoplesChoiceVoting {
  return { pub: open, session: 'authenticated', setSession: vi.fn(), ballotError: null,
    ballot: { event_id: 4, state: 'open', audience: 'members', opens_at: null, closes_at: null, can_vote: true, refusal: null,
      entry_public_id: null, own_entry_public_ids: [OTHER], version: 0 },
    vote: { mutate: vi.fn(), isPending: false, error: null } as unknown as PeoplesChoiceVoting['vote'], ...overrides };
}

describe("People's choice (#181)", () => {
  it('parses the public block and refuses a malformed award', () => {
    expect(parsePublic(open).award).toBeNull();
    const published = parsePublic({ ...open, state: 'published', award: { prize_name: "People's choice", total_votes: 9,
      published_at: '2026-11-05T10:00:00Z', winners: [{ title: 'Rover', votes: 5, entry_public_id: ENTRY }] } });
    expect(published.award?.winners).toEqual([{ title: 'Rover', votes: 5, entry_public_id: ENTRY }]);
    expect(() => parsePublic({ ...open, state: 'tallying' })).toThrow();
    expect(() => parsePublic({ ...open, award: { prize_name: 'x', total_votes: 'many', winners: [] } })).toThrow();
  });
  it('shows a vote button, the chosen vote, and nothing on your own team', () => {
    const state = voting();
    const { rerender } = render(<VoteButton voting={state} entryId={ENTRY} title="Rover" />);
    screen.getByRole('button', { name: 'Vote for Rover' }).click();
    expect(state.vote.mutate).toHaveBeenCalledWith({ entry: ENTRY, version: 0 });
    rerender(<VoteButton voting={voting({ ballot: { ...state.ballot!, entry_public_id: ENTRY, version: 1 } })} entryId={ENTRY} title="Rover" />);
    expect(screen.getByRole('button', { name: 'Your vote for Rover' }).getAttribute('aria-pressed')).toBe('true');
    rerender(<VoteButton voting={state} entryId={OTHER} title="Ours" />);
    expect(screen.queryByRole('button')).toBeNull();
    expect(screen.getByText('Your team’s project')).toBeTruthy();
  });
  it('shows no vote control while voting is closed or for a refused voter', () => {
    const { container, rerender } = render(<VoteButton voting={voting({ pub: { ...open, state: 'closed' } })} entryId={ENTRY} title="Rover" />);
    expect(container.textContent).toBe('');
    rerender(<VoteButton voting={voting({ ballot: { ...voting().ballot!, can_vote: false, refusal: 'attendees_only' } })} entryId={ENTRY} title="Rover" />);
    expect((screen.getByRole('button') as HTMLButtonElement).disabled).toBe(true);
  });
  it('never shows a count before publication, and names the winners after', () => {
    render(<PeoplesChoiceBanner voting={voting()} slug="forge" />);
    expect(screen.getByText(/No counts are shown/)).toBeTruthy();
    expect(screen.queryByText(/votes? in all/)).toBeNull();
    render(<PeoplesChoiceAward award={{ prize_name: "People's choice", total_votes: 1, published_at: '2026-11-05T10:00:00Z',
      winners: [{ title: 'Rover', votes: 1, entry_public_id: ENTRY }] }} projectHref={id => `/p/${id}`} />);
    expect(screen.getByRole('link', { name: 'Rover' }).getAttribute('href')).toBe(`/p/${ENTRY}`);
    expect(screen.getByText(/1 vote in all/)).toBeTruthy();
  });
  it('round-trips the staff window through the local datetime input', () => {
    expect(toLocalInput(null)).toBe('');
    expect(fromLocalInput('')).toBeNull();
    const iso = '2026-11-05T10:30:00.000Z';
    expect(fromLocalInput(toLocalInput(iso))).toBe(iso);
  });
});
