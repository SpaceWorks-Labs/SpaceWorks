import { formatLocale } from "../../lib/format";
import { t } from "@lingui/core/macro";
import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import type { Dispatch, SetStateAction } from "react";
import { ListRow, OverflowMenu, Pagination, StatusBadge } from "../../components/ui";
import { QueryContent } from "../../components/layouts/LayoutFrame";
import { CustomAnswersView } from "../forms/CustomAnswersView";
import { PaymentReconcileActions } from "./PaymentReconcileActions";
import { BookingReservationEditor } from "./BookingReservationEditor";
import { opsQueryState, opsStatusLabel } from "./opsPresentation";
import { useSpaceBookings, type BookableSpace, type Booking, type BookingAction, type BookingFilters } from "./bookingsApi";
import { useUrlListState } from "../../lib/useUrlListState";
import { BookingCheckout } from "./BookingCheckout";
import { RequestedPrice } from "./pricing/RequestedPrice";

type Props = { makerspaceId: number; spaceId: number; space: BookableSpace;
  /** Payment reconciliation is a space-manager power; a resource grant alone does not carry it. */
  canReconcile: boolean; bookings: ReturnType<typeof useSpaceBookings>;
  list: ReturnType<typeof useUrlListState<{ page: string; status: string; starts_at: string; ends_at: string; ordering: string }>>;
  filters: BookingFilters; setFilter: <K extends keyof BookingFilters>(key: K, value: BookingFilters[K]) => void;
  page: number; setPage: Dispatch<SetStateAction<number>>; onAction: (booking: Booking, action: BookingAction) => void };
