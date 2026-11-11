import { formatDateTime } from "../../lib/format";
import { t } from "@lingui/core/macro";
import { StatusBadge, StatusPill } from "../../components/ui";
import { DateChip } from "../../components/ui/DateChip";
import { RouteLink } from "../../components/ui/RouteLink";
import { EventCountdown } from "../events/EventCountdown";
import { EventPrice } from "../events/EventPrice";
import type { PublicEventDetail } from "../events/eventTicketTypes";

function eventStatusLabel(status: string) {
  if (status === "published") return t`Published`;
  if (status === "cancelled") return t`Cancelled`;
  if (status === "completed") return t`Completed`;
  if (status === "draft") return t`Draft`;
  return t`Status unknown`;
}

/** Capacity 0 and null both mean "no cap" on the API. */
export function eventCapacityLabel(capacity: number | null) {
  return capacity ? String(capacity) : t`Unlimited`;
}

export function eventActionLabel(event: PublicEventDetail) {
  if (!event.registration_open) return t`View event`;
  return event.registration_requires_approval ? t`Apply` : event.availability === "Full" ? t`Join waitlist` : t`Register`;
}

export function registrationClosedLabel(event: PublicEventDetail) {
  return t`Registration closed${event.effective_registration_cutoff_at ? ` · ${formatDateTime(event.effective_registration_cutoff_at)}` : ""}`;
}

// `showPrice` is false when event charges are off in this space (#184): no price line at all.
type Props = { event: PublicEventDetail; href: string; time: string; calendarPending: boolean; calendarError?: string; onCalendar: () => void; showPrice?: boolean };

/** One public event: cover, status, description, price, capacity and availability, then the two actions. */
export function PublicEventCard({ event, href, time, calendarPending, calendarError, onCalendar, showPrice = true }: Props) {
  return <article id={`event-${event.public_token}`} tabIndex={-1} className="min-w-0">
    <div className="desk-panel grid gap-4 overflow-hidden">
      {/* Decorative: the title already names the event. */}
      {event.image_url ? <img src={event.image_url} alt="" loading="lazy" className="h-44 w-full object-cover sm:h-52" /> : null}
      <div className={`grid gap-4 px-5 pb-5 ${event.image_url ? "" : "pt-5"}`}>
        <div className="flex flex-wrap items-start gap-4">
          <DateChip date={event.starts_at} />
          <div className="min-w-0 flex-1">
            <h3 className="break-words"><RouteLink className="title-section hover:underline" href={href}>{event.title}</RouteLink></h3>
            <p className="mt-1 break-words text-sm text-muted"><time dateTime={event.starts_at}>{time}</time>{event.location ? ` · ${event.location}` : ""}</p>
          </div>
          <div className="flex flex-wrap gap-2">
            {event.audience_label ? <StatusPill label={event.audience_label} tone="info" /> : null}
            <StatusBadge status={event.status} domain="event" label={eventStatusLabel(event.status)} />
            <StatusPill label={event.registration_open ? event.availability : registrationClosedLabel(event)}
              tone={event.registration_open ? event.availability === "Full" ? "warn" : "success" : "neutral"} />
          </div>
        </div>
        <EventCountdown startsAt={event.starts_at} endsAt={event.ends_at} />
        {event.description ? <p className="line-clamp-3 whitespace-pre-wrap text-sm leading-6 text-ink">{event.description}</p> : null}
        <dl className="flex flex-wrap gap-6 text-sm">
          {showPrice ? <div><dt className="text-muted">{t`Price`}</dt><dd><EventPrice inline amount={event.payment_amount} currency={event.currency} tickets={event.ticket_types} ticketRequired={event.ticket_selection_required} /></dd></div> : null}
          <div><dt className="text-muted">{t`Capacity`}</dt><dd className="font-semibold tabular-nums text-ink">{eventCapacityLabel(event.capacity)}</dd></div>
          <div><dt className="text-muted">{t`Availability`}</dt><dd className="font-semibold text-ink">{event.availability}</dd></div>
          {event.show_registration_count !== false && event.registration_count != null ? <div><dt className="text-muted">{t`Registered`}</dt><dd className="font-semibold tabular-nums text-ink">{event.registration_count}</dd></div> : null}
        </dl>
        <div className="flex flex-wrap gap-2">
          <RouteLink className={event.registration_open ? "desk-button-brand" : "desk-button"} href={href}>{eventActionLabel(event)}</RouteLink>
          <button className="desk-button" type="button" disabled={calendarPending} onClick={onCalendar}>{calendarPending ? t`Preparing…` : t`Add to calendar`}</button>
        </div>
        {calendarError ? <p role="alert" className="text-sm text-danger">{calendarError}</p> : null}
      </div>
    </div>
  </article>;
}
