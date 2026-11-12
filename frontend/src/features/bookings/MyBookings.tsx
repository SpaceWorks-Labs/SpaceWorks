import { formatLocale } from "../../lib/format";
import { t } from "@lingui/core/macro";
import { EmptyState, ListRow, StatusPill, Tabs, OverflowMenu, ErrorBlock, PagePager } from "../../components/ui";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { BookingReschedule } from "./BookingReschedule";
import { BookingConfirmation } from "./BookingConfirmation";
import { bookingStatusLabel } from "./bookingStatusLabel";
import { BookingCalendar } from "./BookingCalendar";
import { memberRequest } from "../../lib/api";
import { personalRecipientKey } from "../notifications/personalQueryKeys";
import { DepartureForm, OUTCOME_LABELS, type DepartureInput, type DepartureOutcome } from "./DepartureForm";
import { ReportProblem } from "../repairs/ReportProblem";
import { LogoLoader } from "../../components/LogoLoader";

export type MemberBooking = {
  public_token: string;
  space_name: string;
  timezone: string;
  starts_at: string;
  ends_at: string;
  status: string;
  cancellation_cutoff_at: string;
  can_cancel: boolean;
  confirmation_available?: boolean;
  /** Phase 2 (hand-typed until the client is regenerated). */
  decision_reason?: string;
  departed_at?: string | null;
  can_checkout?: boolean;
  departure_outcome?: DepartureOutcome | null;
  /** Books one machine's time: a report goes to that machine (decision 220(d)1; hand-typed). */
  machine_time?: boolean;
  /** Decision 223 (m): the event this room is held for (title only when visible to you), else null. */
  hosts_event?: { kind: "event" | "reserved"; title?: string } | null;
};

function hostedEventText(label: NonNullable<MemberBooking["hosts_event"]>) {
  return label.kind === "event" && label.title ? t`This room is held for the event “${label.title}”.` : t`This room is held for an event.`;
}
type BookingPage = { count: number; next: string | null; previous: string | null; results: MemberBooking[] };

