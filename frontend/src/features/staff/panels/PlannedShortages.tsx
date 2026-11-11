import { t } from "@lingui/core/macro";

import { RouteLink } from "../../../components/ui/RouteLink";
import { formatDateTime } from "../../../lib/format";
import { staffTabPath } from "../staffTabs";
import { useStaffGet } from "./shared";

export type PlannedShortage = {
  subject_kind: "event" | "booking"; subject_id: number; subject_title: string; starts_at: string;
  product_id: number; product_name: string; remaining_planned: number; available_quantity: number;
  shortage_quantity: number; replenishment_quantity: number;
};

/** Open item C25: upcoming events and bookings whose planned consumables outrun stock. */
export function PlannedShortages({ makerspaceId, slug, enabledModules }: {
  makerspaceId: number; slug: string; enabledModules: readonly string[];
}) {
  const shortages = useStaffGet<PlannedShortage[]>(["consumables", makerspaceId, "planned-shortages"],
    `/admin/makerspace/${makerspaceId}/consumables/planned-shortages`);
  const href = (row: PlannedShortage) => row.subject_kind === "event"
    ? `${staffTabPath("events", false, slug)}?event=${row.subject_id}`
    : `${staffTabPath("bookings", false, slug)}?booking=${row.subject_id}`;
  return <section className="desk-panel grid gap-3 p-4" aria-labelledby="planned-shortages-title">
    <div>
      <h2 id="planned-shortages-title" className="title-panel">{t`Needed for upcoming activities`}</h2>
      <p className="text-sm text-muted">{t`Events and bookings in the next 30 days that plan to use more than is in stock.`}</p>
    </div>
    {shortages.isPending ? <p role="status" className="text-sm text-muted">{t`Checking upcoming activities…`}</p> : null}
    {shortages.isError ? <p role="alert" className="text-sm text-danger">{t`Upcoming activity needs could not be loaded. Try again later.`}</p> : null}
    {shortages.data && !shortages.data.length ? <p className="text-sm text-muted">{t`Nothing planned is short. Upcoming events and bookings have enough stock.`}</p> : null}
    {shortages.data?.length ? <ul className="grid gap-2 text-sm">
      {shortages.data.map(row => <li key={`${row.subject_kind}-${row.subject_id}-${row.product_id}`}
        className="grid gap-1 rounded-lg border border-line p-3">
        <span className="font-semibold text-ink break-words">{row.product_name}</span>
        <span className="text-muted">
          {row.subject_kind === "event" && enabledModules.includes("events")
            ? <RouteLink className="font-semibold text-accent-ink underline" href={href(row)}>{row.subject_title}</RouteLink>
            : row.subject_kind === "booking" && enabledModules.includes("bookings")
              ? <RouteLink className="font-semibold text-accent-ink underline" href={href(row)}>{t`Booking: ${row.subject_title}`}</RouteLink>
              : row.subject_title}
          {" · "}{formatDateTime(row.starts_at)}
        </span>
        <span className="tabular-nums">
          {row.shortage_quantity > 0
            ? t`Short by ${row.shortage_quantity} (needs ${row.remaining_planned}, ${row.available_quantity} in stock)`
            : t`Enough for this activity, but stock falls to the reorder level`}
          {row.replenishment_quantity > 0 ? <> · {t`Suggested reorder: ${row.replenishment_quantity}`}</> : null}
        </span>
      </li>)}
    </ul> : null}
  </section>;
}
