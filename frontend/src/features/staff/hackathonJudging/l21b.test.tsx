import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { previewQuery } from './l21bApi';
import { panelIds, RoundSettingsFields } from './RoundSettingsFields';
import { ScoreNextBar } from './ScoreNextBar';
import type { Assignment } from './types';

describe('L21b judging helpers', () => {
  it('builds the finalist preview query for top N and hand-picked selections', () => {
    expect(previewQuery({ source_round_id: 1, target_round_id: 2, selection: 'top_n', top_n: 5 }))
      .toBe('source_round_id=1&target_round_id=2&selection=top_n&top_n=5');
    expect(previewQuery({ source_round_id: 1, target_round_id: 2, selection: 'manual', snapshot_ids: [7, 9] }))
      .toBe('source_round_id=1&target_round_id=2&selection=manual&snapshot_ids=7%2C9');
  });
  it('keeps only positive whole panel IDs', () => {
    expect(panelIds('3, 4, x, -1, 5.5, 9')).toEqual([3, 4, 9]);
    expect(panelIds('')).toEqual([]);
  });
  it('labels every round setting for assistive technology', () => {
    const change = vi.fn();
    render(<RoundSettingsFields value={{ visibility: 'assigned', fresh_eyes: false, panel: '' }} onChange={change} />);
    expect(screen.getByLabelText('What judges see')).toBeTruthy();
    expect(screen.getByLabelText(/Fresh eyes/)).toBeTruthy();
    expect(screen.getByLabelText(/Judge panel/)).toBeTruthy();
  });
  it('offers Score next only for weighted rounds', () => {
    const client = new QueryClient();
    const row = (round_id: number, mode: string) => ({ id: round_id, round_id, mode } as unknown as Assignment);
    const scope = { makerspaceId: 1, eventId: 2, actorId: 3, context: 'person' };
    // ScoreNextBar now renders the opened project's editor itself (D12); the bar's offer is what is tested here.
    const renderEditor = () => null;
    const { rerender } = render(<QueryClientProvider client={client}><ScoreNextBar scope={scope} assignments={[row(4, 'top3')]} renderEditor={renderEditor} /></QueryClientProvider>);
    expect(screen.queryByRole('button', { name: /Score next project/ })).toBeNull();
    rerender(<QueryClientProvider client={client}><ScoreNextBar scope={scope} assignments={[row(4, 'weighted_1_5')]} renderEditor={renderEditor} /></QueryClientProvider>);
    expect(screen.getByRole('button', { name: 'Score next project' })).toBeTruthy();
  });
});
