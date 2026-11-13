import { t } from "@lingui/core/macro";
import { useQuery } from "@tanstack/react-query";
import { Clock } from "lucide-react";

import { staffRequest } from "../../../lib/api";
import { formatDate } from "../../../lib/format";
import { hoursText } from "../../payments/IncludedHoursLine";

/** C26: hand-typed from backend/apps/bookings/views_included_hours.py until the client is regenerated. */
export type IncludedHoursPool = {
  kind: "booking" | "machine"; term_id: number; plan_name: string; term_starts_at: string; term_ends_at: string;
  allowance_minutes: number; used_minutes: number; remaining_minutes: number;
};
export type MemberIncludedHoursBalance = { member_id: number; enabled: boolean; pools: IncludedHoursPool[] };

export const includedHoursKey = (makerspaceId: number, userId: number) => ["included-hours", makerspaceId, userId] as const;

export function useMemberIncludedHours(makerspaceId: number, userId: number) {
  return useQuery({
    queryKey: includedHoursKey(makerspaceId, userId),
    retry: false,
    queryFn: ({ signal }) => staffRequest<MemberIncludedHoursBalance>(
      `/admin/makerspace/${makerspaceId}/members/${userId}/included-hours`, { signal }),
  });
}

const poolLabel = (kind: IncludedHoursPool["kind"]) => (kind === "machine" ? t`Machine time` : t`Room bookings`);

/**
 * C26: the member's included plan hours this term, from the same ledger the booking quote reads, so
 * the line can never disagree with a price. It disappears entirely when nothing applies: bookings or
 * membership off (`enabled: false`), no hours on the plan, or a viewer the server refuses (403/404),
 * and a failed read is never shown as "0 h left".
 */
export function StaffIncludedHours({ makerspaceId, userId, className = "" }: { makerspaceId: number; userId: number; className?: string }) {
  const balance = useMemberIncludedHours(makerspaceId, userId);
  const pools = (balance.data?.enabled ? balance.data.pools : []).filter(pool => pool.allowance_minutes > 0);
  if (!pools.length) return null;
  return <section className={`grid min-w-0 gap-1 ${className}`} aria-label={t`Included hours`}>
    <h3 className="title-section">{t`Included hours`}</h3>
    <ul className="grid gap-1 text-sm">{pools.map(pool => {
      const left = hoursText(pool.remaining_minutes / 60);
      const total = hoursText(pool.allowance_minutes / 60);
      const label = poolLabel(pool.kind);
      const ends = formatDate(pool.term_ends_at);
      return <li key={`${pool.term_id}-${pool.kind}`} className="flex min-w-0 flex-wrap items-center gap-2 text-ink">
        <Clock aria-hidden="true" className="h-4 w-4 shrink-0 text-muted" />
        <span className="font-semibold">{label}</span>
        <span className="tabular-nums">{t`${left} of ${total} h left this term`}</span>
        <span className="text-muted">{t`${pool.plan_name} · resets after ${ends}`}</span>
      </li>;
    })}</ul>
  </section>;
}
