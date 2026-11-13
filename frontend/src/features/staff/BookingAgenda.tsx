import { formatLocale } from "../../lib/format";
import { t } from "@lingui/core/macro";
import { useState } from "react";
import { ListRow, Pagination, StatusBadge } from "../../components/ui";
import { QueryContent } from "../../components/layouts/LayoutFrame";
import { useSpaceBookings, type LinkedEventLabel } from "./bookingsApi";
import { opsQueryState, opsStatusLabel } from "./opsPresentation";
import { BookingUnavailableBlocks } from "./BookingUnavailableBlocks";
import { RouteLink } from "../../components/ui/RouteLink";
import { useCrossLink } from "./crossLinks/staffHref";

type Props = { spaceId: number; onOpen: (id: number) => void };

/** Decision 216: a booking holding the room for an event; the title only when the viewer may see it. */
export function linkedEventText(label: LinkedEventLabel | null | undefined) {
  if (!label) return "";
  if (label.kind === "reserved") return t`Reserved`;
  return label.event_status === "cancelled" ? t`Event (cancelled): ${label.title ?? ""}` : t`Event: ${label.title ?? ""}`;
}

/** Upcoming bookings grouped by day. It runs its OWN query (from the start of today, soonest first)
 * so the Requests tab's status/date filters and a `?booking=` deep link never narrow the schedule. */
export function BookingAgenda({ spaceId, onOpen }: Props) {
  const [from] = useState(() => { const today = new Date(); today.setHours(0, 0, 0, 0); return today.toISOString(); });
  const [page, setPage] = useState(1);
  const bookings = useSpaceBookings(spaceId, { starts_at: from }, page, "starts_at");
  const crossLink = useCrossLink();
  // A23: the event a booking holds the room for opens in Events when the viewer may open that tab.
  const eventHref = (label: LinkedEventLabel | null | undefined) =>
    label?.kind === "event" && label.event_id ? crossLink("events", { event: label.event_id }) : undefined;
  const groups = new Map<string, NonNullable<typeof bookings.data>["results"]>();
  for (const booking of bookings.data?.results ?? []) {
    const day = new Date(booking.starts_at).toLocaleDateString(formatLocale(), { weekday: "long", month: "long", day: "numeric", year: "numeric" });
    groups.set(day, [...(groups.get(day) ?? []), booking]);
  }
  return <section aria-label={t`Booking calendar`} className="grid gap-4">
    <div><h2 className="title-panel">{t`Schedule`}</h2><p className="mt-1 text-sm text-muted">{t`Bookings from today onwards, grouped by day. Past bookings are under Requests.`}</p></div>
    <BookingUnavailableBlocks spaceId={spaceId} />
    <QueryContent state={opsQueryState(bookings, "the schedule")} isEmpty={bookings.data?.results.length === 0}
      empty={{ message: t`No upcoming bookings. Create a booking to add one.` }}>
      <div className="grid gap-6">{[...groups.entries()].map(([day, rows]) => <section key={day} className="grid gap-3">
        <h3 className="eyebrow">{day}</h3>
        {rows.map(booking => <ListRow key={booking.id} title={booking.name} identity={{ kind: "date", date: booking.starts_at }}
          meta={new Date(booking.starts_at).toLocaleTimeString(formatLocale(), { hour: "numeric", minute: "2-digit" }) + " – " +
            new Date(booking.ends_at).toLocaleTimeString(formatLocale(), { hour: "numeric", minute: "2-digit" }) +
            (booking.linked_event ? " · " + linkedEventText(booking.linked_event) : "")}
          onClick={() => onOpen(booking.id)} right={<div className="flex flex-wrap items-center gap-3">
            {eventHref(booking.linked_event) ? <RouteLink className="text-sm font-semibold underline" href={eventHref(booking.linked_event)!}>{t`Open event`}</RouteLink> : null}
            <StatusBadge status={booking.status} label={opsStatusLabel(booking.status)} /><button className="desk-button" onClick={() => onOpen(booking.id)}>{t`Open booking`}</button>
          </div>} />)}
      </section>)}</div>
      {bookings.data ? <Pagination page={page} pageSize={24} count={bookings.data.count} totalPages={Math.ceil(bookings.data.count / 24)} onChange={setPage} /> : null}
    </QueryContent>
  </section>;
}