function bookingTime(booking: Booking) {
  const format = new Intl.DateTimeFormat(formatLocale(), { dateStyle: "medium", timeStyle: "short" });
  return format.format(new Date(booking.starts_at)) + " – " + format.format(new Date(booking.ends_at));
}
export function BookingRequests({ makerspaceId, spaceId, space, canReconcile, bookings, list, filters, setFilter, page, setPage, onAction }: Props) {
  const [, setParams] = useSearchParams();
  return <section aria-labelledby="space-bookings-title" className="grid gap-4">
    <div><h2 id="space-bookings-title" className="title-panel">{t`Bookings `}<span className="tabular-nums">({bookings.data?.count ?? 0})</span></h2>
      <p className="mt-1 text-sm text-muted">{t`Contact details and custom answers are staff-only.`}</p></div>
    {filters.booking_id ? <button className="desk-button w-fit" onClick={() => setParams(current => {
      const next = new URLSearchParams(current); next.delete("booking"); return next;
    })}>{t`Show all bookings`}</button> : null}
    <label className="grid gap-1 text-sm">{t`Sort`}<select className="desk-input" value={list.values.ordering}
      onChange={event => list.setFilter("ordering", event.target.value)}>
      <option value="starts_at">{t`Starts first`}</option><option value="-starts_at">{t`Starts last`}</option><option value="created_at">{t`Created first`}</option>
    </select></label>
    {/* Date-time pickers need ~14rem; three abreast only once the page is wide enough for that. */}
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
      <label className="grid gap-1 text-sm">{t`Status`}<select className="desk-input" value={filters.status ?? ""}
        onChange={event => setFilter("status", event.target.value as BookingFilters["status"])}>
        <option value="">{t`All statuses`}</option>{["pending", "confirmed", "rejected", "cancelled", "completed", "no_show"].map(status =>
          <option key={status} value={status}>{status === "no_show" ? t`No-show` : status[0].toUpperCase() + status.slice(1)}</option>)}
      </select></label>
      <label className="grid gap-1 text-sm">{t`Starts after`}<input className="desk-input w-full min-w-0" type="datetime-local" value={filters.starts_at ?? ""} onChange={event => setFilter("starts_at", event.target.value)} /></label>
      <label className="grid gap-1 text-sm">{t`Ends before`}<input className="desk-input w-full min-w-0" type="datetime-local" value={filters.ends_at ?? ""} onChange={event => setFilter("ends_at", event.target.value)} /></label>
    </div>
    <QueryContent state={opsQueryState(bookings, "bookings")} isEmpty={bookings.data?.results.length === 0}
      empty={{ message: t`No matching bookings. Change the filters or create a booking.` }}>
      <div className="grid gap-3">{bookings.data?.results.map(booking => <article className="rounded-xl border border-line bg-panel" key={booking.id}>
        <ListRow title={booking.name} identity={{ kind: "date", date: booking.starts_at }} meta={bookingTime(booking)}
          right={<StatusBadge status={booking.status} label={opsStatusLabel(booking.status)} />} />
        <div className="grid gap-3 p-4">
          <div className="text-sm"><a className="flex min-h-11 items-center break-all hover:underline" href={"mailto:" + booking.email}>{booking.email}</a>
            <a className="flex min-h-11 items-center text-muted hover:underline" href={"tel:" + booking.phone}>{booking.phone}</a></div>
          <BookingAnswers booking={booking} />
          <RequestedPrice booking={booking} />
          <BookingCheckout makerspaceId={makerspaceId} spaceId={spaceId} booking={booking} />
          {canReconcile ? <PaymentReconcileActions makerspaceId={makerspaceId} payment={booking.payment}
            invalidateKeys={[["booking-space", spaceId, "bookings"], ["booking-space", spaceId]]} /> : null}
          {space.staff_tools_enabled ? <BookingReservationEditor key={`${booking.id}-${booking.starts_at}-${JSON.stringify(booking.custom_answers)}-${booking.note}`} space={space} booking={booking} /> : null}
          <BookingActions undoEnabled={space.staff_tools_enabled} booking={booking} onAction={action => onAction(booking, action)} />
        </div>
      </article>)}</div>
      {bookings.data ? <Pagination page={page} pageSize={24} count={bookings.data.count} totalPages={Math.ceil(bookings.data.count / 24)} onChange={setPage} /> : null}
    </QueryContent>
  </section>;
}
function BookingActions({ booking, onAction, undoEnabled }: { booking: Booking; undoEnabled?: boolean; onAction: (action: BookingAction) => void }) {
  const ended = new Date(booking.ends_at) <= new Date();
  // An arrived booker has used the slot: it can still complete, but no longer cancel or no-show.
  const arrived = Boolean(booking.arrived_at);
  const restorable = undoEnabled && booking.restore_until && new Date(booking.restore_until) > new Date();
  const primary = restorable ? { label: t`Undo cancellation`, action: "restore" as const }
    : booking.status === "pending" ? { label: t`Approve`, action: "approve" as const }
    : booking.status === "confirmed" && ended ? { label: t`Complete`, action: "complete" as const } : undefined;
  const cancel = { label: t`Cancel`, onClick: () => onAction("cancel"), confirms: true, tone: "danger" as const };
  const overflow = booking.status === "pending" ? [{ label: t`Reject`, onClick: () => onAction("reject"), confirms: true, tone: "danger" as const }, ...(arrived ? [] : [cancel])]
    : booking.status === "confirmed" ? [
      ...(arrived ? [] : [cancel]),
      ...(ended && !arrived ? [{ label: t`No-show`, onClick: () => onAction("no-show"), confirms: true }] : []),
    ] : [];
  return <div className="flex flex-wrap items-center justify-end gap-3">
    {primary ? <button className="desk-button" type="button" onClick={() => onAction(primary.action)}>{primary.label}</button> : null}
    {overflow.length ? <OverflowMenu label={"Actions for " + booking.name} actions={overflow} /> : null}
  </div>;
}


function BookingAnswers({ booking }: { booking: Booking }) {
  const [open, setOpen] = useState(false);
  return <div className="rounded-lg border border-line p-3">
    <button className="desk-button-ghost" type="button" aria-expanded={open} onClick={() => setOpen(!open)}>{t`View custom answers`}</button>
    {open ? <CustomAnswersView snapshot={booking.custom_answers} /> : null}
  </div>;
}
