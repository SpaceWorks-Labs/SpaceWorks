import { useQuery } from "@tanstack/react-query";
import { memberRequest } from "../../lib/api";

export type BorrowingPeriod = "all" | "current" | "history";
export type OwnBorrowingItem = {
  product_name: string; requested_quantity: number; accepted_quantity: number;
  issued_quantity: number; returned_quantity: number; damaged_quantity: number;
  missing_quantity: number; needs_fix_quantity: number;
};
export type OwnBorrowing = {
  id: number; status: string; created_at: string; issued_at: string | null;
  return_due_at: string | null; closed_at: string | null;
  source: "reviewed_request" | "public_self_checkout" | "admin_direct";
  checked_out_at: string | null; returned_at: string | null;
  items: OwnBorrowingItem[]; returns: { returned_at: string }[];
  /** Decision 221(a): optional until the borrowing-history payload carries renewal eligibility. */
  can_renew?: boolean; renewal_refusal?: string | null;
  /** Renewals this loan may still take; null when renewals are off (#234). */
  renewals_left?: number | null;
};
export type OwnBorrowingPage = { count: number; next: string | null; previous: string | null; results: OwnBorrowing[] };

export function useOwnBorrowingHistory(makerspaceId: number | undefined, actorId: number | undefined,
  period: BorrowingPeriod, page: number, enabled: boolean) {
  return useQuery({ queryKey: ["member", "borrowing-history", makerspaceId, actorId, period, page],
    queryFn: () => memberRequest<OwnBorrowingPage>(`/member/makerspaces/${makerspaceId}/borrowing-history?period=${period}&page=${page}`),
    enabled: enabled && Boolean(makerspaceId && actorId), retry: false, staleTime: 0, gcTime: 0 });
}
