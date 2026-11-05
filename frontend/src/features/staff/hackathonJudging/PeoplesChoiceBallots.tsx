import { useState } from 'react';
import { EmptyState, ErrorBlock, Field, Pagination, StatusPill } from '../../../components/ui';
import { usePeoplesChoiceBallots } from './peoplesChoiceApi';
import type { Scope } from './types';

/** Who voted, to spot throwaway or duplicate accounts. Never which project each person chose. */
export function PeoplesChoiceBallots({ scope }: { scope: Scope }) {
  const [page, setPage] = useState(1);
  const { list, voidBallot } = usePeoplesChoiceBallots(scope, page);
  const [reasons, setReasons] = useState<Record<string, string>>({});
  return <section className="grid gap-3" aria-label="People's choice ballots">
    <h4 className="font-semibold">Ballots</h4>
    <p className="text-sm text-muted">A voided ballot stops counting, and that person cannot vote again. Ballots are final once you publish.</p>
    <ErrorBlock error={list.error || voidBallot.error} />
    {!list.isLoading && !list.data?.count ? <EmptyState title="No ballots yet" description="Ballots appear here as members vote." /> : null}
    <ul className="grid gap-2">{list.data?.results.map(row => <li key={row.handle} className="grid gap-2 rounded-xl border border-line bg-panel p-3">
      <div className="flex flex-wrap items-center justify-between gap-2"><p className="font-medium">{row.voter_name}</p>
        <div className="flex flex-wrap gap-2">{row.attended ? <StatusPill label="Checked in" tone="success" /> : null}
          {row.changed ? <StatusPill label="Changed their vote" /> : null}{row.voided ? <StatusPill label="Voided" tone="danger" /> : null}</div></div>
      {row.voided && row.void_reason ? <p className="text-sm text-muted">Reason: {row.void_reason}</p> : null}
      {row.allowed_actions.includes('void') ? <div className="flex flex-wrap items-end gap-2">
        <Field label="Reason for voiding"><input className="desk-input min-h-11" maxLength={300} value={reasons[row.handle] ?? ''}
          onChange={e => setReasons(value => ({ ...value, [row.handle]: e.target.value }))} /></Field>
        <button type="button" className="desk-button min-h-11" disabled={voidBallot.isPending || !(reasons[row.handle] ?? '').trim()}
          onClick={() => voidBallot.mutate({ handle: row.handle, version: row.version, reason: (reasons[row.handle] ?? '').trim() })}>Void ballot</button></div> : null}
    </li>)}</ul>
    {list.data ? <Pagination page={page} totalPages={Math.max(1, Math.ceil(list.data.count / 24))} pageSize={24} count={list.data.count} onChange={setPage} /> : null}
  </section>;
}
