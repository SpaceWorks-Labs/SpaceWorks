import { useState } from 'react';
import { ErrorBlock, Field } from '../../../components/ui';
import { proposedTds } from './hackmoneyApi';
import { usePeoplesChoicePayouts } from './peoplesChoiceApi';
import type { Scope } from './types';

const METHODS = [['bank_transfer', 'Bank transfer'], ['upi', 'UPI'], ['cash', 'Cash'], ['cheque', 'Cheque'], ['card', 'Card'], ['online', 'Online'], ['other', 'Other']] as const;

/** Record a People's choice prize payout by hand, like a judged prize: one ledger expense of the GROSS prize, with the
 * space's tax proposal (#181, record only); reverse it under Prize payouts. */
export function PeoplesChoicePayouts({ scope }: { scope: Scope }) {
  const { winners, record } = usePeoplesChoicePayouts(scope);
  const rows = winners.data?.winners ?? [];
  const [standing, setStanding] = useState(0); const [amount, setAmount] = useState(''); const [method, setMethod] = useState('bank_transfer');
  const [tds, setTds] = useState<string | null>(null);
  const [reference, setReference] = useState(''); const [paidOn, setPaidOn] = useState(new Date().toISOString().slice(0, 10));
  const picked = rows.find(row => row.id === standing);
  const proposal = picked?.tax_proposal ?? rows[0]?.tax_proposal;
  const tax = tds ?? proposedTds(amount.trim() || picked?.amount_per_winner || '', proposal);
  return <section className="grid gap-3" aria-label="People's choice prize payout">
    <h4 className="font-semibold">Prize payout</h4>
    <ErrorBlock error={winners.error || record.error} />
    {rows.length && rows.every(row => row.paid) ? <p className="text-sm text-muted" role="status">Every People’s choice winner has a recorded payout. See Prize payouts to reverse one.</p> : null}
    {rows.some(row => !row.paid) ? <fieldset className="grid gap-3 rounded-xl border border-line p-4" disabled={record.isPending}>
      <legend className="px-1 font-semibold">Record a payout</legend>
      <Field label="Winner"><select className="desk-input min-h-11" value={standing} onChange={e => { setStanding(Number(e.target.value)); setTds(null); }}>
        <option value={0}>Choose a winner</option>{rows.filter(row => !row.paid).map(row => <option key={row.id} value={row.id}>{row.prize_name} · {row.title}</option>)}</select></Field>
      <Field label="Gross amount paid" hint={`Leave empty to use the prize amount${picked?.amount_per_winner ? ` (${picked.amount_per_winner})` : ''}.`}>
        <input className="desk-input min-h-11" inputMode="decimal" value={amount} onChange={e => { setAmount(e.target.value); setTds(null); }} /></Field>
      <Field label="Tax deducted (TDS)" hint={proposal?.enabled
        ? `Proposed at ${proposal.rate}% above ${proposal.threshold}. You deduct and file it outside SpaceWorks; enter 0 for none.`
        : 'Leave empty unless you deducted tax.'}>
        <input className="desk-input min-h-11" inputMode="decimal" value={tax} onChange={e => setTds(e.target.value)} /></Field>
      <Field label="Method"><select className="desk-input min-h-11" value={method} onChange={e => setMethod(e.target.value)}>
        {METHODS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></Field>
      <Field label="Reference (optional)"><input className="desk-input min-h-11" maxLength={64} value={reference} onChange={e => setReference(e.target.value)} /></Field>
      <Field label="Paid on"><input className="desk-input min-h-11" type="date" value={paidOn} onChange={e => setPaidOn(e.target.value)} /></Field>
      <button type="button" className="desk-button-primary min-h-11 justify-self-start" disabled={!standing || !paidOn}
        onClick={() => record.mutate({ standing_id: standing, method, reference, paid_on: paidOn, ...(amount.trim() ? { amount: amount.trim() } : {}),
          ...(tax.trim() ? { tds_amount: tax.trim() } : {}) },
          { onSuccess: () => { setStanding(0); setAmount(''); setTds(null); setReference(''); } })}>Record payout</button>
    </fieldset> : null}
  </section>;
}
