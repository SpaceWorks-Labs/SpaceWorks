import { t } from "@lingui/core/macro";
import { useStableKey } from '../../../lib/useStableKey';
import { useEffect } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { memberRequest, tenantPublicRequest } from '../../../lib/api';
import { onSessionCleared } from '../../../lib/api/sessionContext';
import type { MyPrizeRead, MyPrizeReadPage, PublicPrizeRead, Team } from '../../../generated/api';
import { command, type Page } from '../hackathonGallery/types';

/** `currency` is the space currency every amount on the prize is in (regenerated types will carry it). */
export type MyPrize = MyPrizeRead & { currency?: string };
export type PrizeScope = { makerspaceId: number; actorId: number };
export type PrizeCommand = { eventId: number; suffix: string; version: number; fields?: Record<string, unknown> };

export const prizesKey = (scope: PrizeScope) => ['member-prizes', scope.actorId, scope.makerspaceId] as const;
export const eventBase = (makerspaceId: number, eventId: number) => `/member/makerspaces/${makerspaceId}/events/${eventId}/`;

/** "My prizes" (hack-money G3/G4/G6/G7): every award of a published result naming this member. */
export function useMyPrizes(scope: PrizeScope, page = 1) {
  const client = useQueryClient(); const key = useStableKey(prizesKey(scope));
  useEffect(() => onSessionCleared(() => client.removeQueries({ queryKey: key })), [client, key]);
  const list = useQuery({ queryKey: [...key, page], retry: false, staleTime: 0,
    queryFn: () => memberRequest<MyPrizeReadPage>(`/member/makerspaces/${scope.makerspaceId}/prizes/?page=${page}`, { cache: 'no-store' }) });
  // Payee details and the PAN are sent once and never cached: the response is the masked claim only.
  const send = useMutation({ retry: false, onSuccess: () => client.invalidateQueries({ queryKey: key }),
    mutationFn: ({ eventId, suffix, version, fields = {} }: PrizeCommand) => {
      const body = { ...fields, ...command(version) };
      return memberRequest<unknown>(eventBase(scope.makerspaceId, eventId) + suffix,
        { method: 'POST', headers: { 'Idempotency-Key': body.operation_id }, body: JSON.stringify(body) });
    } });
  return { list, send };
}

/** The leader's own teams at this event, to name the members a split is shared between. */
export function useLeaderTeam(makerspaceId: number, eventId: number, actorId: number, enabled: boolean) {
  return useQuery({ queryKey: ['member-prizes-team', actorId, makerspaceId, eventId], enabled, retry: false, staleTime: 0,
    queryFn: async () => {
      const teams = await memberRequest<Page<Team>>(`${eventBase(makerspaceId, eventId)}teams/`, { cache: 'no-store' });
      return teams.results.find(team => team.leader_member_id === actorId) ?? null;
    } });
}

/** Public prize list (G6). A 404 means the organiser keeps prizes private, so the block shows nothing. */
export function usePublicPrizes(slug: string, token: string, enabled = true) {
  return useQuery({ queryKey: ['public-hackathon-prizes', slug, token], staleTime: 0, gcTime: 0, retry: false,
    enabled: Boolean(enabled && slug && token),
    queryFn: async () => {
      try {
        return await tenantPublicRequest<PublicPrizeRead[]>(slug, `/public/event-programmes/${encodeURIComponent(token)}/prizes/`, { cache: 'no-store' });
      } catch (error) {
        if ((error as { status?: number }).status === 404) return [];
        throw error;
      }
    } });
}

/** Built at render time so the wording follows the member's language (a module-level `t` map would freeze it). */
export function statusLabel(status: string): string {
  switch (status) {
    case 'owed': return t`Owed to you`;
    case 'paid': return t`Paid`;
    case 'part_paid': return t`Partly paid`;
    case 'fulfilled': return t`Handed over`;
    case 'sponsor_paid': return t`Paid by the sponsor`;
    case 'forfeited': return t`Forfeited`;
    default: return status.replace(/_/g, ' ');
  }
}
export function kindLabel(kind: string): string {
  switch (kind) {
    case 'cash': return t`Cash`;
    case 'item': return t`Item`;
    case 'credit': return t`Credit`;
    case 'perk': return t`Perk`;
    default: return kind.replace(/_/g, ' ');
  }
}
export function shareLabel(state: string): string {
  switch (state) {
    case 'proposed': return t`waiting for you to confirm`;
    case 'confirmed': return t`confirmed`;
    case 'declined': return t`declined`;
    case 'forfeited': return t`forfeited`;
    default: return state.replace(/_/g, ' ');
  }
}

export function statusTone(status: string): 'success' | 'warn' | 'danger' | 'neutral' {
  if (status === 'paid' || status === 'fulfilled' || status === 'sponsor_paid') return 'success';
  if (status === 'forfeited') return 'danger';
  return status === 'owed' || status === 'part_paid' ? 'warn' : 'neutral';
}

export function payoutRow(payout: MyPrize['my_payout']) {
  if (!payout) return null;
  const text = (key: string) => (typeof payout[key] === 'string' ? (payout[key] as string) : '');
  return { gross: text('gross'), tds: text('tds'), net: text('net'), currency: text('currency').toUpperCase(), paidOn: text('paid_on') };
}
