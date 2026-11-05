import { useState } from 'react';
import { ErrorBlock } from '../../../components/ui';
import { useNextProject } from './l21bApi';
import type { Assignment, Scope } from './types';

/** "Score next project": a judge's started project, else the eligible one with the fewest reviews. */
export function ScoreNextBar({ scope, assignments }: { scope: Scope; assignments: Assignment[] }) {
  const next = useNextProject(scope); const [message, setMessage] = useState('');
  const rounds = [...new Set(assignments.filter(row => row.mode === 'weighted_1_5').map(row => row.round_id))];
  if (!rounds.length) return null;
  return <div className="grid gap-2">
    <div className="flex flex-wrap gap-2">{rounds.map(roundId => <button key={roundId} type="button" className="desk-button-primary min-h-11"
      disabled={next.isPending} onClick={() => next.mutate({ roundId, version: 0 }, { onSuccess: result => setMessage(
        result.assignment_id ? `Next up: project ${result.snapshot_id}${result.reason === 'started' ? ', which you already started.' : '.'}` : 'Nothing left to score in this round.') })}>
      Score next project{rounds.length > 1 ? ` (round ${roundId})` : ''}</button>)}</div>
    <p role="status" className="text-sm text-muted">{message}</p>
    <ErrorBlock error={next.error} />
  </div>;
}
