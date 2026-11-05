import { useState } from 'react';
import { ErrorBlock, Field, StatusPill } from '../../../components/ui';
import type { OutcomeRead } from '../../../generated/api';
import { today, usePrizeOutcomes, type ResolveInput } from './hackmoneyApi';
import { METHODS } from './PrizeAwardForms';
import type { Scope } from './types';

const KINDS: Record<string, string> = {
  fulfilled: 'Handed over', sponsor_paid: 'Paid by sponsor', forfeited: 'Forfeited', recovery_opened: 'Owed back after disqualification',
  recovery_repaid: 'Repaid', recovery_waived: 'Recovery waived',
};

/** Prize outcomes that are not payouts; a recovery (G16) is closed as repaid (a ledger receipt) or waived. Never charges anyone. */
export function PrizeOutcomesPanel({ scope }: { scope: Scope }) {
  const { list, resolve } = usePrizeOutcomes(scope, true);
  const rows = list.data?.results ?? [];
  if (!list.isLoading && !rows.length && !list.error) return null;
  return <section className="grid gap-4" aria-label="Prize outcomes">
    <h3 className="title-section">Prize outcomes and recoveries</h3>
    <ErrorBlock error={list.error || resolve.error} />
    {rows.map(row => <OutcomeRow key={row.id} row={row} busy={resolve.isPending} onResolve={fields => resolve.mutate({ id: row.id, fields })} />)}
  </section>;
}

function OutcomeRow({ row, busy, onResolve }: { row: OutcomeRead; busy: boolean; onResolve: (fields: ResolveInput) => void }) {
  const [outcome, setOutcome] = useState<ResolveInput['outcome']>('repaid');
  const [method, setMethod] = useState('bank_transfer'); const [reference, setReference] = useState('');
  const [note, setNote] = useState(''); const [on, setOn] = useState(today());
  const open = row.allowed_actions.includes('resolve');
  const ready = on && (outcome === 'repaid' || note.trim());
  return <article className="grid gap-2 rounded-xl border border-line bg-panel p-4">
    <div className="flex flex-wrap items-center justify-between gap-2"><p className="font-semibold">Award {row.award_id} · {KINDS[row.kind] ?? row.kind}</p>
      <StatusPill label={open ? 'Open' : row.happened_on} tone={open ? 'danger' : 'neutral'} /></div>
    <p className="text-sm text-muted">{row.amount ? `${row.amount} ${row.currency.toUpperCase()} · ` : ''}{row.method ? `${row.method.replace('_', ' ')} · ` : ''}
      {row.reference ? `${row.reference} · ` : ''}{row.note}</p>
    {open ? <fieldset className="grid gap-3" disabled={busy}><legend className="font-semibold">Close this recovery</legend>
      <Field label="Outcome"><select className="desk-input min-h-11" value={outcome} onChange={e => setOutcome(e.target.value as ResolveInput['outcome'])}>
        <option value="repaid">The money came back</option><option value="waived">Not recovering it</option></select></Field>
      {outcome === 'repaid' ? <>
        <Field label="How it came back"><select className="desk-input min-h-11" value={method} onChange={e => setMethod(e.target.value)}>
          {METHODS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></Field>
        <Field label="Reference (optional)"><input className="desk-input min-h-11" maxLength={64} value={reference} onChange={e => setReference(e.target.value)} /></Field>
      </> : null}
      <Field label={outcome === 'waived' ? 'Why it is not being recovered' : 'Note (optional)'}>
        <input className="desk-input min-h-11" maxLength={300} value={note} onChange={e => setNote(e.target.value)} /></Field>
      <Field label="Date"><input className="desk-input min-h-11" type="date" value={on} onChange={e => setOn(e.target.value)} /></Field>
      <button type="button" className="desk-button-primary min-h-11 justify-self-start" disabled={!ready}
        onClick={() => onResolve({ outcome, note, happened_on: on, ...(outcome === 'repaid' ? { method, reference } : {}) })}>
        {outcome === 'repaid' ? 'Record repayment' : 'Waive recovery'}</button>
    </fieldset> : null}
  </article>;
}
