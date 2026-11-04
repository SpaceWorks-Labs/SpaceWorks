import { MapPin } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { DateChip } from "../../components/ui/DateChip";
import { RouteLink } from "../../components/ui/RouteLink";
import type { ApiPath } from "../../generated/api";
import { StructuredApiError, tenantPublicRequest } from "../../lib/api";
import { EventPrice } from "../events/EventPrice";
import type { PublicEventDetail } from "../events/eventTicketTypes";
import { eventActionLabel } from "../inventory/PublicEventCard";
import { MakerspaceSection } from "./MakerspaceSection";
import { deliveryLabel } from "../events/publicSurface";

const PUBLIC_EVENTS_PATH: ApiPath = "/api/v1/public/{makerspace_slug}/events/";
export const FEATURED_LIMIT = 6;

/** Same endpoint and query key as the events page, so opening "All events" reuses this fetch. */
export function useFeaturedEvents(slug: string, enabled: boolean) {
  return useQuery({
    queryKey: ["public-events", slug],
    enabled: enabled && Boolean(slug),
    queryFn: () => tenantPublicRequest<PublicEventDetail[]>(slug,
      PUBLIC_EVENTS_PATH.replace("/api/v1", "").replace("{makerspace_slug}", encodeURIComponent(slug))),
    retry: (count, error) => !(error instanceof StructuredApiError && error.status < 500) && count < 2,
  });
}

/** "17 Oct · 10:00 AM – 1:30 PM" in the makerspace's zone; a multi-day event names both dates. */
export function eventWhen(event: PublicEventDetail, timeZone?: string) {
  const zone = timeZone || undefined;
  const day = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", timeZone: zone });
  const time = new Intl.DateTimeFormat("en-US", { hour: "numeric", minute: "2-digit", timeZone: zone });
  const start = new Date(event.starts_at);
  const end = new Date(event.ends_at);
  const sameDay = day.format(start) === day.format(end);
  return sameDay ? `${day.format(start)} · ${time.format(start)} – ${time.format(end)}`
    : `${day.format(start)} · ${time.format(start)} – ${day.format(end)} · ${time.format(end)}`;
}

function chips(event: PublicEventDetail) {
  // DY-73: how people attend leads the chips (absent while online events are off here).
  const labels = [deliveryLabel(event), event.category?.name, event.audience_label, ...(event.tags ?? [])]
    .filter((label): label is string => Boolean(label?.trim()));
  return [...new Set(labels.map((label) => label.trim()))].slice(0, 3);
}

function FeaturedEventCard({ event, href, timeZone }: { event: PublicEventDetail; href: string; timeZone?: string }) {
  const titleId = `featured-${event.public_token}`;
  return <li className="flex w-[85%] shrink-0 snap-start sm:w-80 md:w-auto">
    <article aria-labelledby={titleId} className="desk-panel flex w-full min-w-0 flex-col overflow-hidden">
      <div className="grid flex-1 content-start gap-3 p-5">
        <div className="flex min-w-0 items-start gap-3">
          <DateChip date={event.starts_at} seed={event.public_token} />
          <h3 id={titleId} className="min-w-0 flex-1 break-words">
            <RouteLink className="title-panel rounded-control hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus" href={href}>{event.title}</RouteLink>
          </h3>
        </div>
        <p className="text-sm font-semibold text-ink"><time dateTime={event.starts_at}>{eventWhen(event, timeZone)}</time></p>
        {event.location ? <p className="flex min-w-0 items-start gap-1.5 text-sm text-muted">
          <MapPin aria-hidden="true" size={16} className="mt-0.5 shrink-0" /><span className="sr-only">Venue: </span>
          <span className="line-clamp-2 [overflow-wrap:anywhere]">{event.location}</span>
        </p> : null}
        {chips(event).length ? <ul aria-label="Event tags" className="flex flex-wrap gap-2">
          {chips(event).map((label) => <li key={label} className="rounded-full border border-line bg-surface px-3 py-1 text-xs font-semibold uppercase tracking-wide text-ink">{label}</li>)}
        </ul> : null}
        <div className="mt-auto flex flex-wrap items-center justify-between gap-3 pt-2">
          <EventPrice inline amount={event.payment_amount} currency={event.currency} tickets={event.ticket_types} ticketRequired={event.ticket_selection_required} />
          <RouteLink className={event.registration_open ? "desk-button-brand" : "desk-button"} href={href} aria-describedby={titleId}>{eventActionLabel(event)}</RouteLink>
        </div>
      </div>
      {/* Decorative: the title already names the event. The banner sits at the foot, as in the reference. */}
      {event.image_url ? <img src={event.image_url} alt="" loading="lazy" className="aspect-[2/1] w-full border-t border-line object-cover" /> : null}
    </article>
  </li>;
}

type Props = { slug: string; path: (part?: string) => string; timeZone?: string };

/**
 * Upcoming public events as a rail: swipeable on phones, a grid from tablet up. The section is
 * absent, not empty, while loading and when nothing is coming up, so the page never shows a
 * placeholder heading over nothing. The endpoint already returns only public, published, not-yet-ended events.
 */
export function FeaturedActivities({ slug, path, timeZone }: Props) {
  const events = useFeaturedEvents(slug, true);
  if (events.isLoading) return null;
  if (events.isError) return <MakerspaceSection id="featured" title="Featured activities">
    <p role="alert" className="flex flex-wrap items-center gap-3 text-sm text-muted">Couldn't load upcoming events.
      <button type="button" className="desk-button" onClick={() => void events.refetch()}>Try again</button></p>
  </MakerspaceSection>;
  const now = Date.now();
  const upcoming = (events.data ?? []).filter((event) => Date.parse(event.ends_at) > now)
    .sort((a, b) => Date.parse(a.starts_at) - Date.parse(b.starts_at)).slice(0, FEATURED_LIMIT);
  if (!upcoming.length) return null;
  return <MakerspaceSection id="featured" title="Featured activities" more={{ label: "All events", href: path("events") }}>
    <ul aria-label="Upcoming events" className="flex snap-x snap-mandatory gap-4 overflow-x-auto pb-2 max-sm:-mx-4 max-sm:scroll-px-4 max-sm:px-4 md:grid md:grid-cols-[repeat(auto-fill,minmax(min(100%,17rem),1fr))] md:overflow-visible md:pb-0">
      {upcoming.map((event) => <FeaturedEventCard key={event.public_token} event={event} href={path(`events/${event.public_token}`)} timeZone={timeZone} />)}
    </ul>
  </MakerspaceSection>;
}
