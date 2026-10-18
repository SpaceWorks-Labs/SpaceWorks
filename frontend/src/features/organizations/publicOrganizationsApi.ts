import { useQuery } from "@tanstack/react-query";

import { publicV1Request } from "../../lib/api";
import { hostScope, publicPagePolicy } from "../publicPages/pageApi";
import type { SpaceCard } from "../publicPages/pageTypes";

export type PublicOrganization = {
  slug: string;
  name: string;
  description: string;
  website: string;
  logo_url: string | null;
  catalogue_links: { events: string };
  canonical_url?: string;
};

export type OrganizationPublicEvent = {
  public_token: string;
  title: string;
  description: string;
  starts_at: string;
  ends_at: string;
  location: string;
  capacity: number;
  payment_amount: string;
  currency: string;
  availability: "Available" | "Limited" | "Full";
  image_url: string | null;
  status: "published";
  event_url: string;
  timezone?: string;
  host: { slug: string; name: string; logo_url: string | null; canonical_url: string };
};
export type OrganizationPastEvent = {
  title: string; description: string; starts_at: string; ends_at: string; timezone: string;
  host: { name: string; canonical_url: string }; event_url: null;
};
export type OrganizationEvents = (Page<OrganizationPublicEvent> & { period: "upcoming" })
  | (Page<OrganizationPastEvent> & { period: "past" });

export type Page<T> = {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
};

export const publicOrganizationKeys = {
  root: (slug: string) => ["public-organization", hostScope(), slug] as const,
  events: (slug: string, page: number, period = "upcoming", publicationToken?: string) =>
    ["public-organization", hostScope(), slug, publicationToken, "events", period, page] as const,
};

export function usePublicOrganization(slug: string) {
  return useQuery({
    queryKey: publicOrganizationKeys.root(slug),
    ...publicPagePolicy,
    queryFn: () => publicV1Request<PublicOrganization>(
      `/public/organizations/${encodeURIComponent(slug)}/`,
    ),
    enabled: Boolean(slug),
  });
}

export function usePublicOrganizationEvents(slug: string, page: number, period: "upcoming" | "past" = "upcoming", enabled = true, publicationToken?: string) {
  return useQuery({
    queryKey: publicOrganizationKeys.events(slug, page, period, publicationToken),
    ...publicPagePolicy,
    queryFn: () => publicV1Request<OrganizationEvents>(
      `/public/organizations/${encodeURIComponent(slug)}/events/?period=${period}&page=${page}`, { cache: "no-store" },
    ),
    enabled: enabled && Boolean(slug),
  });
}
export function usePublicOrganizationSpaces(slug: string, page: number, enabled = true, publicationToken?: string) {
  return useQuery({ queryKey: ["public-organization", hostScope(), slug, publicationToken, "makerspaces", page], ...publicPagePolicy,
    queryFn: () => publicV1Request<Page<SpaceCard>>(`/public/organizations/${encodeURIComponent(slug)}/makerspaces/?page=${page}`, { cache: "no-store" }),
    enabled: enabled && Boolean(slug),
  });
}
