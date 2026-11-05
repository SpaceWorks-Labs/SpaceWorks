import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { memberRequest, tenantPublicRequest } from '../../../lib/api';
import type { PeoplesChoiceBallotRead, PeoplesChoicePublicRead } from '../../../generated/api';
import { command } from '../hackathonGallery/types';

export type PeoplesChoicePublic = PeoplesChoicePublicRead;
export type PeoplesChoiceBallot = PeoplesChoiceBallotRead;
export type BallotScope = { makerspaceId: number; eventId: number };

function object(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error('Invalid People’s choice response.');
  return value as Record<string, unknown>;
}
const STATES = ['off', 'scheduled', 'open', 'closed', 'published'];

/** Public responses are parsed: a published award only, never a count before publication. */
export function parsePublic(value: unknown): PeoplesChoicePublic {
  const row = object(value);
  if (!Number.isSafeInteger(row.event_id) || !STATES.includes(String(row.state))) throw new Error('Invalid People’s choice state.');
  const award = row.award === null ? null : object(row.award);
  if (award && (!Array.isArray(award.winners) || typeof award.prize_name !== 'string' || !Number.isSafeInteger(award.total_votes))) {
    throw new Error('Invalid People’s choice award.');
  }
  return { event_id: Number(row.event_id), state: row.state as PeoplesChoicePublic['state'],
    audience: row.audience === 'attendees' ? 'attendees' : 'members',
    opens_at: typeof row.opens_at === 'string' ? row.opens_at : null, closes_at: typeof row.closes_at === 'string' ? row.closes_at : null,
    award: award ? { prize_name: String(award.prize_name), total_votes: Number(award.total_votes), published_at: String(award.published_at),
      winners: (award.winners as unknown[]).map(item => { const winner = object(item);
        return { title: String(winner.title), votes: Number(winner.votes),
          entry_public_id: typeof winner.entry_public_id === 'string' ? winner.entry_public_id : null }; }) } : null };
}

/** The public block. A 404 means the award is off for this space or event: callers render nothing. */
export function usePublicPeoplesChoice(slug: string, token: string, enabled: boolean) {
  return useQuery({ queryKey: ['public-peoples-choice', slug, token], enabled: enabled && Boolean(token), retry: false, staleTime: 30000,
    queryFn: async () => parsePublic(await tenantPublicRequest(slug, `/public/event-programmes/${encodeURIComponent(token)}/peoples-choice/`, { cache: 'no-store' })) });
}

const ballotKey = (scope: BallotScope) => ['peoples-choice-ballot', scope.makerspaceId, scope.eventId] as const;
const base = (scope: BallotScope) => `/member/makerspaces/${scope.makerspaceId}/events/${scope.eventId}/peoples-choice/`;

/** The signed-in member's own ballot and the vote command (one vote, changeable until voting closes). */
export function useBallot(scope: BallotScope | null) {
  const client = useQueryClient();
  const ballot = useQuery({ queryKey: scope ? ballotKey(scope) : ['peoples-choice-ballot', 'none'], enabled: Boolean(scope), retry: false,
    queryFn: () => memberRequest<PeoplesChoiceBallot>(base(scope as BallotScope)) });
  const vote = useMutation({ retry: false,
    mutationFn: ({ entry, version }: { entry: string; version: number }) => {
      const body = { entry_public_id: entry, ...command(version) };
      return memberRequest<PeoplesChoiceBallot>(`${base(scope as BallotScope)}vote/`, {
        method: 'POST', headers: { 'Idempotency-Key': body.operation_id }, body: JSON.stringify(body) });
    },
    onSuccess: data => { if (scope) client.setQueryData(ballotKey(scope), data); } });
  return { ballot, vote };
}

export const REFUSAL_COPY: Record<string, string> = {
  off: 'People’s choice voting is not running.',
  not_open: 'People’s choice voting has not opened yet.',
  closed: 'People’s choice voting has closed. The result appears here once the organisers publish it.',
  published: 'Voting has ended.',
  attendees_only: 'Only checked-in attendees can vote in this People’s choice.',
  voided: 'The organisers voided your vote, so you cannot vote again.',
};
