import { t } from "@lingui/core/macro";
import { useQuery } from "@tanstack/react-query";
import { staffRequest } from "../../../lib/api";
import { limitLabel } from "../platformSpaces/limitCopy";
import { limitAmount } from "../platformSpaces/LimitRowView";

// Hand-written until the OpenAPI snapshot is regenerated (decision 234 addendum 3).
export type AllowanceArea = "inventory" | "machines" | "events" | "bookings" | "members" | "shop" | "staff" | "qr" | "devices" | "donations" | (string & {});
export type AllowanceLevel = "ok" | "warning" | "limit";
export type AllowanceRow = {
  key: string; label: string; unit: "bytes" | "count" | "amount" | "per_minute" | (string & {}); limit: number; used: number | null;
  remaining: number | null; percent: number | null; level: AllowanceLevel; areas: AllowanceArea[];
};
export type StaffAllowances = { makerspace_id: number; areas: AllowanceArea[]; rows: AllowanceRow[] };

export const allowancesKey = (makerspaceId: number) => ["staff-allowances", makerspaceId] as const;

/** One read per space: the server already narrows rows to what this person manages (#224). */
export function useStaffAllowances(makerspaceId: number) {
  return useQuery({
    queryKey: allowancesKey(makerspaceId), retry: false, staleTime: 5 * 60_000,
    queryFn: () => staffRequest<StaffAllowances>(`/admin/makerspace/${makerspaceId}/allowances`),
  });
}

/** KB/MB/GB for bytes, "N a minute" for a rate, grouped digits otherwise (one formatter with the limits console). */
export function amount(value: number, unit: AllowanceRow["unit"]) {
  return limitAmount({ unit }, value);
}

/** The plain sentence a full allowance shows, also used as a blocked button's reason. */
export function limitReachedText(row: AllowanceRow) {
  return t`${limitLabel(row.key, row.label)}: this space has reached its limit of ${amount(row.limit, row.unit)}. Ask the platform operator to raise it.`;
}

/** The reason an action is blocked by a full allowance, or null when it is not. */
export function useLimitReached(makerspaceId: number, key: string) {
  const query = useStaffAllowances(makerspaceId);
  const rows = query.data?.rows;
  const row = Array.isArray(rows) ? rows.find(item => item.key === key) : undefined;
  return row && row.level === "limit" ? limitReachedText(row) : null;
}
