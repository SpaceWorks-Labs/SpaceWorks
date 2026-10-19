import { useQuery } from "@tanstack/react-query";

import { publicV1Request } from "../../lib/api";
import { hostScope, publicPagePolicy } from "../publicPages/pageApi";
import type { SpaceCard } from "../publicPages/pageTypes";

// canonical_url is added by this round's serializer change; regenerate the client with the schema.
export type PublicOrganization = import("../../generated/api").PublicOrganization & { canonical_url: string };
export type OrganizationPublicEvent = import("../../generated/api").PublicOrganizationEvent;
export type OrganizationPastEvent = import("../../generated/api").OrganizationArchiveEvent;
export type OrganizationEvents = import("../../generated/api").OrganizationEventCollection;
export type Page<T> = import("../publicPages/pageTypes").Collection<T>;

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
