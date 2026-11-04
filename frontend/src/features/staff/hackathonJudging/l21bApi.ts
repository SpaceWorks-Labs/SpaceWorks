import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { staffRequest } from '../../../lib/api';
import { command, type Page } from '../../events/hackathonGallery/types';
import type {
  FinalistAdvanceRead, FinalistPreviewRead, NextProjectRead, OptionsRead, PayoutRead, PrizePayoutPage, ProgressRead,
} from '../../../generated/api';
import { judgingKey } from './api';
import type { Scope } from './types';

export type FinalistPreview = FinalistPreviewRead;
export type FinalistAdvance = FinalistAdvanceRead;
export type RoundProgress = ProgressRead;
export type ProgrammeOptions = OptionsRead;
export type PrizePayout = PayoutRead;
export type FinalistSelection = { source_round_id: number; target_round_id: number; selection: 'top_n' | 'manual'; top_n?: number; snapshot_ids?: number[] };

const path = (scope: Scope, suffix: string) => `/admin/events/${scope.eventId}/${suffix}`;

/** Every L21b command carries a fresh operation id, echoed in the Idempotency-Key header. */
export function postCommand<T>(scope: Scope, suffix: string, version: number, fields: Record<string, unknown> = {}, method: 'POST' | 'PATCH' = 'POST') {
  const body = { ...fields, ...command(version) };
  return staffRequest<T>(path(scope, suffix), { method, headers: { 'Idempotency-Key': body.operation_id }, body: JSON.stringify(body) });
}

export function previewQuery(selection: FinalistSelection) {
  const params = new URLSearchParams({ source_round_id: String(selection.source_round_id),
    target_round_id: String(selection.target_round_id), selection: selection.selection });
  if (selection.selection === 'top_n' && selection.top_n) params.set('top_n', String(selection.top_n));
  if (selection.selection === 'manual' && selection.snapshot_ids?.length) params.set('snapshot_ids', selection.snapshot_ids.join(','));
  return params.toString();
}

export function useFinalists(scope: Scope, enabled: boolean) {
  const client = useQueryClient(); const key = [...judgingKey(scope), 'finalists'];
  const list = useQuery({ queryKey: key, enabled, retry: false, queryFn: () => staffRequest<Page<FinalistAdvance>>(path(scope, 'finalists/')) });
  const preview = useMutation({ retry: false,
    mutationFn: (selection: FinalistSelection) => staffRequest<FinalistPreview>(path(scope, `finalists/preview/?${previewQuery(selection)}`)) });
  const apply = useMutation({ retry: false, onSuccess: () => client.invalidateQueries({ queryKey: judgingKey(scope) }),
    mutationFn: ({ selection, fingerprint, version }: { selection: FinalistSelection; fingerprint: string; version: number }) =>
      postCommand<FinalistPreview>(scope, 'finalists/apply/', version, { ...selection, fingerprint }) });
  const publish = useMutation({ retry: false, onSuccess: () => client.invalidateQueries({ queryKey: key }),
    mutationFn: ({ advance, version }: { advance: number; version: number }) => postCommand(scope, 'finalists/publish/', version, { advance_id: advance }) });
  return { list, preview, apply, publish };
}

export function useRoundProgress(scope: Scope, roundId: number) {
  return useQuery({ queryKey: [...judgingKey(scope), 'progress', roundId], enabled: roundId > 0, retry: false, refetchInterval: 30000,
    queryFn: () => staffRequest<RoundProgress>(path(scope, `judging-rounds/${roundId}/progress/`)) });
}

export function useNextProject(scope: Scope) {
  const client = useQueryClient();
  return useMutation({ retry: false, onSuccess: () => client.invalidateQueries({ queryKey: judgingKey(scope) }),
    mutationFn: ({ roundId, version }: { roundId: number; version: number }) =>
      postCommand<NextProjectRead>(scope, `judging-rounds/${roundId}/next-project/`, version) });
}

export function useProgrammeOptions(scope: Scope) {
  const client = useQueryClient(); const key = [...judgingKey(scope), 'programme-options'];
  const query = useQuery({ queryKey: key, retry: false, queryFn: () => staffRequest<ProgrammeOptions>(path(scope, 'programme-options/')) });
  const save = useMutation({ retry: false, onSuccess: data => client.setQueryData(key, data),
    mutationFn: ({ version, fields }: { version: number; fields: Record<string, unknown> }) =>
      postCommand<ProgrammeOptions>(scope, 'programme-options/', version, fields, 'PATCH') });
  const sendResults = useMutation({ retry: false, onSuccess: data => client.setQueryData(key, data),
    mutationFn: (resultVersion: number) => postCommand<ProgrammeOptions>(scope, 'results/send-email/', resultVersion) });
  return { query, save, sendResults };
}

export function usePrizePayouts(scope: Scope, enabled: boolean) {
  const client = useQueryClient(); const key = [...judgingKey(scope), 'prize-payouts'];
  const list = useQuery({ queryKey: key, enabled, retry: false, queryFn: () => staffRequest<PrizePayoutPage>(path(scope, 'prize-payouts/')) });
  const record = useMutation({ retry: false, onSuccess: () => client.invalidateQueries({ queryKey: key }),
    mutationFn: (fields: Record<string, unknown>) => postCommand<PrizePayout>(scope, 'prize-payouts/', 0, fields) });
  const reverse = useMutation({ retry: false, onSuccess: () => client.invalidateQueries({ queryKey: key }),
    mutationFn: ({ id, reason }: { id: number; reason: string }) => postCommand<PrizePayout>(scope, `prize-payouts/${id}/reverse/`, 0, { reason }) });
  return { list, record, reverse };
}
