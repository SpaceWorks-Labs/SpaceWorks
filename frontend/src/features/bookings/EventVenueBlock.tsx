import { t } from "@lingui/core/macro";
import { useQuery } from "@tanstack/react-query";
import { MapPin } from "lucide-react";

import { Gallery, type GalleryPhoto } from "../../components/ui/Gallery";
import { RouteLink } from "../../components/ui/RouteLink";
import { StructuredApiError, tenantPublicRequest } from "../../lib/api";

/** Hand-typed until the integrator regenerates the OpenAPI client. */
export type EventVenue = {
  host: { name: string; slug: string; location: string; map_url: string; logo_url: string };
  space: { public_token: string; name: string; kind: string; location: string; capacity: number } | null;
  photos: GalleryPhoto[];
};

export function useEventVenue(slug: string, eventToken: string | undefined) {
  return useQuery({
    queryKey: ["public-event-venue", slug, eventToken],
    enabled: Boolean(slug && eventToken),
    staleTime: 60_000,
    // A missing venue route (bookings not installed) is a normal "no block", never a retry loop.
    retry: (count, error) => !(error instanceof StructuredApiError && error.status < 500) && count < 1,
    queryFn: () => tenantPublicRequest<EventVenue>(slug,
      `/public/${encodeURIComponent(slug)}/events/${encodeURIComponent(eventToken ?? "")}/venue/`),
  });
}

/** "Hosted at" block for a public event page: host makerspace, the matched space and its photos. */
export function EventVenueBlock({ venue, spaceHref }: { venue: EventVenue; spaceHref?: (token: string) => string }) {
  const { host, space, photos } = venue;
  const place = space ? `${space.name}, ${host.name}` : host.name;
  const address = space?.location || host.location;
  return (
    <div className="grid gap-4">
      <div className="flex flex-wrap items-start gap-3">
        <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-surface text-brand-ink" aria-hidden="true">
          {host.logo_url ? <img src={host.logo_url} alt="" className="h-11 w-11 rounded-full object-cover" /> : <MapPin size={20} />}
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-sm text-muted">{t`Hosted at`}</p>
          <p className="font-semibold">{place}</p>
          {address ? <p className="text-sm text-muted">{address}</p> : null}
          <div className="mt-2 flex flex-wrap gap-3 text-sm">
            {space && spaceHref ? <RouteLink className="desk-button-ghost" href={spaceHref(space.public_token)}>{t`About this space`}</RouteLink> : null}
            {host.map_url ? <a className="desk-button-ghost" href={host.map_url} target="_blank" rel="noreferrer noopener">{t`Open map`}</a> : null}
          </div>
        </div>
      </div>
      <Gallery photos={photos} label={t`Photos of ${place}`} />
    </div>
  );
}

/** Section list entry for PublicDetailLayout; empty while loading or when the route is unavailable. */
export function useEventVenueSection(slug: string, eventToken: string | undefined, spaceHref?: (token: string) => string) {
  const venue = useEventVenue(slug, eventToken);
  // Only a well-formed venue renders; anything else (an older server, a proxy page) shows no block.
  return venue.data?.host ? [{ id: "venue", label: t`Hosted at`, content: <EventVenueBlock venue={venue.data} spaceHref={spaceHref} /> }] : [];
}
