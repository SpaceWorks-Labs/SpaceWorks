import { useRef } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { memberRequest, staffRequest } from "../../../lib/api";
import type { FinanceScope, Page, Payout, PayoutDetail } from "./types";

export const payoutKey = (scope: FinanceScope) => ["event-payouts", window.location.host, scope.actorId, scope.makerspaceId] as const;
export const payoutPath = (scope: FinanceScope) => `/admin/makerspaces/${scope.makerspaceId}/event-payouts`;
export function usePayouts(scope: FinanceScope, page: number) {
  return useQuery({ queryKey: [...payoutKey(scope), "list", page], gcTime: 0, retry: false,
    queryFn: () => staffRequest<Page<Payout>>(`${payoutPath(scope)}/?page=${page}`, { cache: "no-store" }) });
}
export function usePayout(scope: FinanceScope, id: string) {
  return useQuery({ queryKey: [...payoutKey(scope), id], gcTime: 0, retry: false,
    queryFn: () => staffRequest<PayoutDetail>(`${payoutPath(scope)}/${id}/`, { cache: "no-store" }) });
}
export function usePayoutCommand(scope: FinanceScope, id: string, action: string) {
  const client = useQueryClient();
  const pending = useRef<{ encoded: string; operation: string } | null>(null);
  return useMutation({ gcTime: 0, retry: false, mutationFn: async (data: Record<string, unknown>) => {
    const encoded = JSON.stringify({ action, id, data });
    if (pending.current?.encoded !== encoded) pending.current = { encoded, operation: crypto.randomUUID() };
    const operation = pending.current.operation;
    await staffRequest(`${payoutPath(scope)}/${id}/${action}/`, { method: "POST", cache: "no-store",
      headers: { "Idempotency-Key": operation }, body: JSON.stringify({ ...data, operation_id: operation }) });
  }, onSuccess: async () => { pending.current = null; await client.invalidateQueries({ queryKey: payoutKey(scope) }); } });
}
export function useMemberPayoutHistory(actorId: number, page: number) {
  return useQuery({ queryKey: ["member-event-payout-history", window.location.host, actorId, page], gcTime: 0, retry: false,
    queryFn: () => memberRequest<Page<Payout>>(`/member/event-payouts/?page=${page}`, { cache: "no-store" }) });
}
