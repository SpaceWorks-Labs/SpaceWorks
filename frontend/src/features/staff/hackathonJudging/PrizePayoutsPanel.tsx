import { useState } from 'react';
import { Banknote } from 'lucide-react';
import { EmptyState, ErrorBlock, Field, StatusPill } from '../../../components/ui';
import { usePrizePayouts } from './l21bApi';
import { PrizeAwardCard } from './PrizeAwardCard';
import type { PayoutRead, PrizePayableAwardRead } from '../../../generated/api';
import type { Scope } from './types';

/** Record prize payouts by hand (C-38). Each payout is a ledger expense of the GROSS prize; tax deducted
 * (#181) is recorded beside it. Mistakes are reversed, never edited. */
export function PrizePayoutsPanel({ scope, claims = false }: { scope: Scope; claims?: boolean }) {
  const { list, record, reverse } = usePrizePayouts(scope, true);
  const awards: PrizePayableAwardRead[] = list.data?.awards ?? [];
  return <section className="grid gap-4" aria-label="Prize payouts">
    <div className="flex items-start gap-3"><Banknote className="mt-1 text-accent" aria-hidden="true" /><div>
      <h3 className="title-section">Prize payouts</h3>
      <p className="text-sm text-muted">Record what you paid or handed to each winner. Nothing is paid automatically; every cash payout is an expense in the finance ledger.</p></div></div>
    <ErrorBlock error={list.error || record.error || reverse.error} />
    {awards.length ? <div className="grid gap-3">{awards.map(award =>
      <PrizeAwardCard key={award.id} scope={scope} award={award} claims={claims} recording={record.isPending}
        onRecord={fields => record.mutate(fields)} />)}</div>
      : <p className="text-sm text-muted" role="status">Payouts open once results are published.</p>}
    {!list.isLoading && !list.data?.count ? <EmptyState title="No payouts recorded" description="Recorded payouts and reversals appear here." /> : null}
    {list.data?.results.map(row => <PayoutRow key={row.id} row={row} busy={reverse.isPending}
      onReverse={reason => reverse.mutate({ id: row.id, reason })} />)}
  </section>;
}

function PayoutRow({ row, busy, onReverse }: { row: PayoutRead; busy: boolean; onReverse: (reason: string) => void }) {
  const [reason, setReason] = useState('');
  const money = row.currency.toUpperCase();
  const taxed = Number(row.tds_amount) > 0;
  return <article className="grid gap-2 rounded-xl border border-line bg-panel p-4">
    <div className="flex flex-wrap items-center justify-between gap-2"><p className="font-semibold">{row.prize_name}</p>
      <StatusPill label={row.kind === 'reversal' ? 'Reversal' : row.allowed_actions.includes('reverse') ? 'Paid' : 'Reversed'} /></div>
    <p className="text-sm">{taxed ? `Gross ${row.amount} · tax deducted ${row.tds_amount} · net ${row.net_amount} ${money}` : `${row.amount} ${money}`}
      {` · ${row.method.replace('_', ' ')} · ${row.paid_on}`}{row.reference ? ` · ${row.reference}` : ''}{row.recipient_id ? ` · member #${row.recipient_id}` : ''}</p>
    {row.allowed_actions.includes('reverse') ? <div className="flex flex-wrap items-end gap-2">
      <Field label="Reason for reversing"><input className="desk-input min-h-11" maxLength={300} value={reason} onChange={e => setReason(e.target.value)} /></Field>
      <button type="button" className="desk-button min-h-11" disabled={busy || !reason.trim()} onClick={() => onReverse(reason.trim())}>Reverse payout</button></div> : null}
  </article>;
}
