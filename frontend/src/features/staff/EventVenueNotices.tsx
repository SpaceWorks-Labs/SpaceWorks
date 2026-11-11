import { t } from "@lingui/core/macro";

import { consoleSessionHref } from "../../lib/api/sessionContext";
import { VenueConflictList, type VenueConflict } from "./EventVenueConflicts";
import { staffPathState, staffTabPath } from "./staffTabs";

type Props = {
  eventStatus?: string; coverage?: "covers" | "not_covered"; reservationState?: string;
  bookingId?: number | null; spaceId?: number; conflicts?: VenueConflict[];
};

/** The booking in the Bookings console, where staff reschedule or cancel it through the normal flow. */
function bookingHref(spaceId: number, bookingId: number) {
  const pathname = window.location.pathname;
  const guest = pathname.startsWith("/guest-admin");
  const base = staffTabPath("bookings", guest, staffPathState(pathname, guest).makerspaceSlug || null);
  return consoleSessionHref(`${base}?${new URLSearchParams({ space: String(spaceId), booking: String(bookingId), bookingTab: "requests" })}`);
}

/**
 * Decision 216: event drift and cancellation are flagged here and never applied. The booking
 * keeps its time, status and debt until staff change it in Bookings.
 */
export function EventVenueNotices({ eventStatus, coverage, reservationState, bookingId, spaceId, conflicts }: Props) {
  const live = reservationState === "pending" || reservationState === "confirmed";
  const cancelled = eventStatus === "cancelled";
  const drifted = !cancelled && live && coverage === "not_covered";
  const conflicted = !cancelled && live && Boolean(conflicts?.length);
  if (!cancelled && !drifted && !conflicted) return null;
  const link = bookingId && spaceId ? <a className="desk-button w-fit" href={bookingHref(spaceId, bookingId)}>{t`Open the booking in Bookings`}</a> : null;
  return <div className="grid gap-2 rounded-md border border-line p-2" role={cancelled || drifted ? "alert" : undefined}>
    {cancelled ? <p>{live ? t`This event was cancelled. The room booking and its charges are kept; cancel the booking in Bookings if the room is no longer needed.`
      : t`This event was cancelled. The room booking and its charges stay on record.`}</p> : null}
    {drifted ? <>
      <p><strong>{t`Room booking no longer covers the event time.`}</strong></p>
      <p>{t`Reschedule the booking in Bookings, or replace it once it is rejected or cancelled. Nothing is changed automatically.`}</p>
    </> : null}
    {conflicted ? <VenueConflictList conflicts={conflicts} /> : null}
    {link}
  </div>;
}
