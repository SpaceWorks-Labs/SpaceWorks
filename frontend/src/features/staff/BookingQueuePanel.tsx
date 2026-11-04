import { useState } from "react";

import { ErrorBlock, ListRow, OverflowMenu, Pagination, SegmentedControl, StatusBadge } from "../../components/ui";
import { QueryContent } from "../../components/layouts/LayoutFrame";
import { opsQueryState, opsStatusLabel } from "./opsPresentation";
import { BookingDecisionDialog } from "./BookingDecisionDialog";
import { useBookingQueue, type QueueStatus } from "./bookingQueueApi";
import { useBookingAction, type Booking } from "./bookingsApi";
import { RequestedPrice } from "./pricing/RequestedPrice";

const STATUS_OPTIONS: { value: QueueStatus; label: string }[] = [
  { value: "pending", label: "Awaiting review" }, { value: "confirmed", label: "Confirmed" },
  { value: "rejected", label: "Rejected" }, { value: "cancelled", label: "Cancelled" }, { value: "all", label: "All" },
];

function when(booking: Booking) {
  const format = new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" });
  return `${format.format(new Date(booking.starts_at))} – ${format.format(new Date(booking.ends_at))}`;
}

/** The Requests queue: every booking awaiting review across the spaces this person manages. */
export function BookingQueuePanel({ makerspaceId, status, onStatus, onOpenBooking }: {
  makerspaceId: number; status: QueueStatus; onStatus: (status: QueueStatus) => void;
  onOpenBooking: (booking: Booking) => void;
}) {
  const [page, setPage] = useState(1);
  const queue = useBookingQueue(makerspaceId, status, page);
  const action = useBookingAction(makerspaceId);
  const [rejecting, setRejecting] = useState<Booking | null>(null);
  const [actingOn, setActingOn] = useState<number | null>(null);
  const approve = (booking: Booking) => { setActingOn(booking.id); action.mutate({ bookingId: booking.id, action: "approve" }, { onSettled: () => setActingOn(null) }); };
  const data = queue.data;
  return (
    <section aria-labelledby="booking-queue-title" className="grid gap-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 id="booking-queue-title" className="title-panel">Requests <span className="tabular-nums">({data?.count ?? 0})</span></h2>
          <p className="mt-1 text-sm text-muted">Approve or decline booking requests across all your spaces. Requesters are notified either way.</p>
        </div>
        <SegmentedControl label="Request status" value={status} options={STATUS_OPTIONS}
          onChange={value => { onStatus(value as QueueStatus); setPage(1); }} />
      </div>
      {action.error ? <ErrorBlock error={action.error} /> : null}
      <QueryContent state={opsQueryState(queue, "booking requests")} isEmpty={data?.results.length === 0}
        empty={{ message: status === "pending" ? "Nothing to review. New booking requests appear here." : "No bookings match this filter." }}>
        <ul className="grid gap-3">
          {data?.results.map(booking => (
            <li key={booking.id}>
              <ListRow title={booking.name} identity={{ kind: "date", date: booking.starts_at }}
                meta={<>{booking.space_name ?? "Space"} · {when(booking)}
                  {booking.decision_reason ? <span className="mt-1 block">Reason: {booking.decision_reason}</span> : null}
                  <RequestedPrice booking={booking} /></>}
                onClick={() => onOpenBooking(booking)}
                right={<div className="flex flex-wrap items-center justify-end gap-2">
                  <StatusBadge status={booking.status} label={opsStatusLabel(booking.status)} />
                  {booking.status === "pending" ? <>
                    <button type="button" className="desk-button-brand min-h-11" disabled={action.isPending && actingOn === booking.id}
                      onClick={() => approve(booking)}>{action.isPending && actingOn === booking.id ? "Approving…" : "Approve"}</button>
                    <OverflowMenu label={`More actions for ${booking.name}`} actions={[
                      { label: "Reject with reason", tone: "danger", onClick: () => setRejecting(booking) },
                      { label: "Open in space", onClick: () => onOpenBooking(booking) },
                    ]} />
                  </> : <button type="button" className="desk-button-ghost min-h-11" onClick={() => onOpenBooking(booking)}>Open</button>}
                </div>} />
            </li>
          ))}
        </ul>
        {data && data.count > 24 ? <Pagination page={page} pageSize={24} count={data.count} totalPages={Math.ceil(data.count / 24)} onChange={setPage} /> : null}
      </QueryContent>
      <BookingDecisionDialog key={rejecting?.id ?? "none"} open={rejecting !== null} action="reject" bookerName={rejecting?.name ?? ""}
        pending={action.isPending} onCancel={() => setRejecting(null)}
        onConfirm={reason => rejecting && action.mutate({ bookingId: rejecting.id, action: "reject", reason }, { onSettled: () => setRejecting(null) })} />
    </section>
  );
}
