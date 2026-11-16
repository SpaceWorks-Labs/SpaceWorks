import { t } from "@lingui/core/macro";
import { MapPin } from "lucide-react";

export type Venue = { location?: string | null; venue_address?: string | null; venue_map_url?: string | null };

/** Directions for an outside venue: the organiser's own map link wins, otherwise a map search for the address. */
export function venueMapHref(venue: Venue) {
  const link = venue.venue_map_url?.trim();
  if (link && /^https:\/\//i.test(link)) return link;
  const query = [venue.location, venue.venue_address].map(part => part?.trim()).filter(Boolean).join(", ");
  return venue.venue_address?.trim() ? `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(query)}` : null;
}

export const hasVenueDetails = (venue: Venue) => Boolean(venue.venue_address?.trim() || venue.venue_map_url?.trim());

/** The "Where" block on the public event page (parity E-F3, E-B7 venue fields). Renders nothing without details. */
export function EventVenueDetails({ venue }: { venue: Venue }) {
  if (!hasVenueDetails(venue)) return null;
  const href = venueMapHref(venue);
  return <div className="grid gap-2">
    {venue.location ? <p className="font-semibold text-ink">{venue.location}</p> : null}
    {venue.venue_address ? <p className="whitespace-pre-line text-muted">{venue.venue_address}</p> : null}
    {href ? <a className="inline-flex min-h-11 w-fit items-center gap-2 font-semibold text-brand-ink underline-offset-4 hover:underline" href={href} target="_blank" rel="noopener noreferrer">
      <MapPin size={18} aria-hidden="true" />{t`Get directions`}<span className="sr-only">{t` (opens in a new tab)`}</span></a> : null}
  </div>;
}
