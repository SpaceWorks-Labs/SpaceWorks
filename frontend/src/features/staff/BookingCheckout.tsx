import { t } from "@lingui/core/macro";
import { useState } from "react";

import { StatusPill } from "../../components/ui";
import { DepartureForm, DepartureSummary } from "../bookings/DepartureForm";
import { useRecordDeparture } from "./bookingQueueApi";
import type { Booking } from "./bookingsApi";

const CHECKOUT_OPENS_MS = 30 * 60 * 1000;

/** Booking history on a staff request card: decision reason, check-out remark, and staff check-out. */
export function BookingCheckout({ makerspaceId, spaceId, booking }: { makerspaceId: number; spaceId: number; booking: Booking }) {
  const [open, setOpen] = useState(false);
  const departures = booking.departures ?? [];
  const started = Date.now() >= new Date(booking.starts_at).getTime() - CHECKOUT_OPENS_MS;
  const canRecord = !booking.departed_at && !departures.length && started
    && (booking.status === "confirmed" || booking.status === "completed");
  if (!booking.decision_reason && !departures.length && !canRecord) return null;
  return (
    <div className="grid gap-2 rounded-lg border border-line p-3">
      {booking.decision_reason ? <p className="text-sm"><span className="font-semibold">{t`Reason given to the requester:`}</span> {booking.decision_reason}</p> : null}
      {departures.map(departure => <DepartureSummary key={departure.recorded_at} departure={departure} />)}
      {booking.open_issue_id ? <StatusPill label={t`Issue open`} tone="warn" /> : null}
      {canRecord && !open ? <button type="button" className="desk-button w-fit min-h-11" onClick={() => setOpen(true)}>{t`Record check-out`}</button> : null}
      {canRecord && open ? <StaffCheckoutForm makerspaceId={makerspaceId} spaceId={spaceId} bookingId={booking.id} onDone={() => setOpen(false)} /> : null}
    </div>
  );
}

/** Mounted only when opened, so a request card holds no mutation until staff start a check-out. */
function StaffCheckoutForm({ makerspaceId, spaceId, bookingId, onDone }: { makerspaceId: number; spaceId: number; bookingId: number; onDone: () => void }) {
  const record = useRecordDeparture(makerspaceId, spaceId);
  return <DepartureForm audience="staff" pending={record.isPending} error={record.error?.message}
    onSubmit={input => record.mutate({ bookingId, ...input }, { onSuccess: onDone })} />;
}
