import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';
import { proposedTds } from './hackmoneyApi';
import { PrizeAwardCard } from './PrizeAwardCard';
import { PrizeClaimsPanel } from './PrizeClaimsPanel';
import { DepositsPanel } from './DepositsPanel';
import { PrizePoolPanel } from './PrizePoolPanel';
import { TeamChargesPanel } from './TeamChargesPanel';
import type { PrizePayableAwardRead } from '../../../generated/api';

const request = vi.fn();
vi.mock('../../../lib/api', () => ({ staffRequest: (...args: unknown[]) => request(...args) }));

const scope = { makerspaceId: 1, eventId: 2, actorId: 3, context: 'person' };
const wrap = (node: ReactNode) => render(<QueryClientProvider client={new QueryClient()}>{node}</QueryClientProvider>);
const page = <T,>(results: T[]) => ({ count: results.length, next: null, previous: null, results });
const award = (overrides: Partial<PrizePayableAwardRead> = {}): PrizePayableAwardRead => ({
  id: 9, prize_name: 'Best build', rank: 1, title: 'Robot', amount_per_winner: '20000.00', paid: false, kind: 'cash',
  funding: 'space', value_text: '', status: 'owed', open_recoveries: 0,
  tax_proposal: { enabled: true, rate: '30.00', threshold: '10000.00' }, shares: [], ...overrides });

beforeEach(() => { request.mockReset(); });

describe('hack-money staff helpers', () => {
  it('proposes TDS only when on and above the threshold (#181, record only)', () => {
    const proposal = { enabled: true, rate: '30.00', threshold: '10000.00' };
    expect(proposedTds('20000', proposal, 'inr')).toBe('6000.00');
    expect(proposedTds('10000', proposal, 'inr')).toBe('');
    expect(proposedTds('20000', { ...proposal, enabled: false }, 'inr')).toBe('');
    expect(proposedTds('', proposal, 'inr')).toBe('');
  });
  it('rounds the proposal at the currency minor unit with decimal maths, never a float', () => {
    const proposal = { enabled: true, rate: '10.00', threshold: '0.00' };
    expect(proposedTds('1234.567', proposal, 'kwd')).toBe('123.457');  // 3 places
    expect(proposedTds('1234.55', proposal, 'jpy')).toBe('123');       // 0 places, half-up
    expect(proposedTds('0.29', { ...proposal, rate: '10.00' }, 'usd')).toBe('0.03'); // 0.029 -> 0.03
    expect(proposedTds('20000.10', { enabled: true, rate: '7.55', threshold: '100.00' }, 'inr')).toBe('1510.01');
  });
});

