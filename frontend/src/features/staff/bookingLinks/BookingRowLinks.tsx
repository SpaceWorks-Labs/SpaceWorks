import { t } from "@lingui/core/macro";

import { RouteLink } from "../../../components/ui/RouteLink";
import { linkedEventText } from "../BookingAgenda";
import type { Booking } from "../bookingsApi";
import { useCrossLink } from "../crossLinks/staffHref";

/**
 * EB8, EB9, BK2: a booking's links out — the event it holds the room for, the member who asked
 * for it, and incidents recorded against it. Each appears only when the viewer can open that area;
 * otherwise the event keeps its plain label and the others are left out (decision 224).
 */
export function BookingRowLinks({ booking }: { booking: Booking }) {
  const link = useCrossLink();
  const event = booking.linked_event;
  const eventHref = event?.kind === "event" && event.event_id ? link("events", { event: event.event_id }) : undefined;
  const memberHref = booking.member_id ? link("members", { member: booking.member_id }) : undefined;
  const incidentsHref = link("incidents", { booking: booking.id });
  if (!event && !memberHref && !incidentsHref) return null;
  return <div className="flex min-w-0 flex-wrap items-center gap-x-4 gap-y-2 text-sm">
    {event ? eventHref ? <RouteLink className="font-semibold underline" href={eventHref}>{linkedEventText(event)}</RouteLink>
      : <span>{linkedEventText(event)}</span> : null}
    {memberHref ? <RouteLink className="underline" href={memberHref}>{t`Member activity`}</RouteLink> : null}
    {incidentsHref ? <RouteLink className="underline" href={incidentsHref}>{t`Incidents`}</RouteLink> : null}
  </div>;
}
