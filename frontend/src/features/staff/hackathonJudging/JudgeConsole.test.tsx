import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import fixtures from '../../events/hackathonGallery/domain-fixtures.test.json';
import { expectNoA11yViolations } from '../../../test/axe';
import { JudgeAssignmentEditor } from './JudgeConsole';
import type { Assignment } from './types';

const assignment = fixtures.assignment as Assignment;
describe('judge’s private assignment editor', () => {
  it('requires a score before submission and keeps a partial draft separate', async () => {
    const submit = vi.fn(); const { container } = render(<JudgeAssignmentEditor assignment={assignment} pending={false} error={null} onSubmit={submit} renderAssets={() => null} />);
    expect(screen.getByRole('button', { name: 'Submit judgment' })).toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: 'Save private draft' }));
    expect(submit).toHaveBeenCalledWith('score', { scores: {}, notes: '', team_feedback: '', submit: false });
    fireEvent.change(screen.getByRole('combobox', { name: /Build quality/ }), { target: { value: '4' } });
    fireEvent.click(screen.getByRole('button', { name: 'Submit judgment' }));
    expect(submit).toHaveBeenLastCalledWith('score', { scores: { build: 4 }, notes: '', team_feedback: '', submit: true });
    await expectNoA11yViolations(container);
  });
  it('keeps feedback for the team separate from private notes (S4)', () => {
    const submit = vi.fn(); render(<JudgeAssignmentEditor assignment={assignment} pending={false} error={null} onSubmit={submit} renderAssets={() => null} />);
    expect(screen.getByText(/Never shown to the team/)).toBeTruthy();
    expect(screen.getByText(/only if the organisers share this round/)).toBeTruthy();
    fireEvent.change(screen.getByRole('textbox', { name: 'Private notes' }), { target: { value: 'Shaky wiring' } });
    fireEvent.change(screen.getByRole('textbox', { name: 'Feedback for the team' }), { target: { value: 'Great demo; tidy the wiring.' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save private draft' }));
    expect(submit).toHaveBeenCalledWith('score', { scores: {}, notes: 'Shaky wiring', team_feedback: 'Great demo; tidy the wiring.', submit: false });
  });
  it('keeps draft input after a stale conflict and exposes a reasoned recusal', () => {
    const submit = vi.fn(); const { rerender } = render(<JudgeAssignmentEditor assignment={assignment} pending={false} error={null} onSubmit={submit} renderAssets={() => null} />);
    fireEvent.change(screen.getByRole('textbox', { name: 'Private notes' }), { target: { value: 'Draft retained' } });
    rerender(<JudgeAssignmentEditor assignment={assignment} pending={false} error={new Error('This item changed.')} onSubmit={submit} renderAssets={() => null} />);
    expect(screen.getByRole('textbox', { name: 'Private notes' })).toHaveValue('Draft retained');
    expect(screen.getByRole('button', { name: 'Declare conflict and recuse' })).toBeDisabled();
    fireEvent.change(screen.getByRole('textbox', { name: 'Private reason' }), { target: { value: 'Mentored this team' } });
    fireEvent.click(screen.getByRole('button', { name: 'Declare conflict and recuse' }));
    expect(submit).toHaveBeenCalledWith('recuse', { reason: 'Mentored this team' });
  });
  it('requires distinct ranked projects, including an entire smaller batch', () => {
    const submit = vi.fn();
    render(<JudgeAssignmentEditor assignment={{ ...assignment, mode: 'top3', allowed_actions: ['rank'] }} pending={false} error={null} onSubmit={submit} renderAssets={() => null} />);
    fireEvent.change(screen.getByRole('combobox', { name: 'Rank 1' }), { target: { value: '101' } });
    fireEvent.change(screen.getByRole('combobox', { name: 'Rank 2' }), { target: { value: '101' } });
    expect(screen.getByRole('button', { name: 'Submit top-three ballot' })).toBeDisabled();
    fireEvent.change(screen.getByRole('combobox', { name: 'Rank 2' }), { target: { value: '102' } });
    fireEvent.click(screen.getByRole('button', { name: 'Submit top-three ballot' }));
    expect(submit).toHaveBeenCalledWith('rank', { ordered_top3: [101, 102] });
  });
});
