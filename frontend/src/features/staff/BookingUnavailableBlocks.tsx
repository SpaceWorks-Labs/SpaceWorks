import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { formatLocale } from "../../lib/format";
import { staffRequest } from "../../lib/api";

/** One `unavailable` row of the staff availability read (`busy_overlay`). Hand-typed until regeneration. */
export type StaffBusyBlock = {
  starts_at: string; ends_at: string;
  kind: "room_outage" | "machine_repair" | "closed";
  severity: "block" | "warn";
  reason: string;
};

const DAYS = 14; // the staff availability read answers at most 14 days at a time

function kindLabel(block: StaffBusyBlock) {
  if (block.kind === "machine_repair") return t`Machine under repair`;
  return block.severity === "warn" ? t`Room out of service (bookings still allowed)` : t`Room out of service`;
}

/** Room outages and machine repair over the next two weeks, beside the staff schedule.
 * Closed hours are left out: every night would be listed, and admission already refuses them. */
export function BookingUnavailableBlocks({ spaceId }: { spaceId: number }) {
  const [window] = useState(() => {
    const start = new Date(); start.setHours(0, 0, 0, 0);
    const end = new Date(start); end.setDate(end.getDate() + DAYS - 1);
    return { starts_at: start.toISOString(), ends_at: end.toISOString() };
  });
  const query = useQuery({
    queryKey: ["staff-booking-unavailable", spaceId, window.starts_at],
    queryFn: () => staffRequest<{ unavailable?: StaffBusyBlock[]; timezone: string }>(
      `/admin/spaces/${spaceId}/bookings/availability/?` + new URLSearchParams(window)),
    retry: false,
  });
  const blocks = (query.data?.unavailable ?? []).filter(block => block.kind !== "closed");
  if (!blocks.length) return null;
  const format = new Intl.DateTimeFormat(formatLocale(), { dateStyle: "medium", timeStyle: "short", timeZone: query.data?.timezone });
  return <section aria-label={t`Unavailable times`} className="grid gap-2">
    <h3 className="eyebrow">{t`Unavailable in the next two weeks`}</h3>
    <ul className="grid gap-2">{blocks.map(block => <li key={block.kind + block.starts_at}
      className="break-words rounded-lg border border-warn bg-warn-soft px-3 py-2 text-sm text-ink">
      <span className="mr-2 font-semibold">{kindLabel(block)}</span>
      <time className="tabular-nums" dateTime={block.starts_at}>{format.format(new Date(block.starts_at))} – {format.format(new Date(block.ends_at))}</time>
      {block.reason ? <span className="ml-2 text-muted">{block.reason}</span> : null}
    </li>)}</ul>
  </section>;
}
