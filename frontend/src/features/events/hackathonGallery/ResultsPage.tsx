import { DetailLayout } from '../../../components/layouts';
import { EmptyState } from '../../../components/ui';
import { usePublicResults } from './api';

export function ResultsPage({ makerspaceSlug, publicToken, eventTitle }: { makerspaceSlug: string; publicToken: string; eventTitle: string }) {
  const query = usePublicResults(makerspaceSlug, publicToken);
  const finalists = query.data?.finalists ?? [];
  return <DetailLayout title={`${eventTitle} results`} state={{ status: query.isLoading ? 'loading' : query.isError ? 'error' : 'ready',
    error: query.error?.message, onRetry: () => void query.refetch() }} main={<div className="grid gap-4">
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
