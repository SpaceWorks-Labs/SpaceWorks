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
/** E-B4 (D13): `state_counts` counts the search matches per state, so every filter shows its number. */
export type AssignmentPage = Page<Assignment> & { state_counts?: Partial<Record<AssignmentState, number>> };
export type AssignmentState = 'assigned' | 'scored' | 'skipped' | 'recused' | 'invalidated';
export function useAssignments(scope: Scope, page = 1, filters: { state?: AssignmentState | ''; q?: string } = {}) {
  const client = useQueryClient(); const key = [...judgingKey(scope), 'own-assignments', page, filters.state ?? '', filters.q ?? ''];
  useEffect(() => onSessionCleared(() => client.removeQueries({ queryKey: key })), [client, ...key]);
  useEffect(() => () => { client.removeQueries({ queryKey: key }); }, [client, ...key]);
  const params = new URLSearchParams({ page: String(page) });
  if (filters.state) params.set('state', filters.state);
  if (filters.q?.trim()) params.set('q', filters.q.trim());
  const query = useQuery({ queryKey: key, queryFn: () => staffRequest<AssignmentPage>(path(scope, `judge-assignments/?${params}`)), retry: false,
    placeholderData: previous => previous });
  const submit = useMutation({ retry: false, mutationFn: ({ assignment, action, fields }: {
    assignment: Assignment; action: 'score' | 'rank' | 'recuse' | 'skip'; fields: Record<string, unknown>;
  }) => { const body = { ...fields, ...command(assignment.version) };
    return staffRequest<Envelope>(path(scope, `judge-assignments/${assignment.id}/${action}/`), {
      method: 'POST', headers: { 'Idempotency-Key': body.operation_id }, body: JSON.stringify(body) }); },
    onSuccess: () => client.invalidateQueries({ queryKey: judgingKey(scope) }) });
  useClearOnAccessLoss(judgingKey(scope), [query.error, submit.error]);
  return { query, submit };
}
/** D12: the one project "Score next" opened, read fresh so it is the current version even off this page. */
export function useAssignment(scope: Scope, id: number | null) {
  return useQuery({ queryKey: [...judgingKey(scope), 'own-assignment', id], enabled: id !== null, retry: false, staleTime: 0,
    queryFn: () => staffRequest<Assignment>(path(scope, `judge-assignments/${id}/`)) });
}
export function useDefinitions(scope: Scope, page = 1) {
  const key = judgingKey(scope);
  const tracks = useQuery({ queryKey: [...key, 'tracks', page], queryFn: () => staffRequest<Page<Track>>(path(scope, `tracks/?page=${page}`)), retry: false });
  const prizes = useQuery({ queryKey: [...key, 'prizes', page], queryFn: () => staffRequest<Page<Prize>>(path(scope, `prizes/?page=${page}`)), retry: false });
  return { tracks, prizes };
}
