import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { SponsorConsole } from './SponsorConsole';

const request = vi.fn();
vi.mock('../../../lib/api', async importOriginal => ({
  ...(await importOriginal<typeof import('../../../lib/api')>()),
  staffRequest: (...args: unknown[]) => request(...args),
}));

const scope = { makerspaceId: 1, eventId: 2, actorId: 3, context: 'person' };
const project = {
  snapshot_id: 77, title: 'Solar kettle', description: 'Boils water with sun.', track_ids: [5], asset_ids: [11],
  resumes: [{ asset_id: 41, download_url: '/x' }], links: [{ kind: 'Demo', url: 'https://demo.example' }],
};
const data = (extra = {}) => ({ count: 1, next: null, previous: null, results: [project],
  prizes: [{ id: 9, version: 4, name: 'Sponsor prize' }], ...extra });

function mount(props: Partial<Parameters<typeof SponsorConsole>[0]> = {}) {
  const download = vi.fn().mockResolvedValue(undefined);
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <SponsorConsole scope={scope} sponsorId={6} sponsorName="Acme" renderProjectFiles={(id, ids) => <span>files {id}:{ids.join(',')}</span>}
      downloadResume={download} {...props} /></QueryClientProvider>);
  return { download };
}

beforeEach(() => { request.mockReset(); });

describe('SponsorConsole (EP-25)', () => {
  it('shows a loading state, then only the sponsor-scoped projects with consented résumés', async () => {
    request.mockResolvedValue(data());
    mount();
    expect(screen.getByRole('status', { name: 'Loading content' })).toBeTruthy();
    expect(await screen.findByText('Solar kettle')).toBeTruthy();
    expect(request).toHaveBeenCalledWith('/admin/events/2/sponsors/6/submissions/?page=1');
    expect(screen.getByText('files 77:11')).toBeTruthy();
    expect(screen.getByRole('button', { name: /Download consented recruiting résumé 41/ })).toBeTruthy();
    expect(screen.getByRole('link', { name: /Demo/ }).getAttribute('rel')).toBe('noopener noreferrer');
  });

  it('shows an error with retry when the sponsor list cannot load', async () => {
    request.mockRejectedValueOnce(new Error('Sponsor tracks unavailable.')).mockResolvedValueOnce(data());
    mount();
    expect(await screen.findByText(/Sponsor tracks unavailable/)).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: /retry|try again/i }));
    expect(await screen.findByText('Solar kettle')).toBeTruthy();
  });

  it('keeps Propose disabled until a prize is chosen, then proposes with that prize version and snapshot', async () => {
    request.mockResolvedValue(data());
    mount();
    const propose = await screen.findByRole('button', { name: 'Propose this project for your prize' });
    expect(propose).toBeDisabled();
    fireEvent.change(screen.getByRole('combobox'), { target: { value: '9' } });
    expect(propose).toBeEnabled();
    fireEvent.click(propose);
    await waitFor(() => expect(request.mock.calls.some(c => String(c[0]).endsWith('/sponsors/6/prizes/9/propose/'))).toBe(true));
    const call = request.mock.calls.find(c => String(c[0]).endsWith('/propose/'))!;
    expect(call[1].method).toBe('POST');
    const body = JSON.parse(call[1].body);
    expect(body).toMatchObject({ snapshot_id: 77, expected_version: 4 });
    expect(call[1].headers['Idempotency-Key']).toBe(body.operation_id);
  });

  it('surfaces a failed résumé download without crashing the list', async () => {
    request.mockResolvedValue(data());
    const download = vi.fn().mockRejectedValue(new Error('Consent withdrawn.'));
    mount({ downloadResume: download });
    fireEvent.click(await screen.findByRole('button', { name: /Download consented recruiting résumé 41/ }));
    await waitFor(() => expect(download).toHaveBeenCalledWith(41));
    expect(await screen.findByText(/Consent withdrawn/)).toBeTruthy();
    expect(screen.getByText('Solar kettle')).toBeTruthy();
  });
});
