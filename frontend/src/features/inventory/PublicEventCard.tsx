import { StatusBadge, StatusPill } from "../../components/ui";
import { DateChip } from "../../components/ui/DateChip";
import { RouteLink } from "../../components/ui/RouteLink";
import { EventPrice } from "../events/EventPrice";
import type { PublicEventDetail } from "../events/eventTicketTypes";

/** Capacity 0 and null both mean "no cap" on the API. */
export function eventCapacityLabel(capacity: number | null) {
  return capacity ? String(capacity) : "Unlimited";
}

export function eventActionLabel(event: PublicEventDetail) {
  if (!event.registration_open) return "View event";
  return event.registration_requires_approval ? "Apply" : event.availability === "Full" ? "Join waitlist" : "Register";
}

export function registrationClosedLabel(event: PublicEventDetail) {
  return `Registration closed${event.effective_registration_cutoff_at ? ` · ${new Date(event.effective_registration_cutoff_at).toLocaleString()}` : ""}`;
}

type Props = { event: PublicEventDetail; href: string; time: string; calendarPending: boolean; calendarError?: string; onCalendar: () => void };

/** One public event: cover, status, description, price, capacity and availability, then the two actions. */
export function PublicEventCard({ event, href, time, calendarPending, calendarError, onCalendar }: Props) {
  return <article id={`event-${event.public_token}`} tabIndex={-1} className="min-w-0">
    <div className="desk-panel grid gap-4 overflow-hidden">
      {/* Decorative: the title already names the event. */}
      {event.image_url ? <img src={event.image_url} alt="" loading="lazy" className="h-44 w-full object-cover sm:h-52" /> : null}
      <div className={`grid gap-4 px-5 pb-5 ${event.image_url ? "" : "pt-5"}`}>
        <div className="flex flex-wrap items-start gap-4">
          <DateChip date={event.starts_at} />
          <div className="min-w-0 flex-1">
            <h3 className="title-section break-words"><RouteLink className="hover:underline" href={href}>{event.title}</RouteLink></h3>
            <p className="mt-1 text-sm text-muted"><time dateTime={event.starts_at}>{time}</time>{event.location ? ` · ${event.location}` : ""}</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <StatusBadge status={event.status} domain="event" />
            <StatusPill label={event.registration_open ? event.availability : registrationClosedLabel(event)}
              tone={event.registration_open ? event.availability === "Full" ? "warn" : "success" : "neutral"} />
          </div>
        </div>
        {event.description ? <p className="line-clamp-3 whitespace-pre-wrap text-sm leading-6 text-ink">{event.description}</p> : null}
        <dl className="flex flex-wrap gap-6 text-sm">
          <div><dt className="text-muted">Price</dt><dd><EventPrice inline amount={event.payment_amount} currency={event.currency} tickets={event.ticket_types} ticketRequired={event.ticket_selection_required} /></dd></div>
          <div><dt className="text-muted">Capacity</dt><dd className="font-semibold tabular-nums text-ink">{eventCapacityLabel(event.capacity)}</dd></div>
          <div><dt className="text-muted">Availability</dt><dd className="font-semibold text-ink">{event.availability}</dd></div>
        </dl>
        <div className="flex flex-wrap gap-2">
          <RouteLink className={event.registration_open ? "desk-button-brand" : "desk-button"} href={href}>{eventActionLabel(event)}</RouteLink>
          <button className="desk-button" type="button" disabled={calendarPending} onClick={onCalendar}>{calendarPending ? "Preparing…" : "Add to calendar"}</button>
        </div>
        {calendarError ? <p role="alert" className="text-sm text-danger">{calendarError}</p> : null}
      </div>
    </div>
  </article>;
}
