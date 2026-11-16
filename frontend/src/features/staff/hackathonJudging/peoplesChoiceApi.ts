import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { staffRequest } from '../../../lib/api';
import type { Page } from '../../events/hackathonGallery/types';
import type {
  PayoutRead, PeoplesChoiceConfigRead, PeoplesChoicePayableWinnersRead, PeoplesChoiceStandingsRead, PeoplesChoiceVoteRowRead,
} from '../../../generated/api';
import { judgingKey } from './api';
import { postCommand } from './l21bApi';
import type { Scope } from './types';

export type PeoplesChoiceSettings = PeoplesChoiceConfigRead;
export type PeoplesChoiceStandings = PeoplesChoiceStandingsRead;
export type PeoplesChoiceBallot = PeoplesChoiceVoteRowRead;

const path = (scope: Scope, suffix = '') => `/admin/events/${scope.eventId}/peoples-choice/${suffix}`;
const pcKey = (scope: Scope) => [...judgingKey(scope), 'peoples-choice'] as const;

/** Settings, the staff-only count and publication (#181). Every write is a versioned, idempotent command. */
export function usePeoplesChoice(scope: Scope) {
  const client = useQueryClient(); const key = pcKey(scope);
  const settings = useQuery({ queryKey: [...key, 'settings'], retry: false,
    queryFn: () => staffRequest<PeoplesChoiceSettings>(path(scope)) });
  const standings = useQuery({ queryKey: [...key, 'standings'], retry: false, enabled: Boolean(settings.data?.enabled || settings.data?.state === 'published'),
    queryFn: () => staffRequest<PeoplesChoiceStandings>(path(scope, 'standings/')) });
  const save = useMutation({ retry: false, onSuccess: data => { client.setQueryData([...key, 'settings'], data); void client.invalidateQueries({ queryKey: key }); },
    mutationFn: ({ version, fields }: { version: number; fields: Record<string, unknown> }) =>
      postCommand<PeoplesChoiceSettings>(scope, 'peoples-choice/', version, fields, 'PATCH') });
  const publish = useMutation({ retry: false, onSuccess: () => client.invalidateQueries({ queryKey: key }),
    mutationFn: (version: number) => postCommand<PeoplesChoiceStandings>(scope, 'peoples-choice/publish/', version) });
  return { settings, standings, save, publish };
}

export function usePeoplesChoiceBallots(scope: Scope, page: number) {
  const client = useQueryClient(); const key = pcKey(scope);
  const list = useQuery({ queryKey: [...key, 'ballots', page], retry: false,
    queryFn: () => staffRequest<Page<PeoplesChoiceBallot>>(path(scope, `votes/?page=${page}`)) });
  const voidBallot = useMutation({ retry: false, onSuccess: () => client.invalidateQueries({ queryKey: key }),
    mutationFn: ({ handle, version, reason }: { handle: string; version: number; reason: string }) =>
      postCommand<PeoplesChoiceBallot>(scope, `peoples-choice/votes/${handle}/void/`, version, { reason }) });
  return { list, voidBallot };
}

export function usePeoplesChoicePayouts(scope: Scope) {
  const client = useQueryClient(); const key = [...pcKey(scope), 'payouts'];
  const winners = useQuery({ queryKey: key, retry: false,
    queryFn: () => staffRequest<PeoplesChoicePayableWinnersRead>(path(scope, 'payouts/')) });
  const record = useMutation({ retry: false, onSuccess: () => client.invalidateQueries({ queryKey: judgingKey(scope) }),
    mutationFn: (fields: Record<string, unknown>) => postCommand<PayoutRead>(scope, 'peoples-choice/payouts/', 0, fields) });
  return { winners, record };
}
