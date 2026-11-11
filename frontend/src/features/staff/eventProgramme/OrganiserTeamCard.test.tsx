import { afterEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { StructuredApiError, staffRequest } from '../../../lib/api';
import { ToastHost } from '../../../components/ui';
import { clearToasts } from '../../../components/ui/toastStore';
import { OrganiserTeamCard } from './OrganiserTeamCard';

vi.mock('../../../lib/api', async original => ({ ...(await original<typeof import('../../../lib/api')>()), staffRequest: vi.fn(), memberRequest: vi.fn() }));
vi.mock('./sessionScope', () => ({ sessionScope: () => ['actor-17'] }));
afterEach(() => { vi.clearAllMocks(); clearToasts(); });

const team = { id: 7, event_id: 42, name: 'Copper', state: 'forming', version: 4, member_count: 3, eligibility_issue: false };
function renderCard(moderation = true) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><OrganiserTeamCard eventId={42} team={team} teams={[team]} moderation={moderation} /><ToastHost /></QueryClientProvider>);
  return client;
}
const body = (suffix: string) => JSON.parse(String(vi.mocked(staffRequest).mock.calls.find(([path]) => String(path).endsWith(suffix))?.[1]?.body));
async function deleteTeam() {
  fireEvent.click(screen.getByRole('button', { name: 'Delete team' }));
  fireEvent.click(within(await screen.findByRole('dialog')).getByRole('button', { name: 'Delete team' }));
  return screen.findByText('Copper deleted. You can undo this for five minutes.');
}

describe('organiser team delete with undo (C6)', () => {
  it('deletes with the team version and restores from the toast with the deleted version', async () => {
    vi.mocked(staffRequest).mockImplementation(async (path) => (String(path).endsWith('/delete/')
      ? { ...team, state: 'disbanded', version: 5 } : { ...team, version: 6 }) as never);
    renderCard();
    await deleteTeam();
    expect(body('/teams/7/delete/')).toMatchObject({ expected_version: 4 });
    expect(body('/teams/7/delete/').operation_id).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Undo' }));
    expect(await screen.findByText('Action undone.')).toBeTruthy();
    expect(body('/teams/7/restore/')).toMatchObject({ expected_version: 5 });
  });

  it('says plainly when the five-minute window has passed', async () => {
    vi.mocked(staffRequest).mockImplementation(async (path) => {
      if (String(path).endsWith('/restore/')) throw new StructuredApiError(409, { code: 'undo_expired', detail: 'The undo window has passed.' });
      return { ...team, state: 'disbanded', version: 5 } as never;
    });
    renderCard();
    await deleteTeam();
    fireEvent.click(screen.getByRole('button', { name: 'Undo' }));
    await waitFor(() => expect(screen.getByText('Could not undo: The five-minute undo window has passed.')).toBeTruthy());
  });

  it('shows no moderation actions while events.team_moderation is off', () => {
    renderCard(false);
    expect(screen.queryByRole('button', { name: 'Delete team' })).toBeNull();
    expect(screen.queryByRole('button', { name: 'Rename' })).toBeNull();
  });
});
