import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { CertificateApprovals } from './CertificateApprovals';
import { memberRequest, memberRequestBlob } from '../../../lib/api';

vi.mock('../../../lib/api', async original => ({ ...await original<typeof import('../../../lib/api')>(), memberRequest: vi.fn(), memberRequestBlob: vi.fn() }));

const row = (over = {}) => ({ signatory_id: 3, slot: 1, event_id: 42, event_title: 'Maker Fair', template_revision_id: 8,
  certificate_kind: '', approved: false, name: 'Dr Rao', title: 'Director', ...over });
const mount = () => render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><CertificateApprovals makerspaceId={7} /></QueryClientProvider>);

beforeEach(() => { vi.mocked(memberRequest).mockReset(); vi.mocked(memberRequestBlob).mockReset();
  URL.createObjectURL = vi.fn(() => 'blob:preview'); URL.revokeObjectURL = vi.fn(); });
afterEach(() => vi.restoreAllMocks());

describe('CertificateApprovals screen (EP-46)', () => {
  it('renders nothing when the member has no designs to approve', async () => {
    vi.mocked(memberRequest).mockResolvedValue([] as never);
    const { container } = mount();
    await waitFor(() => expect(memberRequest).toHaveBeenCalledWith('/member/makerspaces/7/certificate-approvals/'));
    expect(container.textContent).toBe('');
  });

  it('renders nothing (and no crash) when the lookup fails', async () => {
    vi.mocked(memberRequest).mockRejectedValue(new Error('nope'));
    const { container } = mount();
    await waitFor(() => expect(memberRequest).toHaveBeenCalled());
    expect(container.textContent).toBe('');
  });

  it('lists pending designs and approves with the signatory and revision ids', async () => {
    vi.mocked(memberRequest).mockImplementation(async (_p: string, o?: RequestInit) => (o?.method === 'POST' ? {} : [row()]) as never);
    mount();
    expect(await screen.findByText('Maker Fair')).toBeTruthy();
    expect(screen.getByText(/signing as Dr Rao, Director/)).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Approve' }));
    await waitFor(() => expect(memberRequest).toHaveBeenCalledWith('/member/makerspaces/7/certificate-approvals/3/approve/',
      { method: 'POST', body: JSON.stringify({ template_revision_id: 8 }) }));
  });

  it('shows Approved instead of an Approve button once approved', async () => {
    vi.mocked(memberRequest).mockResolvedValue([row({ approved: true })] as never);
    mount();
    expect(await screen.findByText('Approved')).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Approve' })).toBeNull();
  });

  it('opens the design PDF preview from the member preview path and closes it', async () => {
    vi.mocked(memberRequest).mockResolvedValue([row()] as never);
    vi.mocked(memberRequestBlob).mockResolvedValue(new Blob(['x']) as never);
    mount();
    fireEvent.click(await screen.findByRole('button', { name: 'Review design' }));
    expect(await screen.findByTitle('Certificate design for Maker Fair')).toBeTruthy();
    expect(memberRequestBlob).toHaveBeenCalledWith('/member/makerspaces/7/certificate-approvals/3/designs/8/preview.pdf');
    fireEvent.click(screen.getByRole('button', { name: 'Close the design' }));
    expect(screen.queryByTitle('Certificate design for Maker Fair')).toBeNull();
  });

  it('shows the approval error in an alert', async () => {
    vi.mocked(memberRequest).mockImplementation(async (_p: string, o?: RequestInit) => { if (o?.method === 'POST') throw new Error('Design changed; review again.'); return [row()] as never; });
    mount();
    fireEvent.click(await screen.findByRole('button', { name: 'Approve' }));
    expect((await screen.findByRole('alert')).textContent).toContain('Design changed');
  });
});
