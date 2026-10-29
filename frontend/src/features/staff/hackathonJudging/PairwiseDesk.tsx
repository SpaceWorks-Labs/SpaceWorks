import type { ReactNode } from 'react';
import { ErrorBlock } from '../../../components/ui';
import { usePairwise } from './pairwiseApi';
import { PairwiseJudge } from './PairwiseJudge';
import type { Scope } from './types';

/** Every open pairwise round for this judge. Hidden entirely when the space has the feature off. */
export function PairwiseDesk({ scope, renderAssets }: { scope: Scope; renderAssets: (ids: number[]) => ReactNode }) {
  const { rounds, act, denied } = usePairwise(scope, true);
  if (denied) return null;
  if (rounds.isError) return <ErrorBlock error={rounds.error} onRetry={() => void rounds.refetch()} />;
  const rows = rounds.data?.results ?? [];
  const active = rows.find(row => !row.finished)?.round_id;
  return rows.length ? <div className="grid gap-8">{rows.map(row => <PairwiseJudge key={row.round_id} state={row}
    pending={act.isPending} error={act.variables?.round === row.round_id ? act.error : null} renderAssets={renderAssets}
    shortcuts={row.round_id === active} onReload={() => { act.reset(); void rounds.refetch(); }}
    onCommand={(action, fields) => act.mutate({ round: row.round_id, action, version: row.version, fields })} />)}</div> : null;
}
