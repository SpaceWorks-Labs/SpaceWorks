import { useQuery } from "@tanstack/react-query";

import { tenantPublicRequest, type TenantBootstrap } from "../../lib/api";
import type { ShopPublicProduct } from "./shopApi";
import type { PickupEvent } from "./pickupPreference";

/**
 * #135 Q-S18 follow-up: the shop items an event offers. Hand-typed until the client is
 * regenerated. The server answers 404 with the shop, its event pickup or Events off.
 */
export type EventShopOffers = { event: PickupEvent; currency: string; products: ShopPublicProduct[] };

/** Only ask when the bootstrap says the shop sells online with event pickup and Events is on. */
export function eventOffersEnabled(bootstrap?: Pick<TenantBootstrap, "modules" | "features"> | null) {
  const modules = bootstrap?.modules ?? [];
  const features = bootstrap?.features ?? [];
  return modules.includes("shop") && modules.includes("events")
    && features.includes("shop.online") && features.includes("shop.event_pickup");
}

export function useEventShopOffers(slug: string, publicToken: string | undefined, enabled: boolean) {
  return useQuery({
    queryKey: ["shop", slug, "event-offers", publicToken],
    enabled: enabled && Boolean(slug && publicToken),
    retry: false,
    queryFn: () => tenantPublicRequest<EventShopOffers>(slug,
      `/public/m/${encodeURIComponent(slug)}/shop/events/${encodeURIComponent(publicToken ?? "")}/offers/`),
  });
}
