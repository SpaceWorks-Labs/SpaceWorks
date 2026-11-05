import { useState } from 'react';
import { Field } from '../../../components/ui';
import type { PrizePayableAwardRead, PrizeShareRow } from '../../../generated/api';
import { proposedTds, today, type FulfilInput, type ShareInput } from './hackmoneyApi';

export const METHODS = [['bank_transfer', 'Bank transfer'], ['upi', 'UPI'], ['cash', 'Cash'], ['cheque', 'Cheque'], ['card', 'Card'], ['online', 'Online'], ['other', 'Other']] as const;

/** A cash payout: to the leader by default, or to one confirmed share; TDS is proposed by the space (#181, record only). */
export function PayoutForm({ award, recipients, busy, onSubmit }: { award: PrizePayableAwardRead; recipients: PrizeShareRow[]; busy: boolean;
  onSubmit: (fields: Record<string, unknown>) => void }) {
  const [recipient, setRecipient] = useState(recipients[0]?.member_id ?? 0);
  const share = recipients.find(row => row.member_id === recipient);
  const [amount, setAmount] = useState(''); const [tds, setTds] = useState<string | null>(null);
  const [method, setMethod] = useState('bank_transfer'); const [reference, setReference] = useState(''); const [paidOn, setPaidOn] = useState(today());
  const gross = amount.trim() || share?.amount || award.amount_per_winner || '';
  const tax = tds ?? proposedTds(gross, award.tax_proposal);
  const needsRecipient = award.shares.length > 0;
  const submit = () => onSubmit({ method, reference, paid_on: paidOn, ...(needsRecipient ? { recipient_id: recipient } : {}),
    ...(amount.trim() ? { amount: amount.trim() } : {}), ...(tax.trim() ? { tds_amount: tax.trim() } : {}) });
  return <fieldset className="grid gap-3 rounded-xl border border-line p-3" disabled={busy}>
    <legend className="px-1 font-semibold">Record a payout</legend>
    {needsRecipient ? <Field label="Winner" hint={recipients.length ? undefined : 'No confirmed share is waiting to be paid.'}>
      <select className="desk-input min-h-11" value={recipient} onChange={e => { setRecipient(Number(e.target.value)); setTds(null); }}>
        {recipients.map(row => <option key={row.id} value={row.member_id ?? 0}>Member #{row.member_id} · {row.amount}</option>)}</select></Field> : null}
    <Field label="Gross amount paid" hint={`Leave empty to use ${share ? 'the share' : 'the prize amount'}${gross ? ` (${gross})` : ''}.`}>
      <input className="desk-input min-h-11" inputMode="decimal" value={amount} onChange={e => { setAmount(e.target.value); setTds(null); }} /></Field>
    <Field label="Tax deducted (TDS)" hint={award.tax_proposal.enabled
      ? `Proposed at ${award.tax_proposal.rate}% above ${award.tax_proposal.threshold}. You deduct and file it outside SpaceWorks; enter 0 for none.`
      : 'Leave empty unless you deducted tax.'}>
      <input className="desk-input min-h-11" inputMode="decimal" value={tax} onChange={e => setTds(e.target.value)} /></Field>
    <Field label="Method"><select className="desk-input min-h-11" value={method} onChange={e => setMethod(e.target.value)}>
      {METHODS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></Field>
    <Field label="Reference (optional)"><input className="desk-input min-h-11" maxLength={64} value={reference} onChange={e => setReference(e.target.value)} /></Field>
    <Field label="Paid on"><input className="desk-input min-h-11" type="date" value={paidOn} onChange={e => setPaidOn(e.target.value)} /></Field>
    <button type="button" className="desk-button-primary min-h-11 justify-self-start" disabled={!paidOn || (needsRecipient && !recipient)} onClick={submit}>Record payout</button>
  </fieldset>;
}

/** A non-cash prize handed over or shipped, or a prize the sponsor paid directly. Never a ledger entry. */
export function FulfilForm({ sponsor, busy, onSubmit }: { sponsor: boolean; busy: boolean; onSubmit: (fields: FulfilInput) => void }) {
  const [method, setMethod] = useState<FulfilInput['method']>(sponsor ? 'sponsor_paid' : 'handed_over');
  const [reference, setReference] = useState(''); const [note, setNote] = useState(''); const [on, setOn] = useState(today());
  return <fieldset className="grid gap-3 rounded-xl border border-line p-3" disabled={busy}>
    <legend className="px-1 font-semibold">{sponsor ? 'Record that the sponsor paid' : 'Record handed over'}</legend>
    <Field label="How"><select className="desk-input min-h-11" value={method} onChange={e => setMethod(e.target.value as FulfilInput['method'])}>
      <option value="handed_over">Handed over</option><option value="shipped">Shipped</option>
      <option value="sponsor_paid">Paid by the sponsor</option><option value="other">Other</option></select></Field>
    <Field label="Tracking number or sponsor reference (optional)"><input className="desk-input min-h-11" maxLength={64} value={reference} onChange={e => setReference(e.target.value)} /></Field>
    <Field label="Note (optional)"><input className="desk-input min-h-11" maxLength={300} value={note} onChange={e => setNote(e.target.value)} /></Field>
    <Field label="Date"><input className="desk-input min-h-11" type="date" value={on} onChange={e => setOn(e.target.value)} /></Field>
    <button type="button" className="desk-button-primary min-h-11 justify-self-start" disabled={!on}
      onClick={() => onSubmit({ method, reference, note, happened_on: on })}>{sponsor ? 'Record sponsor paid' : 'Record handed over'}</button>
  </fieldset>;
}

/** After the claim window: forfeit the whole prize or one unpaid share. The server refuses while the window is open. */
export function ForfeitForm({ shares, busy, onSubmit }: { shares: PrizeShareRow[]; busy: boolean; onSubmit: (note: string, shareId?: number) => void }) {
  const [note, setNote] = useState(''); const [share, setShare] = useState(0);
  return <details className="rounded-xl border border-line p-3"><summary className="min-h-11 cursor-pointer font-semibold">Forfeit an unclaimed prize</summary>
    <fieldset className="mt-2 grid gap-3" disabled={busy}>
      <p className="text-sm text-muted">Only after the claim window closes. Nothing was paid, so nothing reaches the ledger.</p>
      {shares.length ? <Field label="What to forfeit"><select className="desk-input min-h-11" value={share} onChange={e => setShare(Number(e.target.value))}>
        <option value={0}>The whole prize</option>{shares.map(row => <option key={row.id} value={row.id}>Share of member #{row.member_id}</option>)}</select></Field> : null}
      <Field label="Reason"><input className="desk-input min-h-11" maxLength={300} value={note} onChange={e => setNote(e.target.value)} /></Field>
      <button type="button" className="desk-button min-h-11 justify-self-start" disabled={!note.trim()}
        onClick={() => onSubmit(note.trim(), share || undefined)}>Forfeit</button>
    </fieldset></details>;
}

type Row = { member: string; amount: string };

/** Staff record a split the team agreed in person: every share is confirmed at once (G3). */
export function SplitEditor({ total, busy, onSubmit }: { total: string | null; busy: boolean; onSubmit: (shares: ShareInput[]) => void }) {
  const [rows, setRows] = useState<Row[]>([{ member: '', amount: '' }]);
  const set = (index: number, patch: Partial<Row>) => setRows(value => value.map((row, at) => (at === index ? { ...row, ...patch } : row)));
  const shares = rows.map(row => ({ member_id: Number(row.member), amount: row.amount.trim() }));
  const valid = shares.every(row => Number.isInteger(row.member_id) && row.member_id > 0 && Number(row.amount) > 0);
  const sum = shares.reduce((acc, row) => acc + (Number(row.amount) || 0), 0);
  const over = total !== null && sum > Number(total);
  return <details className="rounded-xl border border-line p-3"><summary className="min-h-11 cursor-pointer font-semibold">Record a split the team agreed</summary>
    <fieldset className="mt-2 grid gap-3" disabled={busy}>
      {rows.map((row, index) => <div key={index} className="flex flex-wrap items-end gap-2">
        <Field label={`Member ID ${index + 1}`}><input className="desk-input min-h-11" inputMode="numeric" value={row.member} onChange={e => set(index, { member: e.target.value })} /></Field>
        <Field label={`Amount ${index + 1}`}><input className="desk-input min-h-11" inputMode="decimal" value={row.amount} onChange={e => set(index, { amount: e.target.value })} /></Field>
        {rows.length > 1 ? <button type="button" className="desk-button min-h-11" onClick={() => setRows(value => value.filter((_, at) => at !== index))}>Remove</button> : null}
      </div>)}
      {over ? <p className="text-sm text-danger" role="alert">The shares add up to more than the prize ({total}).</p> : null}
      <div className="flex flex-wrap gap-2">
        <button type="button" className="desk-button min-h-11" onClick={() => setRows(value => [...value, { member: '', amount: '' }])}>Add member</button>
        <button type="button" className="desk-button-primary min-h-11" disabled={!valid || over} onClick={() => onSubmit(shares)}>Save split</button></div>
    </fieldset></details>;
}
