import { ErrorBlock, StatusPill } from '../../../components/ui';
import type { DepositRow } from '../../../generated/api';
import { useDeposits } from './hackmoneyApi';
import { useProgrammeOptions } from './l21bApi';
import type { Scope } from './types';

const OUTCOMES: Record<DepositRow['outcome'], [string, 'success' | 'warn' | 'neutral']> = {
  return: ['Refund case', 'success'], void: ['Not owed', 'neutral'], keep: ['Kept (no-show)', 'warn'], none: ['Already decided', 'neutral'],
};

/** G10: preview and approve the one deposit settlement batch. Money still moves only through the refund-case queue. */
export function DepositsPanel({ scope }: { scope: Scope }) {
  const { summary, settle } = useDeposits(scope, true);
  const options = useProgrammeOptions(scope).query.data;
  if (summary.isLoading) return <p role="status">Loading deposits…</p>;
  if (!summary.data) return <ErrorBlock error={summary.error} onRetry={() => void summary.refetch()} />;
  const data = summary.data;
  const count = (kind: DepositRow['outcome']) => data.rows.filter(row => row.outcome === kind).length;
  const blocked = !data.event_ended || Boolean(data.settled_at) || !options || !data.amount;
  return <section className="grid gap-4" aria-label="Deposits">
    <h3 className="title-section">Refundable deposits</h3>
    <ErrorBlock error={settle.error} />
    <p className="text-sm text-muted">{data.settled_at
      ? `Settled on ${new Date(data.settled_at).toLocaleString()}. Returned deposits are refund cases in the refunds queue, where staff approve each one.`
      : `People who checked in${data.requires_submission ? ' and submitted a project' : ''} get a refund case; no-shows keep the charge. Approving opens the refund cases only — each refund is still approved in the refunds queue.`}</p>
    <p className="text-sm">{count('return')} to return · {count('void')} not owed · {count('keep')} kept · {count('none')} already decided</p>
    {data.rows.length ? <ul className="grid gap-2" aria-label="Deposits to settle">{data.rows.map(row =>
      <li key={row.payment_id} className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-line p-3 text-sm">
        <span>Member #{row.member_id ?? '—'} · {row.amount} {row.currency.toUpperCase()} · {row.payment_status.replace('_', ' ')}</span>
        <StatusPill label={OUTCOMES[row.outcome][0]} tone={OUTCOMES[row.outcome][1]} /></li>)}</ul>
      : <p className="text-sm text-muted">No deposits were charged.</p>}
    {!data.event_ended && !data.settled_at ? <p className="text-sm text-muted" role="status">Settle deposits after the event ends.</p> : null}
    <button type="button" className="desk-button-primary min-h-11 justify-self-start" disabled={blocked || settle.isPending}
      onClick={() => options && settle.mutate(options.version)}>Approve settlement</button>
  </section>;
}
