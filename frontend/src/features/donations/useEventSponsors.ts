import { useQuery } from "@tanstack/react-query";

import { tenantPublicRequest } from "../../lib/api";
import type { SponsorCard } from "../publicPages/PublicSponsorCards";

/**
 * Space sponsors linked to one public event (lane L18). Off, unknown or empty all read as "no
 * sponsors", so the event page simply leaves the section out.
 */
export function useEventSponsors(slug: string, publicToken: string | undefined, enabled: boolean) {
  const query = useQuery({
    queryKey: ["public-event-sponsors", slug, publicToken],
    queryFn: () => tenantPublicRequest<{ results: SponsorCard[] }>(slug,
      `/public/${encodeURIComponent(slug)}/events/${encodeURIComponent(publicToken ?? "")}/sponsors`),
    enabled: enabled && Boolean(slug && publicToken), retry: false,
  });
  return query.data?.results ?? [];
}
