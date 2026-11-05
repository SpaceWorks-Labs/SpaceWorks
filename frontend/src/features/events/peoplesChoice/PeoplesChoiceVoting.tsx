import { useEffect, useState } from 'react';
import { Heart } from 'lucide-react';
import { ErrorBlock } from '../../../components/ui';
import { MemberAuthPanel } from '../../members/MemberAuthPanel';
import { getAccessToken, refreshAccessToken } from '../../../lib/api';
import { PeoplesChoiceAward } from './PeoplesChoiceAward';
import { REFUSAL_COPY, useBallot, usePublicPeoplesChoice } from './api';

export type PeoplesChoiceSpace = { makerspaceId: number };
const when = (value: string | null) => value ? new Date(value).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' }) : '';

/** Restores a member session once, and only where People's choice is on (no refresh call otherwise). */
function useVoterSession(enabled: boolean) {
  const [session, setSession] = useState<'restoring' | 'authenticated' | 'anonymous'>(() => getAccessToken() ? 'authenticated' : 'restoring');
  useEffect(() => {
    if (!enabled || getAccessToken()) return;
    let active = true;
    void refreshAccessToken().then(restored => { if (active) setSession(restored ? 'authenticated' : 'anonymous'); })
      .catch(() => { if (active) setSession('anonymous'); });
    return () => { active = false; };
  }, [enabled]);
  return [session, setSession] as const;
}

/** Everything the gallery needs for People's choice (#181): the public state, the member's ballot and the vote. */
export function usePeoplesChoiceVoting(slug: string, token: string, space: PeoplesChoiceSpace | undefined) {
  const pub = usePublicPeoplesChoice(slug, token, Boolean(space));
  const running = Boolean(pub.data && pub.data.state !== 'off');
  const [session, setSession] = useVoterSession(running);
  const signedIn = session === 'authenticated';
  const { ballot, vote } = useBallot(space && running && signedIn && pub.data ? { makerspaceId: space.makerspaceId, eventId: pub.data.event_id } : null);
  return { pub: running ? pub.data : undefined, session, setSession, ballot: ballot.data, ballotError: ballot.error, vote };
}
export type PeoplesChoiceVoting = ReturnType<typeof usePeoplesChoiceVoting>;

/** The block above the gallery: the window, the member's ballot, sign-in, or the published award. */
export function PeoplesChoiceBanner({ voting, slug, projectHref }: { voting: PeoplesChoiceVoting; slug: string; projectHref?: (id: string) => string }) {
  const [signIn, setSignIn] = useState(false);
  const { pub, ballot } = voting;
  if (!pub) return null;
  if (pub.award) return <PeoplesChoiceAward award={pub.award} projectHref={projectHref} />;
  const audience = pub.audience === 'attendees' ? 'Checked-in attendees' : 'Signed-in members';
  const timing = pub.state === 'scheduled' ? `Voting opens ${when(pub.opens_at)}.`
    : pub.state === 'open' ? (pub.closes_at ? `Voting is open until ${when(pub.closes_at)}.` : 'Voting is open.')
      : 'Voting has closed. The result appears here once the organisers publish it.';
  return <section className="grid gap-3 rounded-xl border border-line bg-panel p-5" aria-label="People's choice">
    <div className="flex items-start gap-3"><Heart className="mt-1 text-accent" aria-hidden="true" /><div className="grid gap-1">
      <h2 className="title-section">People’s choice</h2>
      <p className="text-sm">{timing} {pub.state !== 'closed' ? `${audience} each get one vote for their favourite project, and can change it until voting closes.` : ''}</p>
      <p className="text-sm text-muted">No counts are shown until the organisers publish the result. Judging is separate.</p></div></div>
    {pub.state === 'open' && voting.session === 'anonymous' ? (signIn
      ? <MemberAuthPanel embedded makerspaceSlug={slug} context={<p className="text-sm text-muted">Sign in to vote.</p>}
        onAuthenticated={() => { setSignIn(false); voting.setSession('authenticated'); }} />
      : <button type="button" className="desk-button min-h-11 justify-self-start" onClick={() => setSignIn(true)}>Sign in to vote</button>) : null}
    {ballot && !ballot.can_vote && ballot.refusal && ballot.refusal !== 'closed' ? <p className="text-sm" role="status">{REFUSAL_COPY[ballot.refusal]}</p> : null}
    {ballot?.entry_public_id ? <p className="text-sm" role="status">You have voted. Choose another project to change your vote.</p> : null}
    <ErrorBlock error={voting.ballotError || voting.vote.error} />
  </section>;
}

/** The vote control on one gallery card; nothing when voting is not open to this member. */
export function VoteButton({ voting, entryId, title }: { voting: PeoplesChoiceVoting; entryId: string; title: string }) {
  const { ballot, vote } = voting;
  if (!voting.pub || voting.pub.state !== 'open' || !ballot) return null;
  if (ballot.own_entry_public_ids.includes(entryId)) return <p className="text-sm text-muted">Your team’s project</p>;
  const chosen = ballot.entry_public_id === entryId;
  return <button type="button" className={chosen ? 'desk-button-primary min-h-11' : 'desk-button min-h-11'} aria-pressed={chosen}
    disabled={!ballot.can_vote || chosen || vote.isPending}
    onClick={() => vote.mutate({ entry: entryId, version: ballot.version })}>
    <Heart size={18} aria-hidden="true" />{chosen ? 'Your vote' : ballot.entry_public_id ? 'Move my vote here' : 'Vote'}{' '}
    <span className="sr-only">for {title}</span></button>;
}
