import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { SignatoriesPanel } from './SignatoriesPanel';
import { staffRequest } from '../../../lib/api';
import type { SignatoryState } from './signatoryApi';

vi.mock('../../../lib/api', async original => ({ ...await original<typeof import('../../../lib/api')>(), staffRequest: vi.fn() }));

const state = (over: Partial<SignatoryState> = {}): SignatoryState => ({
  approval_required: false,
  signatories: [{ id: 1, slot: 1, name: 'Dr Rao', title: 'Director', member_id: 5, member_name: 'Rao Account', signature_artwork_id: null, version: 1 }],
  designs: [], ...over });

function mount(initial: SignatoryState | Error) {
  vi.mocked(staffRequest).mockReset().mockImplementation(async (_path: string, options?: RequestInit) => {
    if (!options?.method || options.method === 'GET') {
      if (initial instanceof Error) throw initial;
      return initial as never;
    }
    return { ...state({ approval_required: true }) } as never;
  });
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><SignatoriesPanel eventId={42} /></QueryClientProvider>);
}
const open = () => { const d = document.querySelector('details')!; d.open = true; };

beforeEach(() => vi.clearAllMocks());

describe('SignatoriesPanel (EP-46)', () => {
  it('lists three slots, prefilling the saved signatory and its approving account', async () => {
    mount(state());
    open();
    expect(await screen.findByDisplayValue('Dr Rao')).toBeTruthy();
    expect(screen.getByText('Rao Account')).toBeTruthy();
    expect(document.querySelectorAll('fieldset')).toHaveLength(3);
    expect(vi.mocked(staffRequest)).toHaveBeenCalledWith('/admin/events/42/certificates/signatories/');
  });

  it('disables Save until a printed name is entered, then posts the slot payload', async () => {
    mount(state({ signatories: [] }));
    open();
    const save = await screen.findByRole('button', { name: 'Save signatory 2' });
    expect(save).toBeDisabled();
    const fieldset = save.closest('fieldset')!;
    const inputs = fieldset.querySelectorAll('input.desk-input[maxlength]');
    fireEvent.change(inputs[0], { target: { value: 'Ms Iyer' } });
    fireEvent.change(inputs[1], { target: { value: 'Chair' } });
    expect(save).toBeEnabled();
    fireEvent.click(save);
    await waitFor(() => expect(vi.mocked(staffRequest)).toHaveBeenCalledWith('/admin/events/42/certificates/signatories/', expect.objectContaining({ method: 'POST' })));
    const call = vi.mocked(staffRequest).mock.calls.find(([, o]) => o?.method === 'POST')!;
    expect(JSON.parse(String(call[1]?.body))).toEqual({ slot: 2, name: 'Ms Iyer', title: 'Chair', member_id: null, signature_artwork_id: null });
  });

  it('removes a saved signatory by slot with DELETE', async () => {
    mount(state());
    open();
    fireEvent.click(await screen.findByRole('button', { name: 'Remove' }));
    await waitFor(() => expect(vi.mocked(staffRequest)).toHaveBeenCalledWith('/admin/events/42/certificates/signatories/1/', { method: 'DELETE' }));
  });

  it('turns the approval policy on through its own endpoint and then shows per-design approval status', async () => {
    mount(state({ designs: [{ template_revision_id: 8, certificate_kind: '', released: false, slots: [{ slot: 1, signatory_id: 1, approved: true }, { slot: 2, signatory_id: 2, approved: false }] }] }));
    open();
    const toggle = await screen.findByRole('checkbox');
    expect(screen.queryByText('Approvals')).toBeNull();
    fireEvent.click(toggle);
    await waitFor(() => expect(vi.mocked(staffRequest)).toHaveBeenCalledWith('/admin/events/42/certificates/signatories/approval-policy/', { method: 'POST', body: JSON.stringify({ required: true }) }));
  });

  it('shows approved vs waiting slots when approval is required', async () => {
    mount(state({ approval_required: true, designs: [{ template_revision_id: 8, certificate_kind: '', released: false,
      slots: [{ slot: 1, signatory_id: 1, approved: true }, { slot: 2, signatory_id: 2, approved: false }] }] }));
    open();
    expect(await screen.findByText('Signatory 1: approved')).toBeTruthy();
    expect(screen.getByText('Signatory 2: waiting')).toBeTruthy();
    expect(screen.getByText(/revision 8/)).toBeTruthy();
    expect(screen.getByText(/Default design/)).toBeTruthy();
  });

  it('shows an alert when the signatory list fails to load', async () => {
    mount(new Error('Signatories are unavailable.'));
    open();
    expect((await screen.findByRole('alert')).textContent).toContain('Signatories are unavailable.');
  });
});
