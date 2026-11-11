import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { expectNoA11yViolations } from '../../../test/axe';
import type { MyPrizeRead, PublicPrizeRead } from '../../../generated/api';
import { MyPrizes } from './MyPrizes';
import { PublicPrizes } from './PublicPrizes';

const { mutate, prizes } = vi.hoisted(() => ({ mutate: vi.fn(), prizes: { rows: [] as unknown[] } }));
vi.mock('./api', async original => ({
  ...(await original<typeof import('./api')>()),
  useMyPrizes: () => ({ list: { data: { count: prizes.rows.length, next: null, previous: null, results: prizes.rows }, isLoading: false },
    send: { mutate, isPending: false, error: null } }),
  useLeaderTeam: () => ({ isLoading: false, error: null, data: { members: [
    { id: 1, member_id: 17, joined_at: '', profile: { display_name: 'Ada' } },
    { id: 2, member_id: 18, joined_at: '', profile: { display_name: 'Lin' } }] } }),
}));

const template = { country: 'IN', method: 'upi', template_key: 'in_upi', template_version: 1, routing_document_required: false,
  fields: [{ key: 'holder_name', required: true, label: 'Account holder name', help: '' }, { key: 'upi_id', required: true, label: 'UPI ID', help: '' }] };
const prize = (patch: Partial<MyPrizeRead> = {}): MyPrizeRead => ({
  award_id: 5, event_id: 42, event_title: 'Build Weekend', prize_name: 'Best build', rank: 1, kind: 'cash', value_text: '',
  status: 'owed', my_share: null, my_payout: null, claim: null, claim_deadline: null, is_leader: true,
  allowed_actions: ['propose_split', 'claim'], tax_id_requested: false, payee_templates: [template], ...patch,
});
const scope = { makerspaceId: 9, actorId: 17 };

describe('My prizes', () => {
  it('lets the leader claim with the space template and never asks for a PAN when tax is off', async () => {
    prizes.rows = [prize()];
    const { container } = render(<MyPrizes scope={scope} />);
    fireEvent.click(screen.getByRole('button', { name: 'Claim this prize' }));
    expect(screen.queryByLabelText(/PAN/)).toBeNull();
    fireEvent.change(screen.getByLabelText('Account holder name'), { target: { value: 'Ada Lovelace' } });
    fireEvent.change(screen.getByLabelText('UPI ID'), { target: { value: 'ada@upi' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save payee details' }));
    expect(mutate).toHaveBeenLastCalledWith(expect.objectContaining({ eventId: 42, suffix: 'prize-awards/5/claim/', version: 0,
      fields: { country: 'IN', method: 'upi', details: { holder_name: 'Ada Lovelace', upi_id: 'ada@upi' } } }), expect.anything());
    await expectNoA11yViolations(container);
  });

  it('asks for an optional PAN only when the space records prize tax, and rejects a malformed one', () => {
    prizes.rows = [prize({ tax_id_requested: true })];
    render(<MyPrizes scope={scope} />);
    fireEvent.click(screen.getByRole('button', { name: 'Claim this prize' }));
    fireEvent.change(screen.getByLabelText('Account holder name'), { target: { value: 'Ada' } });
    fireEvent.change(screen.getByLabelText('UPI ID'), { target: { value: 'ada@upi' } });
    fireEvent.change(screen.getByLabelText(/PAN/), { target: { value: 'abc' } });
    expect(screen.getByRole('button', { name: 'Save payee details' })).toBeDisabled();
    fireEvent.change(screen.getByLabelText(/PAN/), { target: { value: 'abcde1234f' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save payee details' }));
    expect(mutate).toHaveBeenLastCalledWith(expect.objectContaining({ fields: expect.objectContaining({ pan: 'ABCDE1234F' }) }), expect.anything());
  });

  it('proposes a split between named team members', () => {
    prizes.rows = [prize()];
    render(<MyPrizes scope={scope} />);
    fireEvent.click(screen.getByRole('button', { name: 'Split with my team' }));
    fireEvent.change(screen.getByLabelText('Ada'), { target: { value: '100' } });
    fireEvent.change(screen.getByLabelText('Lin'), { target: { value: '150.50' } });
    fireEvent.click(screen.getByRole('button', { name: 'Propose split' }));
    expect(mutate).toHaveBeenLastCalledWith(expect.objectContaining({ suffix: 'prize-awards/5/split/', version: 0,
      fields: { shares: [{ member_id: 17, amount: '100' }, { member_id: 18, amount: '150.50' }] } }), expect.anything());
  });

  it('confirms a proposed share with its version and shows a paid payout as gross, tax and net', () => {
    prizes.rows = [prize({ is_leader: false, allowed_actions: ['confirm_share', 'decline_share'],
      my_share: { id: 8, award_id: 5, member_id: 17, amount: '100.00', state: 'proposed', version: 3, confirmed_at: null } }),
      prize({ award_id: 6, status: 'paid', allowed_actions: [],
        my_payout: { gross: '15000.00', tds: '4500.00', net: '10500.00', currency: 'inr', paid_on: '2026-11-05' } })];
    render(<MyPrizes scope={scope} />);
    fireEvent.click(screen.getByRole('button', { name: 'Confirm my share' }));
    expect(mutate).toHaveBeenLastCalledWith(expect.objectContaining({ suffix: 'prize-shares/8/confirm/', version: 3 }), expect.anything());
    expect(screen.getByText('₹4,500.00')).toBeInTheDocument();
    expect(screen.getByText('₹10,500.00')).toBeInTheDocument();
  });

  it('shows only masked claim details', () => {
    prizes.rows = [prize({ allowed_actions: ['claim', 'remove_claim'], claim: { share_id: 8, version: 2, state: 'submitted', country: 'IN',
      method: 'upi', masked_details: 'ada••••', pan_masked: '••••••234F', verified: false } })];
    render(<MyPrizes scope={scope} />);
    expect(screen.getByText(/PAN ••••••234F/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Remove my payee details' }));
    expect(mutate).toHaveBeenLastCalledWith(expect.objectContaining({ suffix: 'prize-awards/5/claim/remove/' }), expect.anything());
  });
});

describe('public prizes', () => {
  it('renders nothing when the organiser keeps prizes private', () => {
    const { container } = render(<PublicPrizes rows={[]} />);
    expect(container).toBeEmptyDOMElement();
  });
  it('lists cash amounts per winner and non-cash values', () => {
    const rows: PublicPrizeRead[] = [
      { name: 'Grand prize', track: '', sponsor: 'Acme', kind: 'cash', value_text: '', amount_per_winner: '50000.00', award_count: 1, currency: 'inr' },
      { name: 'Hardware', track: 'IoT', sponsor: '', kind: 'item', value_text: 'Pi 5 kit', amount_per_winner: null, award_count: 3, currency: 'inr' }];
    render(<PublicPrizes rows={rows} />);
    expect(screen.getByText(/₹50,000.00 per winner/)).toBeInTheDocument();
    expect(screen.getByText(/Item: Pi 5 kit · 3 winners/)).toBeInTheDocument();
  });
});
