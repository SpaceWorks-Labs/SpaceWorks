import { useEffect } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { staffRequest } from '../../../lib/api';
import { onSessionCleared } from '../../../lib/api/sessionContext';
import { command, type Envelope, type Page } from '../../events/hackathonGallery/types';
import type { Assignment, Prize, ResultState, Round, Scope, Track } from './types';
import { useClearOnAccessLoss } from '../../events/hackathonGallery/accessLoss';

export const judgingKey = (scope: Scope) => ['hackathon-judging', scope.context, scope.actorId, scope.makerspaceId, scope.eventId] as const;
const path = (scope: Scope, suffix: string) => `/admin/events/${scope.eventId}/${suffix}`;
export function useJudging(scope: Scope, enabled = true, resultsEnabled = false, page = 1) {
  const client = useQueryClient();
  const key = judgingKey(scope);
  useEffect(() => onSessionCleared(() => client.removeQueries({ queryKey: key })), [client, ...key]);
  useEffect(() => () => { void client.cancelQueries({ queryKey: key }); client.removeQueries({ queryKey: key }); }, [client, ...key]);
  const query = useQuery({ queryKey: [...key, 'rounds', page], enabled,
    queryFn: () => staffRequest<Page<Round>>(path(scope, `judging-rounds/?page=${page}`)), retry: false, refetchInterval: 15000 });
  const result = useQuery({ queryKey: [...key, 'results'], enabled: enabled && resultsEnabled,
    queryFn: () => staffRequest<ResultState>(path(scope, 'results/finalize/')), retry: false });
  const mutate = useMutation({ retry: false, mutationFn: ({ suffix, version, fields = {}, method = 'POST' }: {
    suffix: string; version: number; fields?: Record<string, unknown>; method?: 'POST' | 'PATCH';
  }) => { const body = { ...fields, ...command(version) };
    return staffRequest<Envelope & Record<string, unknown>>(path(scope, suffix), {
      method, headers: { 'Idempotency-Key': body.operation_id }, body: JSON.stringify(body) }); },
    onSuccess: () => client.invalidateQueries({ queryKey: key }) });
  const denied = useClearOnAccessLoss(key, [query.error, result.error, mutate.error]);
  return { query, result, mutate, denied };
}
export function useAssignments(scope: Scope, page = 1) {
  const client = useQueryClient(); const key = [...judgingKey(scope), 'own-assignments', page];
  useEffect(() => onSessionCleared(() => client.removeQueries({ queryKey: key })), [client, ...key]);
  useEffect(() => () => { client.removeQueries({ queryKey: key }); }, [client, ...key]);
  const query = useQuery({ queryKey: key, queryFn: () => staffRequest<Page<Assignment>>(path(scope, `judge-assignments/?page=${page}`)), retry: false });
  const submit = useMutation({ retry: false, mutationFn: ({ assignment, action, fields }: {
    assignment: Assignment; action: 'score' | 'rank' | 'recuse' | 'skip'; fields: Record<string, unknown>;
  }) => { const body = { ...fields, ...command(assignment.version) };
    return staffRequest<Envelope>(path(scope, `judge-assignments/${assignment.id}/${action}/`), {
      method: 'POST', headers: { 'Idempotency-Key': body.operation_id }, body: JSON.stringify(body) }); },
    onSuccess: () => client.invalidateQueries({ queryKey: judgingKey(scope) }) });
  useClearOnAccessLoss(judgingKey(scope), [query.error, submit.error]);
  return { query, submit };
}
export function useDefinitions(scope: Scope, page = 1) {
  const key = judgingKey(scope);
  const tracks = useQuery({ queryKey: [...key, 'tracks', page], queryFn: () => staffRequest<Page<Track>>(path(scope, `tracks/?page=${page}`)), retry: false });
  const prizes = useQuery({ queryKey: [...key, 'prizes', page], queryFn: () => staffRequest<Page<Prize>>(path(scope, `prizes/?page=${page}`)), retry: false });
  return { tracks, prizes };
}
