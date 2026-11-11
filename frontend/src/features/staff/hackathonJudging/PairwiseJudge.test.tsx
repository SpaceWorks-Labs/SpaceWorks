import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { expectNoA11yViolations } from '../../../test/axe';
import { PairwiseJudge } from './PairwiseJudge';
import type { PairwiseState } from './types';

const card = (id: number, title: string) => ({ assignment_id: id, snapshot_id: id + 100, title, description: `${title} notes`, track_id: null, asset_ids: [] });
const comparing: PairwiseState = { round_id: 7, round_key: 'finals', event_id: 3, version: 4, guidance: 'Which solves the brief better?',
  previous: card(1, 'Solar kiln'), current: card(2, 'Rain sensor'), compared: 6, remaining: 5, finished: false,
  allowed_actions: ['compare', 'skip', 'recuse'] };

function setup(state: PairwiseState = comparing, extra: Partial<Parameters<typeof PairwiseJudge>[0]> = {}) {
  const onCommand = vi.fn();
  const view = render(<PairwiseJudge state={state} onCommand={onCommand} pending={false} error={null}
    renderAssets={() => null} onReload={() => {}} {...extra} />);
  return { onCommand, ...view };
}

describe('pairwise judge desk', () => {
  it('shows both projects side by side with progress announced politely', async () => {
    const { container } = setup();
    expect(screen.getByRole('article', { name: 'Before: Solar kiln' })).toBeVisible();
    expect(screen.getByRole('article', { name: 'Now: Rain sensor' })).toBeVisible();
    expect(screen.getByText('6 compared · 5 still to see')).toHaveAttribute('aria-live', 'polite');
    expect(screen.getByText('Which solves the brief better?')).toBeVisible();
    await expectNoA11yViolations(container);
  });
  it('answers with buttons or the 1 / 2 / S keys and sends the private notes', () => {
    const { onCommand } = setup();
    fireEvent.change(screen.getByRole('textbox', { name: /Private notes/ }), { target: { value: 'tidy wiring' } });
    fireEvent.click(screen.getByRole('button', { name: /Now is better/ }));
    expect(onCommand).toHaveBeenLastCalledWith('compare', { outcome: 'current', notes: 'tidy wiring' });
    fireEvent.keyDown(window, { key: '1' });
    expect(onCommand).toHaveBeenLastCalledWith('compare', { outcome: 'previous', notes: 'tidy wiring' });
    fireEvent.keyDown(window, { key: 's' });
    expect(onCommand).toHaveBeenLastCalledWith('skip', { notes: 'tidy wiring' });
    expect(onCommand).toHaveBeenCalledTimes(3);
  });
  it('ignores shortcuts while typing, with modifiers, when pending or when another desk owns them', () => {
    const { onCommand, rerender } = setup();
    fireEvent.keyDown(screen.getByRole('textbox', { name: /Private notes/ }), { key: '2' });
    fireEvent.keyDown(window, { key: '2', ctrlKey: true });
    rerender(<PairwiseJudge state={comparing} onCommand={onCommand} pending error={null} renderAssets={() => null} onReload={() => {}} />);
    fireEvent.keyDown(window, { key: '2' });
    rerender(<PairwiseJudge state={comparing} onCommand={onCommand} pending={false} error={null} renderAssets={() => null} onReload={() => {}} shortcuts={false} />);
    fireEvent.keyDown(window, { key: '2' });
    expect(onCommand).not.toHaveBeenCalled();
  });
  it('the first project is only viewed, then N loads the next one', () => {
    const { onCommand } = setup({ ...comparing, previous: null, allowed_actions: ['next', 'skip', 'recuse'] });
    expect(screen.queryByRole('button', { name: /better/ })).toBeNull();
    fireEvent.keyDown(window, { key: 'n' });
    expect(onCommand).toHaveBeenCalledWith('next', {});
  });
  it('recusal needs a reason and a stale cursor offers a reload', () => {
    const onReload = vi.fn();
    const { onCommand } = setup(comparing, { error: new Error('This item changed.'), onReload });
    const recuse = screen.getByRole('button', { name: 'Declare conflict and recuse' });
    expect(recuse).toBeDisabled();
    fireEvent.change(screen.getByRole('textbox', { name: 'Private reason' }), { target: { value: 'My cousin' } });
    fireEvent.click(recuse);
    expect(onCommand).toHaveBeenCalledWith('recuse', { reason: 'My cousin' });
    fireEvent.click(screen.getByRole('button', { name: 'Reload my place in this round' }));
    expect(onReload).toHaveBeenCalledOnce();
  });
  it('says when the judge has compared everything', () => {
    setup({ ...comparing, previous: null, current: null, remaining: 0, finished: true, allowed_actions: [] });
    expect(screen.getByText('You have compared every project available to you')).toBeVisible();
  });
});
