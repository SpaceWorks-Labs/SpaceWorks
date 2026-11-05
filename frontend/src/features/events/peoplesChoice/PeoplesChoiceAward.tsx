import { Heart } from 'lucide-react';
import type { PeoplesChoicePublic } from './api';
import { usePublicPeoplesChoice } from './api';

/** The published People's choice award (#181): the winner (joint on a tie) and the total votes counted. */
export function PeoplesChoiceAward({ award, projectHref }: { award: NonNullable<PeoplesChoicePublic['award']>; projectHref?: (id: string) => string }) {
  return <section className="grid gap-3 rounded-xl border border-line bg-panel p-5" aria-label="People's choice award">
    <div className="flex items-start gap-3"><Heart className="mt-1 text-accent" aria-hidden="true" /><div className="grid gap-1">
      <h2 className="title-section">{award.prize_name}</h2>
      <p className="text-sm text-muted">Voted by the community, {award.total_votes} {award.total_votes === 1 ? 'vote' : 'votes'} in all. Judging awards are separate.</p></div></div>
    {award.winners.length ? <ul className="grid gap-2">{award.winners.map((winner, index) => <li key={winner.entry_public_id ?? index} className="font-semibold">
      {winner.entry_public_id && projectHref ? <a className="underline underline-offset-4" href={projectHref(winner.entry_public_id)}>{winner.title}</a> : winner.title}
      <span className="font-normal text-muted"> · {winner.votes} {winner.votes === 1 ? 'vote' : 'votes'}</span></li>)}</ul>
      : <p className="text-sm">No project received a vote.</p>}
  </section>;
}

/** The award on the event and results pages; nothing until it is published (or when the award is off). */
export function PublishedPeoplesChoice({ slug, token, enabled, projectHref }: { slug: string; token: string; enabled: boolean; projectHref?: (id: string) => string }) {
  const query = usePublicPeoplesChoice(slug, token, enabled);
  return query.data?.award ? <PeoplesChoiceAward award={query.data.award} projectHref={projectHref} /> : null;
}
