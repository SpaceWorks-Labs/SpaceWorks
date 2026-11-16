import { t } from "@lingui/core/macro";
import { Clock } from "lucide-react";

import { formatNumber } from "../../lib/format";

/** Decision 221(d): plan hours applied to one booking quote (`bookings.included_hours.summarize`). */
export type IncludedHoursSummary = {
  kind: "booking" | "machine"; term_id: number | null; plan_name: string; term_ends_at: string; allowance_minutes: number;
  applied_minutes: number; applied_hours: string; remaining_minutes: number; remaining_hours: string;
  /** B13: "organization" when the hours came from an organization's hours bank rather than a member's plan term. */
  source?: "organization"; organization_id?: number; period_key?: string;
};

export const hoursText = (value: string | number) => formatNumber(Number(value), { maximumFractionDigits: 2 });

/** "N h included · X h left this term": the member, public and staff quotes all say the same. */
export function IncludedHoursLine({ info, className = "" }: { info: IncludedHoursSummary | null | undefined; className?: string }) {
  if (!info) return null;
  const used = hoursText(info.applied_hours);
  const left = hoursText(info.remaining_hours);
  return <p className={`flex items-center gap-2 text-ink ${className}`}>
    <Clock aria-hidden="true" className="h-4 w-4 shrink-0 text-muted" />
    <span><span className="tabular-nums">{info.applied_minutes > 0 ? t`${used} h included` : t`No included hours used`}</span>
      {" · "}<span className="tabular-nums">{info.source === "organization" ? t`${left} h left in the organization's bank` : t`${left} h left this term`}</span>
      <span className="text-muted">{t` (${info.plan_name})`}</span></span>
  </p>;
}
