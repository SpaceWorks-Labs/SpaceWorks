import { useState } from "react";
import { ListRow, Pagination, StatusBadge } from "../../components/ui";
import { QueryContent } from "../../components/layouts/LayoutFrame";
import { useSpaceBookings } from "./bookingsApi";
import { opsQueryState, opsStatusLabel } from "./opsPresentation";

type Props = { spaceId: number; onOpen: (id: number) => void };

/** Upcoming bookings grouped by day. It runs its OWN query (from the start of today, soonest first)
 * so the Requests tab's status/date filters and a `?booking=` deep link never narrow the schedule. */
export function BookingAgenda({ spaceId, onOpen }: Props) {
  const [from] = useState(() => { const today = new Date(); today.setHours(0, 0, 0, 0); return today.toISOString(); });
  const [page, setPage] = useState(1);
  const bookings = useSpaceBookings(spaceId, { starts_at: from }, page, "starts_at");
  const groups = new Map<string, NonNullable<typeof bookings.data>["results"]>();
  for (const booking of bookings.data?.results ?? []) {
    const day = new Date(booking.starts_at).toLocaleDateString(undefined, { weekday: "long", month: "long", day: "numeric", year: "numeric" });
    groups.set(day, [...(groups.get(day) ?? []), booking]);
  }
  return <section aria-label="Booking calendar" className="grid gap-4">
    <div><h2 className="title-panel">Schedule</h2><p className="mt-1 text-sm text-muted">Bookings from today onwards, grouped by day. Past bookings are under Requests.</p></div>
    <QueryContent state={opsQueryState(bookings, "the schedule")} isEmpty={bookings.data?.results.length === 0}
      empty={{ message: "No upcoming bookings. Create a booking to add one." }}>
      <div className="grid gap-6">{[...groups.entries()].map(([day, rows]) => <section key={day} className="grid gap-3">
        <h3 className="eyebrow">{day}</h3>
        {rows.map(booking => <ListRow key={booking.id} title={booking.name} identity={{ kind: "date", date: booking.starts_at }}
          meta={new Date(booking.starts_at).toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" }) + " – " +
            new Date(booking.ends_at).toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" })}
          onClick={() => onOpen(booking.id)} right={<div className="flex flex-wrap items-center gap-3">
            <StatusBadge status={booking.status} label={opsStatusLabel(booking.status)} /><button className="desk-button" onClick={() => onOpen(booking.id)}>Open booking</button>
          </div>} />)}
      </section>)}</div>
      {bookings.data ? <Pagination page={page} pageSize={24} count={bookings.data.count} totalPages={Math.ceil(bookings.data.count / 24)} onChange={setPage} /> : null}
    </QueryContent>
  </section>;
}
