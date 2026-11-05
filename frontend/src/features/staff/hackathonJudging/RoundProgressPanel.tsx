import { useState } from 'react';
import { ErrorBlock, Field } from '../../../components/ui';
import { useRoundProgress } from './l21bApi';
import type { Round, Scope } from './types';

const RULE = { two_sd: 'over 2 SD from the project mean', spread_25: 'over 25 points from another judge' } as const;

/** Live judging progress for one round: below-target projects, judge completion, outliers, stale drafts. */
export function RoundProgressPanel({ scope, rounds }: { scope: Scope; rounds: Round[] }) {
  const live = rounds.filter(round => round.state !== 'draft');
  const [roundId, setRoundId] = useState(live[0]?.id ?? 0);
  const query = useRoundProgress(scope, roundId);
  const data = query.data;
  return <section className="grid gap-4" aria-label="Judging progress">
    <h3 className="title-section">Judging progress</h3>
    {!live.length ? <p className="text-sm text-muted">Progress appears once a round is open.</p> : <Field label="Round">
      <select className="desk-input min-h-11" value={roundId} onChange={e => setRoundId(Number(e.target.value))}>
        {live.map(round => <option key={round.id} value={round.id}>{round.key}</option>)}</select></Field>}
    {query.isLoading ? <p role="status">Loading progress…</p> : null}
    <ErrorBlock error={query.error} onRetry={() => void query.refetch()} />
    {data ? <div className="grid gap-5">
      <div><h4 className="font-semibold">Below the review target ({data.target})</h4>
        {data.below_target.length ? <ul className="grid gap-1 text-sm">{data.below_target.map(row =>
          <li key={row.snapshot_id}>{row.title}: {row.reviews} of {row.target} reviews</li>)}</ul>
          : <p className="text-sm text-muted">Every project has reached the target.</p>}</div>
      <div className="overflow-x-auto"><table className="w-full text-left text-sm"><caption className="sr-only">Per-judge completion</caption>
        <thead><tr><th scope="col">Judge</th><th scope="col">Submitted</th><th scope="col">Assigned</th><th scope="col">Recused or skipped</th><th scope="col">Done</th></tr></thead>
        <tbody>{data.judges.map(row => <tr key={row.judge_role_assignment_id}><th scope="row">{row.name || `Judge ${row.judge_role_assignment_id}`}</th>
          <td>{row.submitted}</td><td>{row.assigned}</td><td>{row.withdrawn}</td><td>{row.completion}%</td></tr>)}</tbody></table></div>
      <div><h4 className="font-semibold">Scores to check</h4>
        {data.outliers.length ? <ul className="grid gap-1 text-sm">{data.outliers.map((row, index) =>
          <li key={index}>Project {row.snapshot_id}: judge {row.judge_role_assignment_id} scored {row.score} (mean {row.project_mean}), {RULE[row.rule]}</li>)}</ul>
          : <p className="text-sm text-muted">No outlier scores.</p>}</div>
      <div><h4 className="font-semibold">Drafts saved but not submitted for over a day</h4>
        {data.stale_drafts.length ? <ul className="grid gap-1 text-sm">{data.stale_drafts.map(row =>
          <li key={row.assignment_id}>Judge {row.judge_role_assignment_id}, project {row.snapshot_id}, saved {new Date(row.saved_at).toLocaleString()}</li>)}</ul>
          : <p className="text-sm text-muted">No stale drafts.</p>}</div>
    </div> : null}
  </section>;
}
