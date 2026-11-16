import { afterEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { staffRequest } from '../../../lib/api';
import { finishesProject, ScoreNextBar } from './ScoreNextBar';
import type { Assignment } from './types';

vi.mock('../../../lib/api', async original => ({ ...(await original<typeof import('../../../lib/api')>()), staffRequest: vi.fn() }));
afterEach(() => vi.clearAllMocks());

const scope = { makerspaceId: 1, eventId: 2, actorId: 3, context: 'person' };
const assignment = (id: number, title: string) => ({ id, round_id: 4, mode: 'weighted_1_5', title, version: 1 } as unknown as Assignment);

describe('Score next (D12)', () => {
  it('opens the next project and advances on its own until the judge is caught up', async () => {
    const queue = [{ assignment_id: 11, snapshot_id: 101, reason: 'fewest_reviews' }, { assignment_id: 12, snapshot_id: 102, reason: 'fewest_reviews' },
      { assignment_id: null, snapshot_id: null, reason: 'none' }];
    vi.mocked(staffRequest).mockImplementation(async (path) => {
      if (String(path).includes('/next-project/')) return queue.shift() as never;
      if (String(path).endsWith('/judge-assignments/11/')) return assignment(11, 'Rover') as never;
      if (String(path).endsWith('/judge-assignments/12/')) return assignment(12, 'Drone') as never;
      throw new Error(`unexpected ${String(path)}`);
    });
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(<QueryClientProvider client={client}><ScoreNextBar scope={scope} assignments={[assignment(11, 'Rover')]}
      renderEditor={(row, afterSubmit) => <button type="button" onClick={() => afterSubmit('score', { submit: true })}>{`Submit ${row.title}`}</button>} /></QueryClientProvider>);
    fireEvent.click(screen.getByRole('button', { name: 'Score next project' }));
    expect(await screen.findByRole('heading', { name: 'Now scoring: Rover' })).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Submit Rover' }));
    expect(await screen.findByRole('heading', { name: 'Now scoring: Drone' })).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Submit Drone' }));
    expect(await screen.findByText(/You're all caught up/)).toBeTruthy();
    expect(screen.queryByRole('heading', { name: /Now scoring/ })).toBeNull();
    expect(vi.mocked(staffRequest).mock.calls.filter(([path]) => String(path).includes('/next-project/'))).toHaveLength(3);
    client.clear();
  });

  it('keeps the project open after a private draft and advances after submit, recuse or skip', () => {
    expect(finishesProject('score', { submit: false })).toBe(false);
    expect(finishesProject('score', { submit: true })).toBe(true);
    expect(finishesProject('rank', {})).toBe(true);
    expect(finishesProject('recuse', { reason: 'Mentored them' })).toBe(true);
    expect(finishesProject('skip', { reason: 'Out of time' })).toBe(true);
  });
});
