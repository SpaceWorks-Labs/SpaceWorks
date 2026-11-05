import { DetailLayout } from '../../../components/layouts';
import { EmptyState } from '../../../components/ui';
import { usePublicResults } from './api';
import { PublishedPeoplesChoice } from '../peoplesChoice/PeoplesChoiceAward';

export function ResultsPage({ makerspaceSlug, publicToken, eventTitle, peoplesChoice = false, projectHref }: { makerspaceSlug: string; publicToken: string; eventTitle: string;
  /** #181: show the published People's choice award, an extra award beside the judged ones. */
  peoplesChoice?: boolean; projectHref?: (id: string) => string }) {
  const query = usePublicResults(makerspaceSlug, publicToken);
  const finalists = query.data?.finalists ?? [];
  return <DetailLayout title={`${eventTitle} results`} state={{ status: query.isLoading ? 'loading' : query.isError ? 'error' : 'ready',
    error: query.error?.message, onRetry: () => void query.refetch() }} main={<div className="grid gap-4">
      <PublishedPeoplesChoice slug={makerspaceSlug} token={publicToken} enabled={peoplesChoice} projectHref={projectHref} />
      {!query.isError && finalists.length ? <section className="grid gap-3 rounded-xl border border-line bg-panel p-5" aria-label="Finalists">
        <h2 className="title-section">Finalists</h2>
        <ul className="grid gap-2">{finalists.map((row, index) => <li key={index} className="font-semibold">{row.title}</li>)}</ul>
      </section> : null}
      {!query.data?.awards.length ? <EmptyState title="No public awards" description="Award cards appear here only after the organizer announces them and the team opts in." /> : null}
      {!query.isError && query.data?.awards.map((award, index) => <article key={index} className="rounded-xl border border-line bg-panel p-5">
        <p className="text-sm text-muted">{award.prize} · Rank {award.rank}</p><h2 className="title-section mt-2">{award.title}</h2>
      </article>)}
    </div>} />;
}