function dateLabel(value: string, timezone: string) {
  return new Intl.DateTimeFormat(formatLocale(), { timeZone: timezone, dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}

/** `canReport` is room reporting (`bookings.issue_reporting`), `canReportMachines` machine
 * reporting (`machines.issue_reporting`): the server reports a machine-time booking on its
 * machine while that is on, and on the room otherwise. */
export function MyBookings({ slug, canReport = false, canReportMachines = false, initialPeriod = "upcoming" }: { slug: string; canReport?: boolean; canReportMachines?: boolean; initialPeriod?: "upcoming" | "past" }) {
  const recipient = personalRecipientKey();
  return <OwnBookings key={`${slug}:${recipient}:${initialPeriod}`} slug={slug} recipient={recipient} canReport={canReport} canReportMachines={canReportMachines} initialPeriod={initialPeriod} />;
}

function OwnBookings({ slug, recipient, canReport, canReportMachines, initialPeriod }: { slug: string; recipient: number | "signed-out"; canReport: boolean; canReportMachines: boolean; initialPeriod: "upcoming" | "past" }) {
  const reportable = (booking: MemberBooking) => (booking.machine_time ? canReportMachines || canReport : canReport)
    && ["confirmed", "completed", "no_show"].includes(booking.status);
  const [period, setPeriod] = useState<"upcoming" | "past">(initialPeriod);
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<MemberBooking | null>(null);
  const [confirmation, setConfirmation] = useState<string | null>(null);
  const [moving, setMoving] = useState<MemberBooking | null>(null);
  const [checkingOut, setCheckingOut] = useState<MemberBooking | null>(null);
  const client = useQueryClient();
  const basePath = `/public/${encodeURIComponent(slug)}/my-bookings/`;
  const bookings = useQuery({
    queryKey: ["member", slug, "bookings", recipient, period, page],
    queryFn: () => memberRequest<BookingPage>(`${basePath}?period=${period}&page=${page}`),
    enabled: Boolean(slug), retry: false,
  });
  const cancel = useMutation({
    // The booker confirms cancelling an event's room (409 `booking_hosts_event` otherwise).
    mutationFn: ({ token, confirmEventRoom }: { token: string; confirmEventRoom: boolean }) => memberRequest<MemberBooking>(`${basePath}${encodeURIComponent(token)}/cancel/`, { method: "POST", body: JSON.stringify(confirmEventRoom ? { confirm_event_room: true } : {}) }),
    onSuccess: async () => {
      setSelected(null);
      await Promise.all([
        client.invalidateQueries({ queryKey: ["member", slug] }),
        client.invalidateQueries({ queryKey: ["public-space-availability", slug] }),
      ]);
    },
  });
  const checkout = useMutation({
    mutationFn: ({ token, ...input }: DepartureInput & { token: string }) => memberRequest<MemberBooking>(
      `${basePath}${encodeURIComponent(token)}/checkout/`, { method: "POST", body: JSON.stringify(input) }),
    onSuccess: async () => { setCheckingOut(null); await client.invalidateQueries({ queryKey: ["member", slug] }); },
  });
  // A row that hosts an event, or a 409 that says so (the label can change after the list loaded).
  const refusal = cancel.error as { code?: string; body?: { event?: MemberBooking["hosts_event"] } } | null;
  const refusedHost = refusal?.code === "booking_hosts_event" ? refusal.body?.event ?? { kind: "reserved" as const } : null;
  const hostWarning = selected ? selected.hosts_event ?? refusedHost : null;
  const error = bookings.error ?? (refusedHost ? null : cancel.error);

  return <section className="desk-panel p-5" aria-labelledby="my-bookings-heading">
    <h2 className="title-panel" id="my-bookings-heading">{t`My bookings`}</h2>
    <BookingCalendar key={`${slug}:${recipient}`} slug={slug} />
    <Tabs label={t`Booking period`} activeKey={period} tabs={[{ key: "upcoming", label: t`Upcoming`, href: "#upcoming" }, { key: "past", label: t`Past`, href: "#past" }]} onChange={value => { setPeriod(value as "upcoming" | "past"); setPage(1); setSelected(null); setMoving(null); }}>
    {bookings.isLoading ? <LogoLoader label={t`Loading bookings…`} size={48} className="min-h-16 py-3" /> : null}
    {error ? <ErrorBlock error={error instanceof Error ? error : new Error(t`Couldn't load bookings. Try again.`)} onRetry={bookings.isError ? () => void bookings.refetch() : undefined} /> : null}
    {bookings.data?.results.length === 0 ? <EmptyState message={period === "upcoming" ? t`No upcoming bookings. Book a bench or room when you need one.` : t`No past bookings yet. Your visits will appear here.`} /> : null}
    <ul className="mt-3 space-y-3">
      {bookings.data?.results.map(booking => <li key={booking.public_token}><ListRow title={booking.space_name} identity={{ kind: "date", date: booking.starts_at }}
        meta={<>{dateLabel(booking.starts_at, booking.timezone)} – {dateLabel(booking.ends_at, booking.timezone)} ({booking.timezone}){booking.can_cancel ? <span className="mt-1 block">{t`Cancel before ${dateLabel(booking.cancellation_cutoff_at, booking.timezone)}.`}</span> : null}
          {booking.decision_reason ? <span className="mt-1 block">{t`Reason from staff: ${booking.decision_reason}`}</span> : null}
          {booking.departure_outcome ? <span className="mt-1 block">{t`Checked out: ${OUTCOME_LABELS[booking.departure_outcome]}`}</span> : null}
          {booking.hosts_event ? <span className="mt-1 block font-medium text-ink">{hostedEventText(booking.hosts_event)}</span> : null}</>}
        right={<div className="flex flex-wrap items-center gap-3"><StatusPill label={bookingStatusLabel(booking.status)} tone={booking.status === "confirmed" ? "success" : "neutral"} />
          {booking.confirmation_available ? <button type="button" className="desk-button" onClick={() => setConfirmation(booking.public_token)}>{t`View confirmation`}</button> : null}
          {booking.can_checkout ? <button type="button" className="desk-button" onClick={() => { checkout.reset(); setCheckingOut(booking); }}>{t`Check out`}</button> : null}
          {reportable(booking) ? <ReportProblem source={{ makerspace_slug: slug, booking_token: booking.public_token }} /> : null}
          {booking.can_cancel ? <><button type="button" className="desk-button" disabled={cancel.isPending} onClick={() => { setSelected(null); setMoving(booking); }}>{t`Reschedule booking`}</button>
          <OverflowMenu label={t`Booking actions`} actions={[{ label: t`Cancel booking`, tone: "danger", onClick: () => { cancel.reset(); setMoving(null); setSelected(booking); } }]} /></> : null}</div>} /></li>)}
    </ul>
    {checkingOut ? <div className="mt-3 rounded-lg border border-line p-3" aria-label={t`Check out of ${checkingOut.space_name}`}>
      <DepartureForm audience="member" submitLabel={t`Check out`} pending={checkout.isPending} error={checkout.error?.message}
        onSubmit={input => checkout.mutate({ token: checkingOut.public_token, ...input })} />
      <button type="button" className="desk-button-ghost mt-2 min-h-11" onClick={() => setCheckingOut(null)}>{t`Not now`}</button>
    </div> : null}
    {confirmation ? <BookingConfirmation key={confirmation} slug={slug} token={confirmation} onClose={() => setConfirmation(null)} /> : null}
    {moving ? <BookingReschedule key={moving.public_token} booking={moving} slug={slug} onClose={() => setMoving(null)} /> : null}
    {selected ? <div className="mt-3 rounded-lg border border-warn p-3" aria-label={t`Confirm cancellation`}>
      <p className="text-sm">{t`Cancel your booking for ${selected.space_name}? Any unpaid charge is voided. If you already paid, a refund request opens under the space's cancellation policy and staff decide it.`}</p>
      {hostWarning ? <p className="mt-2 text-sm font-medium text-warn-ink" role="alert">{t`${hostedEventText(hostWarning)} Cancelling removes the event's room; the organizers are told.`}</p> : null}
      <div className="mt-2 flex flex-wrap gap-2 [&>button]:flex-1 sm:[&>button]:flex-none"><button type="button" className="desk-button-brand" disabled={cancel.isPending} onClick={() => cancel.mutate({ token: selected.public_token, confirmEventRoom: Boolean(hostWarning) })}>{cancel.isPending ? t`Cancelling…` : hostWarning ? t`Cancel the event's room` : t`Confirm cancellation`}</button><button type="button" className="desk-button-ghost" disabled={cancel.isPending} onClick={() => setSelected(null)}>{t`Keep booking`}</button></div>
    </div> : null}
    {bookings.data ? <PagePager page={page} setPage={setPage} next={bookings.data.next} disabled={bookings.isFetching} /> : null}
    </Tabs>
  </section>;
}
