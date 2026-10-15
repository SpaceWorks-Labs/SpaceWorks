import { EmptyState, ListRow, StatusPill, Tabs, OverflowMenu, ErrorBlock } from "../../components/ui";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { BookingReschedule } from "./BookingReschedule";
import { BookingCalendar } from "./BookingCalendar";
import { memberRequest } from "../../lib/api";
import { personalRecipientKey } from "../notifications/personalQueryKeys";

export type MemberBooking = {
  public_token: string;
  space_name: string;
  timezone: string;
  starts_at: string;
  ends_at: string;
  status: string;
  cancellation_cutoff_at: string;
  can_cancel: boolean;
};
type BookingPage = { count: number; next: string | null; previous: string | null; results: MemberBooking[] };

function dateLabel(value: string, timezone: string) {
  return new Intl.DateTimeFormat(undefined, { timeZone: timezone, dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}

export function MyBookings({ slug }: { slug: string }) {
  const recipient = personalRecipientKey();
  return <OwnBookings key={`${slug}:${recipient}`} slug={slug} recipient={recipient} />;
}

function OwnBookings({ slug, recipient }: { slug: string; recipient: number | "signed-out" }) {
  const [period, setPeriod] = useState<"upcoming" | "past">("upcoming");
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<MemberBooking | null>(null);
  const [moving, setMoving] = useState<MemberBooking | null>(null);
  const client = useQueryClient();
  const basePath = `/public/${encodeURIComponent(slug)}/my-bookings/`;
  const bookings = useQuery({
    queryKey: ["member", slug, "bookings", recipient, period, page],
    queryFn: () => memberRequest<BookingPage>(`${basePath}?period=${period}&page=${page}`),
    enabled: Boolean(slug), retry: false,
  });
  const cancel = useMutation({
    mutationFn: (token: string) => memberRequest<MemberBooking>(`${basePath}${encodeURIComponent(token)}/cancel/`, { method: "POST", body: JSON.stringify({}) }),
    onSuccess: async () => {
      setSelected(null);
      await Promise.all([
        client.invalidateQueries({ queryKey: ["member", slug] }),
        client.invalidateQueries({ queryKey: ["public-space-availability", slug] }),
      ]);
    },
  });
  const error = bookings.error ?? cancel.error;

  return <section className="desk-panel p-5" aria-labelledby="my-bookings-heading">
    <h2 className="title-panel" id="my-bookings-heading">My bookings</h2>
    <BookingCalendar key={`${slug}:${recipient}`} slug={slug} />
    <Tabs label="Booking period" activeKey={period} tabs={[{ key: "upcoming", label: "Upcoming", href: "#upcoming" }, { key: "past", label: "Past", href: "#past" }]} onChange={value => { setPeriod(value as "upcoming" | "past"); setPage(1); setSelected(null); setMoving(null); }}>
    {bookings.isLoading ? <p className="mt-3 text-sm text-muted" role="status">Loading bookings…</p> : null}
    {error ? <ErrorBlock error={error instanceof Error ? error : new Error("Couldn't load bookings. Try again.")} onRetry={bookings.isError ? () => void bookings.refetch() : undefined} /> : null}
    {bookings.data?.results.length === 0 ? <EmptyState message={period === "upcoming" ? "No upcoming bookings. Book a bench or room when you need one." : "No past bookings yet. Your visits will appear here."} /> : null}
    <ul className="mt-3 space-y-3">
      {bookings.data?.results.map(booking => <li key={booking.public_token}><ListRow title={booking.space_name} identity={{ kind: "date", date: booking.starts_at }}
        meta={<>{dateLabel(booking.starts_at, booking.timezone)} – {dateLabel(booking.ends_at, booking.timezone)} ({booking.timezone}){booking.can_cancel ? <span className="mt-1 block">Cancel before {dateLabel(booking.cancellation_cutoff_at, booking.timezone)}.</span> : null}</>}
        right={<div className="flex flex-wrap items-center gap-3"><StatusPill label={booking.status.replace(/_/g, " ")} tone={booking.status === "confirmed" ? "success" : "neutral"} />
          {booking.can_cancel ? <><button type="button" className="desk-button" disabled={cancel.isPending} onClick={() => { setSelected(null); setMoving(booking); }}>Reschedule booking</button>
          <OverflowMenu label="Booking actions" actions={[{ label: "Cancel booking", tone: "danger", onClick: () => { cancel.reset(); setMoving(null); setSelected(booking); } }]} /></> : null}</div>} /></li>)}
    </ul>
    {moving ? <BookingReschedule key={moving.public_token} booking={moving} slug={slug} onClose={() => setMoving(null)} /> : null}
    {selected ? <div className="mt-3 rounded-lg border border-warn p-3" aria-label="Confirm cancellation">
      <p className="text-sm">Cancel your booking for {selected.space_name}? Any pending charge will be voided. Contact staff about a refund for a paid booking.</p>
      <div className="mt-2 flex gap-2"><button type="button" className="desk-button-brand" disabled={cancel.isPending} onClick={() => cancel.mutate(selected.public_token)}>{cancel.isPending ? "Cancelling…" : "Confirm cancellation"}</button><button type="button" className="desk-button-ghost" disabled={cancel.isPending} onClick={() => setSelected(null)}>Keep booking</button></div>
    </div> : null}
    {bookings.data && (bookings.data.next || bookings.data.previous) ? <div className="mt-3 flex items-center gap-3">
      <button type="button" className="desk-button-brand" disabled={!bookings.data.previous || bookings.isFetching} onClick={() => setPage((value) => value - 1)}>Previous</button>
      <span className="text-sm">Page {page}</span>
      <button type="button" className="desk-button-brand" disabled={!bookings.data.next || bookings.isFetching} onClick={() => setPage((value) => value + 1)}>Next</button>
    </div> : null}
    </Tabs>
  </section>;
}
