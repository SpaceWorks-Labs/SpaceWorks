import { useEffect } from 'react';
import { useStableKey } from '../../../lib/useStableKey';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { staffRequest } from '../../../lib/api';
import { onSessionCleared } from '../../../lib/api/sessionContext';
import { command, type Page } from '../../events/hackathonGallery/types';
import { useClearOnAccessLoss } from '../../events/hackathonGallery/accessLoss';
import { judgingKey } from './api';
import type { PairwiseAction, PairwiseState, Scope } from './types';

const base = (scope: Scope) => `/admin/events/${scope.eventId}/`;

/**
 * The signed-in judge's open pairwise rounds, each with that judge's own cursor. Standings are
 * never fetched here: judges compare without seeing scores, so nothing anchors their choice.
 */
export function usePairwise(scope: Scope, enabled: boolean) {
  const client = useQueryClient();
  const key = useStableKey([...judgingKey(scope), 'pairwise']);
  useEffect(() => onSessionCleared(() => client.removeQueries({ queryKey: key })), [client, key]);
  const rounds = useQuery({ queryKey: key, enabled, retry: false,
    queryFn: () => staffRequest<Page<PairwiseState>>(`${base(scope)}pairwise-rounds/`) });
  const act = useMutation({ retry: false, mutationFn: ({ round, action, version, fields = {} }: {
    round: number; action: PairwiseAction; version: number; fields?: Record<string, unknown>;
  }) => { const body = { ...fields, ...command(version) };
    return staffRequest<{ version: number }>(`${base(scope)}judging-rounds/${round}/pairwise/${action}/`, {
      method: 'POST', headers: { 'Idempotency-Key': body.operation_id }, body: JSON.stringify(body) }); },
    // Every answer changes the cursor version, so the judge's state is re-read before the next one.
    onSettled: () => client.invalidateQueries({ queryKey: key }) });
  const denied = useClearOnAccessLoss(judgingKey(scope), [rounds.error]);
  return { rounds, act, denied };
}
