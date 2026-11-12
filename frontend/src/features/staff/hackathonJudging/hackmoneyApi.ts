import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { staffRequest } from '../../../lib/api';
import type { Page } from '../../events/hackathonGallery/types';
import type {
  AwardSplitRead, ClaimRead, DepositSettlementRead, MissingTeamChargeRead, OutcomeRead, PrizePoolRead, RevealRead,
  StaffClaimRow, TeamChargeRead,
} from '../../../generated/api';
import { judgingKey } from './api';
import { postCommand } from './l21bApi';
import type { Scope } from './types';
import { moneyToMilli, percentOfMoney } from '../../../lib/money';

/** Hack-money (#180, #181) staff hooks. Nothing here moves money: every write records what staff did. */
const path = (scope: Scope, suffix: string) => `/admin/events/${scope.eventId}/${suffix}`;
const payoutsKey = (scope: Scope) => [...judgingKey(scope), 'prize-payouts'];
const claimsKey = (scope: Scope) => [...judgingKey(scope), 'prize-claims'];
const outcomesKey = (scope: Scope) => [...judgingKey(scope), 'prize-outcomes'];
const poolKey = (scope: Scope) => [...judgingKey(scope), 'prize-pool'];

export type ShareInput = { member_id: number; amount: string };
export type FulfilInput = { method: 'handed_over' | 'shipped' | 'sponsor_paid' | 'other'; reference?: string; note?: string; happened_on: string };
export type RevealReason = 'pay_winner' | 'verify_details' | 'record_tax';
export type ResolveInput = { outcome: 'repaid' | 'waived'; method?: string; reference?: string; note?: string; happened_on: string };

/** Split, fulfil and forfeit an announced award (G3/G4/G5/G8). Every success refreshes payouts, outcomes and the pool. */
export function usePrizeAwardActions(scope: Scope) {
  const client = useQueryClient();
  const refresh = () => {
    for (const key of [payoutsKey(scope), outcomesKey(scope), poolKey(scope), claimsKey(scope)]) void client.invalidateQueries({ queryKey: key });
  };
  const split = useMutation({ retry: false, onSuccess: refresh,
    mutationFn: ({ awardId, shares }: { awardId: number; shares: ShareInput[] }) =>
      postCommand<AwardSplitRead>(scope, `prize-awards/${awardId}/split/`, 0, { shares }) });
  const fulfil = useMutation({ retry: false, onSuccess: refresh,
    mutationFn: ({ awardId, fields }: { awardId: number; fields: FulfilInput }) =>
      postCommand<OutcomeRead>(scope, `prize-awards/${awardId}/fulfil/`, 0, fields) });
  const forfeit = useMutation({ retry: false, onSuccess: refresh,
    mutationFn: ({ awardId, note, shareId }: { awardId: number; note: string; shareId?: number }) =>
      postCommand<OutcomeRead>(scope, `prize-awards/${awardId}/forfeit/`, 0, { note, ...(shareId ? { share_id: shareId } : {}) }) });
  return { split, fulfil, forfeit };
}

/** Winner claims (G4/G7): masked on every read; a reveal is returned once and never stored in the query cache. */
export function usePrizeClaims(scope: Scope, enabled: boolean) {
  const client = useQueryClient(); const key = claimsKey(scope);
  const list = useQuery({ queryKey: key, enabled, retry: false, queryFn: () => staffRequest<Page<StaffClaimRow>>(path(scope, 'prize-claims/')) });
  const verify = useMutation({ retry: false, onSuccess: () => client.invalidateQueries({ queryKey: key }),
    mutationFn: ({ shareId, version }: { shareId: number; version: number }) =>
      postCommand<ClaimRead>(scope, `prize-shares/${shareId}/verify/`, version) });
  const reveal = useMutation({ retry: false, gcTime: 0,
    mutationFn: ({ shareId, version, reason }: { shareId: number; version: number; reason: RevealReason }) =>
      postCommand<RevealRead>(scope, `prize-shares/${shareId}/reveal/`, version, { reason_code: reason }) });
  return { list, verify, reveal };
}

/** Fulfilments, sponsor payments, forfeits and recoveries (G16). */
export function usePrizeOutcomes(scope: Scope, enabled: boolean) {
  const client = useQueryClient(); const key = outcomesKey(scope);
  const list = useQuery({ queryKey: key, enabled, retry: false, queryFn: () => staffRequest<Page<OutcomeRead>>(path(scope, 'prize-outcomes/')) });
  const resolve = useMutation({ retry: false,
    onSuccess: () => { void client.invalidateQueries({ queryKey: key }); void client.invalidateQueries({ queryKey: poolKey(scope) }); },
    mutationFn: ({ id, fields }: { id: number; fields: ResolveInput }) =>
      postCommand<OutcomeRead>(scope, `prize-outcomes/${id}/resolve/`, 0, fields) });
  return { list, resolve };
}

export function usePrizePool(scope: Scope, enabled: boolean) {
  return useQuery({ queryKey: poolKey(scope), enabled, retry: false, queryFn: () => staffRequest<PrizePoolRead>(path(scope, 'prize-pool/')) });
}

/** G10: preview and approve the one deposit settlement batch (expected_version = programme options version). */
export function useDeposits(scope: Scope, enabled: boolean) {
  const client = useQueryClient(); const key = [...judgingKey(scope), 'deposits'];
  const summary = useQuery({ queryKey: key, enabled, retry: false, queryFn: () => staffRequest<DepositSettlementRead>(path(scope, 'deposits/')) });
  const settle = useMutation({ retry: false,
    onSuccess: data => { client.setQueryData(key, data); void client.invalidateQueries({ queryKey: [...judgingKey(scope), 'programme-options'] }); },
    mutationFn: (optionsVersion: number) => postCommand<DepositSettlementRead>(scope, 'deposits/settle/', optionsVersion) });
  return { summary, settle };
}

/** G15: confirmed teams whose team charge was never raised, and an idempotent retry. */
export function useMissingTeamCharges(scope: Scope, enabled: boolean) {
  const client = useQueryClient(); const key = [...judgingKey(scope), 'team-charges-missing'];
  const list = useQuery({ queryKey: key, enabled, retry: false, queryFn: () => staffRequest<Page<MissingTeamChargeRead>>(path(scope, 'team-charges/missing/')) });
  const raise = useMutation({ retry: false, onSuccess: () => client.invalidateQueries({ queryKey: key }),
    mutationFn: (teamId: number) => postCommand<TeamChargeRead>(scope, `team-charges/${teamId}/raise/`, 0) });
  return { list, raise };
}

/** The TDS the space's setting proposes for a gross amount (record only, #181); '' when none. */
export type TaxProposal = { enabled: boolean; rate: string; threshold: string };

/** Decimal-safe (BigInt thousandths), rounded at the currency's own minor unit like the server's proposal. */
export function proposedTds(amount: string, proposal: TaxProposal | undefined, currency: string): string {
  const gross = moneyToMilli(amount), limit = moneyToMilli(proposal?.threshold ?? '');
  if (!proposal?.enabled || gross === null || limit === null || gross <= limit) return '';
  return percentOfMoney(amount, proposal.rate, currency) ?? '';
}

export const today = () => new Date().toISOString().slice(0, 10);
