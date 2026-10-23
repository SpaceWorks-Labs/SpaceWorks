import { useRef } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { memberRequest, staffRequest } from "../../../lib/api";
import type { CommandResult, FinanceDashboardData, FinanceScope, Page, PayeeContext, Payout, PayoutDetail } from "./types";
import type { CommandData, PayoutCommand } from "./commands";

export const payoutKey = (scope: FinanceScope) => ["event-payouts", window.location.host, scope.actorId, scope.makerspaceId] as const;
export const payoutPath = (scope: FinanceScope) => `/admin/makerspaces/${scope.makerspaceId}/event-payouts`;
export const memberPayoutKey = (actorId: number) => ["member-event-payouts", window.location.host, actorId] as const;
export const memberPayoutPath = (id: string) => `/member/event-payouts/${encodeURIComponent(id)}`;
const privateQuery = { gcTime: 0, retry: false } as const;
export function usePayouts(scope: FinanceScope, page: number) {
  return useQuery({ ...privateQuery, queryKey: [...payoutKey(scope), "list", page],
    queryFn: ({ signal }) => staffRequest<Page<Payout>>(`${payoutPath(scope)}/?page=${page}`, { signal, cache: "no-store" }) });
}
export function usePayout(scope: FinanceScope, id: string) {
  return useQuery({ ...privateQuery, queryKey: [...payoutKey(scope), "detail", id],
    queryFn: ({ signal }) => staffRequest<PayoutDetail>(`${payoutPath(scope)}/${encodeURIComponent(id)}/`, { signal, cache: "no-store" }) });
}
export function usePayoutDashboard(scope: FinanceScope) {
  return useQuery({ ...privateQuery, queryKey: [...payoutKey(scope), "dashboard"],
    queryFn: ({ signal }) => staffRequest<FinanceDashboardData>(`${payoutPath(scope)}/dashboard/`, { signal, cache: "no-store" }) });
}
/** Stable UUID after an uncertain response; changed payloads get a new UUID. */
export function useCommandIdentity() {
  const pending = useRef<{ encoded: string; operation: string } | null>(null);
  return { forPayload(data: unknown) {
    const encoded = JSON.stringify(data);
    if (pending.current?.encoded !== encoded) pending.current = { encoded, operation: crypto.randomUUID() };
    return pending.current.operation;
  }, clear() { pending.current = null; } };
}
export function commandPath(scope: FinanceScope, id: string, action: PayoutCommand) {
  // Frozen G1 route addresses entries at the ledger root.
  return action.startsWith("entries/") ? `${payoutPath(scope)}/${action}/`
    : `${payoutPath(scope)}/${encodeURIComponent(id)}/${action}/`;
}
export function usePayoutCommand<Action extends PayoutCommand>(scope: FinanceScope, id: string, action: Action) {
  const client = useQueryClient();
  const identity = useCommandIdentity();
  return useMutation({ ...privateQuery, mutationFn: async (data: CommandData<Action>) => {
    const operation = identity.forPayload({ scope, id, action, data });
    return staffRequest<CommandResult>(commandPath(scope, id, action), { method: "POST", cache: "no-store",
      headers: { "Idempotency-Key": operation }, body: JSON.stringify({ ...data, operation_id: operation }) });
  }, onSuccess: async () => { identity.clear(); await client.invalidateQueries({ queryKey: payoutKey(scope) }); } });
}
export function useMemberPayoutHistory(actorId: number, page: number) {
  return useQuery({ ...privateQuery, queryKey: [...memberPayoutKey(actorId), "list", page],
    queryFn: ({ signal }) => memberRequest<Page<Payout>>(`/member/event-payouts/?page=${page}`, { signal, cache: "no-store" }) });
}
export function useMemberPayout(actorId: number, id: string) {
  return useQuery({ ...privateQuery, queryKey: [...memberPayoutKey(actorId), "detail", id],
    queryFn: ({ signal }) => memberRequest<PayoutDetail>(`${memberPayoutPath(id)}/`, { signal, cache: "no-store" }) });
}
export function usePayeeContext(actorId: number, id: string) {
  return useQuery({ ...privateQuery, queryKey: [...memberPayoutKey(actorId), "payee", id],
    queryFn: ({ signal }) => memberRequest<PayeeContext>(`${memberPayoutPath(id)}/payee/`, { signal, cache: "no-store" }) });
}
