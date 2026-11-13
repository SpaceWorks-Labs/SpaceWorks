import { t } from "@lingui/core/macro";
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { EmptyState, ErrorBlock, Pagination } from '../../../components/ui';
import { staffRequest } from '../../../lib/api';
import type { Page } from '../../events/hackathonGallery/types';
import { judgingKey } from './api';
import type { Scope } from './types';
import { LogoLoader } from '../../../components/LogoLoader';

type Signal = { team_id: number; fresh_nominations: number; repeat_nominations: number;
  final_rating_count: number; final_rating_mean: string | null; top_two_picks: number };
export function MentorShortlistBoard({ scope }: { scope: Scope }) {
  const [page, setPage] = useState(1);
  const query = useQuery({ queryKey: [...judgingKey(scope), 'mentor-signals', page], retry: false,
    queryFn: () => staffRequest<Page<Signal>>(`/admin/events/${scope.eventId}/judging-signals/?page=${page}`) });
  return <section className="grid gap-4" aria-label={t`Private mentor shortlist signals`}>
    <h3 className="title-section">{t`Private mentor shortlist signals`}</h3>
    <p className="text-sm text-muted">{t`Use these separate Mentor Desk observations during integrity and shortlist review. Judging calculations use only submitted rubric judgments or ranking ballots.`}</p>
    {query.isLoading ? <LogoLoader label={t`Loading mentor signals…`} size={48} className="min-h-16 py-3" /> : null}
    <ErrorBlock error={query.error} onRetry={() => void query.refetch()} />
    {!query.isLoading && !query.isError && !query.data?.count ? <EmptyState title={t`No mentor signals yet`} description={t`Nominations and final-round observations appear here when Mentor Desk is in use.`} /> : null}
    {!query.isError && query.data?.results.map(row => <article key={row.team_id} className="rounded-xl border border-line bg-panel p-4">
      <h4 className="font-semibold">{t`Team ${row.team_id}`}</h4><dl className="mt-3 grid grid-cols-2 gap-2 text-sm">
        <dt>{t`Fresh nominations`}</dt><dd>{row.fresh_nominations}</dd><dt>{t`Repeat nominations`}</dt><dd>{row.repeat_nominations}</dd>
        <dt>{t`Final-round ratings`}</dt><dd>{t`${row.final_rating_count} · mean `}{row.final_rating_mean ?? t`No submitted ratings`}</dd>
        <dt>{t`Top-two picks`}</dt><dd>{row.top_two_picks}</dd></dl>
    </article>)}
    <Pagination page={page} count={query.data?.count ?? 0} pageSize={24} totalPages={Math.ceil((query.data?.count ?? 0) / 24)} onChange={setPage} />
  </section>;
}