describe('PrizeAwardCard', () => {
  it('prefills the proposed tax on a cash prize and records gross plus TDS', () => {
    const record = vi.fn();
    wrap(<PrizeAwardCard scope={scope} award={award()} claims recording={false} currency="inr" onRecord={record} />);
    expect((screen.getByLabelText('Tax deducted (TDS)') as HTMLInputElement).value).toBe('6000.00');
    // A payout needs a reference: the button stays off until one is typed.
    expect((screen.getByRole('button', { name: 'Record payout' }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.change(screen.getByLabelText(/^Reference/), { target: { value: ' UTR123 ' } });
    fireEvent.click(screen.getByRole('button', { name: 'Record payout' }));
    expect(record).toHaveBeenCalledWith(expect.objectContaining({ award_id: 9, tds_amount: '6000.00', reference: 'UTR123' }));
  });
  it('offers fulfilment instead of a payout for a non-cash or sponsor-paid prize', () => {
    wrap(<PrizeAwardCard scope={scope} award={award({ kind: 'item', value_text: 'Pi kit' })} claims recording={false} onRecord={vi.fn()} />);
    expect(screen.queryByRole('button', { name: 'Record payout' })).toBeNull();
    expect(screen.getByRole('button', { name: 'Record handed over' })).toBeTruthy();
    wrap(<PrizeAwardCard scope={scope} award={award({ funding: 'sponsor_direct' })} claims recording={false} onRecord={vi.fn()} />);
    expect(screen.getByRole('button', { name: 'Record sponsor paid' })).toBeTruthy();
  });
  it('shows no actions once a prize is settled', () => {
    wrap(<PrizeAwardCard scope={scope} award={award({ status: 'paid', paid: true })} claims recording={false} onRecord={vi.fn()} />);
    expect(screen.getByText('Paid')).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Record payout' })).toBeNull();
  });
});

describe('PrizeClaimsPanel', () => {
  it('lists masked claims and shows a reveal only after the audited request', async () => {
    request.mockImplementation((url: string) => {
      if (url.endsWith('prize-claims/')) return Promise.resolve(page([{ share_id: 5, version: 2, state: 'submitted', country: 'IN',
        method: 'upi', masked_details: 'UPI ••••@bank', pan_masked: '••••••234F', verified: false, award_id: 9, member_id: 7,
        amount: '10000.00', share_state: 'confirmed' }]));
      return Promise.resolve({ share_id: 5, country: 'IN', method: 'upi', details: { upi_id: 'win@bank' }, pan: 'ABCDE1234F' });
    });
    wrap(<PrizeClaimsPanel scope={scope} />);
    expect(await screen.findByText(/UPI ••••@bank/)).toBeTruthy();
    expect(screen.queryByText('ABCDE1234F')).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'Reveal to pay' }));
    expect(await screen.findByText('ABCDE1234F')).toBeTruthy();
    const body = JSON.parse((request.mock.calls.at(-1) ?? [])[1].body);
    expect(body).toMatchObject({ reason_code: 'pay_winner', expected_version: 2 });
  });
});

describe('DepositsPanel', () => {
  it('keeps settlement disabled before the event ends', async () => {
    request.mockImplementation((url: string) => url.endsWith('deposits/')
      ? Promise.resolve({ event_id: 2, amount: '500.00', requires_submission: false, settled_at: null, event_ended: false,
        rows: [{ payment_id: 1, registration_id: 3, member_id: 4, amount: '500.00', currency: 'inr', payment_status: 'paid_online', outcome: 'return' }] })
      : Promise.resolve({ version: 3 }));
    wrap(<DepositsPanel scope={scope} />);
    expect(await screen.findByText('Refund case')).toBeTruthy();
    expect((screen.getByRole('button', { name: 'Approve settlement' }) as HTMLButtonElement).disabled).toBe(true);
  });
});

describe('PrizePoolPanel and TeamChargesPanel', () => {
  it('shows the pool totals', async () => {
    request.mockResolvedValue({ currency: 'inr', announced_total: '50000.00', sponsor_funded: '30000.00', paid_gross: '20000.00',
      tds_recorded: '6000.00', owed: '30000.00', recovered: '0.00', sponsor_direct_awards: 1 });
    wrap(<PrizePoolPanel scope={scope} />);
    expect(await screen.findByText(/50,000.00/)).toBeTruthy();
    expect(screen.getByText(/1 award paid directly by sponsors/)).toBeTruthy();
  });
  it('raises a missing team charge on request', async () => {
    request.mockImplementation((url: string) => url.endsWith('missing/')
      ? Promise.resolve(page([{ team_id: 8, team_name: 'Bots', leader_id: 4, amount: '1000.00', currency: 'inr' }]))
      : Promise.resolve({ team_id: 8, payment_id: 1, status: 'pending', amount: '1000.00', currency: 'inr' }));
    wrap(<TeamChargesPanel scope={scope} />);
    fireEvent.click(await screen.findByRole('button', { name: 'Raise charge now' }));
    await waitFor(() => expect(request.mock.calls.some(([url]) => String(url).endsWith('team-charges/8/raise/'))).toBe(true));
  });
});
