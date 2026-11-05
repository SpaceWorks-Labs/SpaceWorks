import { useState } from 'react';
import { Trophy } from 'lucide-react';
import { EmptyState, ErrorBlock } from '../../../components/ui';
import { useMyPrizes, type PrizeCommand, type PrizeScope } from './api';
import { PrizeCard } from './PrizeCard';

/** Member "My prizes" (hack-money G3/G4/G6/G7). Nothing here moves money: finance records every payout by hand. */
export function MyPrizes({ scope }: { scope: PrizeScope }) {
  const [page, setPage] = useState(1);
  const { list, send } = useMyPrizes(scope, page);
  const run = (command: PrizeCommand, done?: () => void) => send.mutate(command, { onSuccess: () => done?.() });
  const data = list.data;
  return <section className="grid gap-4" aria-labelledby="my-prizes-title">
    <div className="flex items-start gap-3"><Trophy className="mt-1 text-accent" aria-hidden="true" /><div>
      <h1 id="my-prizes-title" className="title-page">My prizes</h1>
      <p className="text-sm text-muted">Prizes you won in this space. Split a cash prize with your team, then tell the organisers where to pay you.</p>
    </div></div>
    <ErrorBlock error={list.error || send.error} onRetry={list.error ? () => void list.refetch() : undefined} />
    {list.isLoading ? <p role="status">Loading your prizes…</p> : null}
    {data && !data.count ? <EmptyState title="No prizes yet" description="Prizes appear here once results naming your team are published." /> : null}
    {data?.results.map(prize => <PrizeCard key={prize.award_id} prize={prize} makerspaceId={scope.makerspaceId}
      actorId={scope.actorId} pending={send.isPending} send={run} />)}
    {data && (data.next || data.previous) ? <nav className="flex gap-2" aria-label="Prize pages">
      <button type="button" className="desk-button min-h-11" disabled={!data.previous} onClick={() => setPage(value => value - 1)}>Previous</button>
      <button type="button" className="desk-button min-h-11" disabled={!data.next} onClick={() => setPage(value => value + 1)}>Next</button>
    </nav> : null}
  </section>;
}
