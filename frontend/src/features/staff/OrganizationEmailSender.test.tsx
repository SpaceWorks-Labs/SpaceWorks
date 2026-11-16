import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { OrganizationEmailSender } from './OrganizationEmailSender';
import { staffRequest } from '../../lib/api';

vi.mock('../../lib/api', async original => ({ ...await original<typeof import('../../lib/api')>(), staffRequest: vi.fn() }));

const client = () => new QueryClient({ defaultOptions: { queries: { retry: false } } });
const mount = (qc = client()) => render(<QueryClientProvider client={qc}><OrganizationEmailSender organizationId={12} /></QueryClientProvider>);
beforeEach(() => { vi.mocked(staffRequest).mockReset(); });

describe('OrganizationEmailSender (OR-11)', () => {
  it('renders nothing until the sender loads, and nothing when the load fails', async () => {
    vi.mocked(staffRequest).mockImplementation(async () => { throw new Error('forbidden') });
    const qc = client();
    const { container } = mount(qc);
    await waitFor(() => expect(qc.getQueryState(['organization-email-sender', 12])?.status).toBe('error'));
    expect(staffRequest).toHaveBeenCalledWith('/admin/organizations/12/email-sender/');
    expect(container.textContent).toBe('');
  });

  it('prefills the saved sender and PUTs the edited name and reply-to', async () => {
    vi.mocked(staffRequest).mockImplementation(async (_p: string, o?: RequestInit) =>
      (o?.method === 'PUT' ? { ...JSON.parse(String(o.body)), updated_at: 'now' } : { sender_name: 'Robotics Club', reply_to: 'club@example.org', updated_at: null }) as never);
    mount();
    const name = await screen.findByLabelText('Sender name') as HTMLInputElement;
    expect(name.value).toBe('Robotics Club');
    expect((screen.getByLabelText('Reply-to email') as HTMLInputElement).value).toBe('club@example.org');
    fireEvent.change(name, { target: { value: 'Robo Team' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save sender' }));
    await waitFor(() => expect(staffRequest).toHaveBeenCalledWith('/admin/organizations/12/email-sender/',
      { method: 'PUT', body: JSON.stringify({ sender_name: 'Robo Team', reply_to: 'club@example.org' }) }));
    expect(await screen.findByText('Sender saved.')).toBeTruthy();
  });

  it('shows the server error and no success note when the save is refused', async () => {
    vi.mocked(staffRequest).mockImplementation(async (_p: string, o?: RequestInit) => {
      if (o?.method === 'PUT') throw new Error('Co-host senders are off for this space.');
      return { sender_name: '', reply_to: '', updated_at: null } as never;
    });
    mount();
    fireEvent.click(await screen.findByRole('button', { name: 'Save sender' }));
    expect((await screen.findByRole('alert')).textContent).toContain('Co-host senders are off');
    expect(screen.queryByText('Sender saved.')).toBeNull();
  });
});
