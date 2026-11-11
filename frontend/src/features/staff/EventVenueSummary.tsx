import { t } from "@lingui/core/macro";

import { StatusPill } from "../../components/ui";
import { RouteLink } from "../../components/ui/RouteLink";
import { useCrossLink } from "./crossLinks/staffHref";
import { useEventVenue, venueStateText, venueWarningText, type VenueStateName } from "./eventVenueApi";

const TONES = { none: "neutral", confirmed: "success", pending: "warn", blocked: "danger" } as const;

export function venueStatusLabel(state: VenueStateName) {
  return { none: t`No room`, confirmed: t`Room confirmed`, pending: t`Room pending`, blocked: t`Room needs attention` }[state];
}

/**
 * Decision 223 G6: the venue as everyone told about it sees it -- co-organizers, per-event
 * delegates and staff without booking authority included. Read-only: no booker, price or
 * write action. Staff who may manage the booking get the full panel below it instead.
 */
export function EventVenueSummary({ makerspaceId, eventId, active = true }: { makerspaceId: number; eventId: number; active?: boolean }) {
  const venue = useEventVenue(makerspaceId, eventId, active);
  const crossLink = useCrossLink();
  if (venue.isPending) return <p role="status" className="text-sm text-muted">{t`Checking the venue…`}</p>;
  // 404/403: Bookings or Events off, or no publish authority on this event -- show nothing.
  if (venue.isError || !venue.data) return null;
  const panel = venue.data;
  // A23: the room booking opens in Bookings for anyone who may open that tab; others keep the text.
  const bookingHref = panel.venue.booking_id && panel.venue.space_id
    ? crossLink("bookings", { space: panel.venue.space_id, booking: panel.venue.booking_id, bookingTab: "requests" }) : undefined;
  if (panel.venue.state === "none" && !panel.warnings.length && !panel.can_manage_booking) return null;
  return <section aria-labelledby={`event-venue-${eventId}`} className="grid gap-2 rounded-lg border border-line p-3 text-sm">
    <div className="flex flex-wrap items-center justify-between gap-2">
      <h3 id={`event-venue-${eventId}`} className="title-section">{t`Venue`}</h3>
      <StatusPill label={venueStatusLabel(panel.venue.state)} tone={TONES[panel.venue.state]} />
    </div>
    <p role={panel.venue.state === "blocked" ? "alert" : undefined}>{venueStateText(panel.venue)}</p>
    {bookingHref ? <RouteLink className="w-fit font-semibold underline" href={bookingHref}>{t`Open the room booking`}</RouteLink> : null}
    {panel.warnings.length ? <ul className="grid list-disc gap-1 pl-5" aria-label={t`Venue warnings`}>
      {panel.warnings.map(warning => <li key={warning.code}>{venueWarningText(warning)}</li>)}
    </ul> : null}
    {!panel.can_manage_booking ? <p className="text-muted">{panel.venue.state === "blocked"
      ? t`Ask a Booking Manager to replace the room booking, or publish without a room.`
      : panel.venue.coverage === "not_covered" ? t`Ask a Booking Manager to move the room booking.`
      : t`Only staff who manage bookings can change the room.`}</p> : null}
  </section>;
}
