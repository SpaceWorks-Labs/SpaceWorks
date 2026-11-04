import { useState } from 'react';
import { Banknote } from 'lucide-react';
import { EmptyState, ErrorBlock, Field, StatusPill } from '../../../components/ui';
import { usePrizePayouts } from './l21bApi';
import type { PrizePayableAwardRead } from '../../../generated/api';
import type { Scope } from './types';

const METHODS = [['bank_transfer', 'Bank transfer'], ['upi', 'UPI'], ['cash', 'Cash'], ['cheque', 'Cheque'], ['card', 'Card'], ['online', 'Online'], ['other', 'Other']] as const;

/** Record prize payouts by hand (C-38). Each payout is a ledger expense; mistakes are reversed, never edited. */
export function PrizePayoutsPanel({ scope }: { scope: Scope }) {
  const { list, record, reverse } = usePrizePayouts(scope, true);
  const awards: PrizePayableAwardRead[] = list.data?.awards ?? [];
  const [award, setAward] = useState(0); const [amount, setAmount] = useState(''); const [method, setMethod] = useState('bank_transfer');
  const [reference, setReference] = useState(''); const [paidOn, setPaidOn] = useState(new Date().toISOString().slice(0, 10));
  const [reasons, setReasons] = useState<Record<number, string>>({});
  const busy = record.isPending || reverse.isPending;
  const submit = () => record.mutate({ award_id: award, method, reference, paid_on: paidOn, ...(amount.trim() ? { amount: amount.trim() } : {}) },
    { onSuccess: () => { setAward(0); setAmount(''); setReference(''); } });
  return <section className="grid gap-4" aria-label="Prize payouts">
    <div className="flex items-start gap-3"><Banknote className="mt-1 text-accent" aria-hidden="true" /><div>
      <h3 className="title-section">Prize payouts</h3>
      <p className="text-sm text-muted">Record what you paid each winner. Nothing is paid automatically; every payout is an expense in the finance ledger.</p></div></div>
    <ErrorBlock error={list.error || record.error || reverse.error} />
    {awards.length ? <fieldset className="grid gap-3 rounded-xl border border-line p-4" disabled={busy}>
      <legend className="px-1 font-semibold">Record a payout</legend>
      <Field label="Award"><select className="desk-input min-h-11" value={award} onChange={e => setAward(Number(e.target.value))}>
        <option value={0}>Choose a winner</option>{awards.filter(row => !row.paid).map(row =>
          <option key={row.id} value={row.id}>{row.prize_name} · rank {row.rank} · {row.title}</option>)}</select></Field>
      <Field label="Amount paid" hint={`Leave empty to use the prize amount${awards.find(row => row.id === award)?.amount_per_winner ? ` (${awards.find(row => row.id === award)?.amount_per_winner})` : ''}.`}>
        <input className="desk-input min-h-11" inputMode="decimal" value={amount} onChange={e => setAmount(e.target.value)} /></Field>
      <Field label="Method"><select className="desk-input min-h-11" value={method} onChange={e => setMethod(e.target.value)}>
        {METHODS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></Field>
      <Field label="Reference (optional)"><input className="desk-input min-h-11" maxLength={64} value={reference} onChange={e => setReference(e.target.value)} /></Field>
      <Field label="Paid on"><input className="desk-input min-h-11" type="date" value={paidOn} onChange={e => setPaidOn(e.target.value)} /></Field>
      <button type="button" className="desk-button-primary min-h-11 justify-self-start" disabled={!award || !paidOn} onClick={submit}>Record payout</button>
    </fieldset> : <p className="text-sm text-muted" role="status">Payouts open once results are published.</p>}
    {!list.isLoading && !list.data?.count ? <EmptyState title="No payouts recorded" description="Recorded payouts and reversals appear here." /> : null}
    {list.data?.results.map(row => <article key={row.id} className="grid gap-2 rounded-xl border border-line bg-panel p-4">
      <div className="flex flex-wrap items-center justify-between gap-2"><p className="font-semibold">{row.prize_name}</p>
        <StatusPill label={row.kind === 'reversal' ? 'Reversal' : row.allowed_actions.includes('reverse') ? 'Paid' : 'Reversed'} /></div>
      <p className="text-sm">{row.amount} {row.currency.toUpperCase()} · {row.method.replace('_', ' ')} · {row.paid_on}{row.reference ? ` · ${row.reference}` : ''}</p>
      {row.allowed_actions.includes('reverse') ? <div className="flex flex-wrap items-end gap-2"><Field label="Reason for reversing"><input className="desk-input min-h-11" maxLength={300} value={reasons[row.id] ?? ''} onChange={e => setReasons(value => ({ ...value, [row.id]: e.target.value }))} /></Field>
        <button type="button" className="desk-button min-h-11" disabled={busy || !(reasons[row.id] ?? '').trim()} onClick={() => reverse.mutate({ id: row.id, reason: (reasons[row.id] ?? '').trim() })}>Reverse payout</button></div> : null}
    </article>)}
  </section>;
}
