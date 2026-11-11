import { t } from "@lingui/core/macro";
import { useState } from 'react';
import { DetailLayout } from '../../../components/layouts';
import { EmptyState, Field } from '../../../components/ui';
import { usePublicResults } from './api';
import { PublishedPeoplesChoice } from '../peoplesChoice/PeoplesChoiceAward';

export function ResultsPage({ makerspaceSlug, publicToken, eventTitle, peoplesChoice = false, projectHref }: { makerspaceSlug: string; publicToken: string; eventTitle: string;
  /** #181: show the published People's choice award, an extra award beside the judged ones. */
  peoplesChoice?: boolean; projectHref?: (id: string) => string }) {
  const [text, setText] = useState(''); const [search, setSearch] = useState('');
  const query = usePublicResults(makerspaceSlug, publicToken, search);
  const finalists = query.data?.finalists ?? [];
  const searching = !!search.trim();
  return <DetailLayout title={`${eventTitle} results`} state={{ status: query.isLoading ? 'loading' : query.isError ? 'error' : 'ready',
    error: query.error?.message, onRetry: () => void query.refetch() }} main={<div className="grid gap-4">
      {/* D13: search the announced awards and finalists by project title or prize. */}
      <form role="search" className="flex flex-wrap items-end gap-2" onSubmit={event => { event.preventDefault(); setSearch(text); }}>
        <Field label={t`Search results`}><input className="desk-input min-h-11" type="search" maxLength={100} value={text}
          onChange={e => { setText(e.target.value); if (!e.target.value) setSearch(''); }} placeholder={t`Project or prize`} /></Field>
        <button type="submit" className="desk-button min-h-11">{t`Search`}</button>
        {searching ? <button type="button" className="desk-button-ghost min-h-11 underline underline-offset-4" onClick={() => { setText(''); setSearch(''); }}>{t`Clear search`}</button> : null}
      </form>
      {!searching ? <PublishedPeoplesChoice slug={makerspaceSlug} token={publicToken} enabled={peoplesChoice} projectHref={projectHref} /> : null}
      {!query.isError && finalists.length ? <section className="grid gap-3 rounded-xl border border-line bg-panel p-5" aria-label={t`Finalists`}>
        <h2 className="title-section">{t`Finalists`}</h2>
        <ul className="grid gap-2">{finalists.map((row, index) => <li key={index} className="font-semibold">{row.title}</li>)}</ul>
      </section> : null}
      {!query.data?.awards.length ? searching ? <EmptyState title={t`Nothing matches “${search.trim()}”`} description={t`Try another project title or prize name.`} />
        : <EmptyState title={t`No public awards`} description={t`Award cards appear here only after the organizer announces them and the team opts in.`} /> : null}
      {!query.isError && query.data?.awards.map((award, index) => <article key={index} className="rounded-xl border border-line bg-panel p-5">
        <p className="text-sm text-muted">{t`${award.prize} · Rank ${award.rank}`}</p><h2 className="title-section mt-2">{award.title}</h2>
      </article>)}
    </div>} />;
}
