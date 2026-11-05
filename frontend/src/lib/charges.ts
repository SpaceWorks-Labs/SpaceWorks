import { useTenantBootstrap } from "../features/inventory/usePublicInventory";
import type { TenantBootstrap } from "./api/types";
import { useTenant } from "./tenant";

/**
 * Owner decision #184: money is decided per DOMAIN. A domain whose charges are off is
 * completely free, so no price, fee, deposit or payment UI may show for it anywhere.
 */
export type ChargeDomain =
  | "loans"
  | "machines"
  | "bookings"
  | "events"
  | "membership"
  | "shop"
  | "donations";

/**
 * Whether `domain` charges money in this space. Fails OPEN while the bootstrap is still
 * loading or when an older backend omits `charges_tracked`: hiding a real price from
 * someone who is about to be charged is worse than briefly showing one.
 */
export function chargesOn(
  bootstrap: TenantBootstrap | null | undefined,
  domain: ChargeDomain,
): boolean {
  const value = bootstrap?.charges_tracked?.[domain];
  return typeof value === "boolean" ? value : true;
}

/**
 * Hook form of `chargesOn` for both tenant modes. Single-tenant builds read the bootstrap
 * from context; central builds fetch it by `slug` (deduped by the shared query key).
 */
export function useChargesOn(domain: ChargeDomain, slug?: string): boolean {
  const tenant = useTenant();
  const query = useTenantBootstrap(slug ?? "", tenant.mode === "central" && Boolean(slug));
  const bootstrap = tenant.mode === "single" ? tenant.bootstrap : query.data;
  return chargesOn(bootstrap, domain);
}
