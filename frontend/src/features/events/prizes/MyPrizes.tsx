import { t } from "@lingui/core/macro";
import { useState } from 'react';
import { Trophy } from 'lucide-react';
import { EmptyState, ErrorBlock } from '../../../components/ui';
import { useMyPrizes, type PrizeCommand, type PrizeScope } from './api';
import { PrizeCard } from './PrizeCard';
import { PagePager } from "../../../components/ui";
import { LogoLoader } from '../../../components/LogoLoader';

/** Member "My prizes" (hack-money G3/G4/G6/G7). Nothing here moves money: finance records every payout by hand. */
export function MyPrizes({ scope }: { scope: PrizeScope }) {
  const [page, setPage] = useState(1);
  const { list, send } = useMyPrizes(scope, page);
  const run = (command: PrizeCommand, done?: () => void) => send.mutate(command, { onSuccess: () => done?.() });
  const data = list.data;
  return <section className="grid gap-4" aria-labelledby="my-prizes-title">
    <div className="flex items-start gap-3"><Trophy className="mt-1 text-accent-ink" aria-hidden="true" /><div>
      <h1 id="my-prizes-title" className="title-page">{t`My prizes`}</h1>
      <p className="text-sm text-muted">{t`Prizes you won in this space. Split a cash prize with your team, then tell the organisers where to pay you.`}</p>
    </div></div>
    <ErrorBlock error={list.error || send.error} onRetry={list.error ? () => void list.refetch() : undefined} />
    {list.isLoading ? <LogoLoader label={t`Loading your prizes…`} size={48} className="min-h-16 py-3" /> : null}
    {data && !data.count ? <EmptyState title={t`No prizes yet`} description={t`Prizes appear here once results naming your team are published.`} /> : null}
    {data?.results.map(prize => <PrizeCard key={prize.award_id} prize={prize} makerspaceId={scope.makerspaceId}
      actorId={scope.actorId} pending={send.isPending} send={run} />)}
    {data ? <PagePager page={page} setPage={setPage} next={data.next} /> : null}
  </section>;
}
