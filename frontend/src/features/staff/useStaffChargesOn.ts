import { useQuery } from "@tanstack/react-query";

import { staffRequest } from "../../lib/api";
import type { ChargeDomain } from "../../lib/charges";
import { capabilityOn } from "../../lib/features";

type SpaceFlags = { id: number; enabled_modules?: string[]; enabled_features?: string[] };

/** The backend's `charge_tracking_enabled`: the `charges.enabled` master switch AND the domain's key. */
export function staffChargesOn(space: Omit<SpaceFlags, "id">, domain: ChargeDomain) {
  return capabilityOn(space, "charges.enabled") && capabilityOn(space, `charges.${domain}`);
}

/**
 * Staff-console twin of `useChargesOn` (#184) for editors that hold a makerspace id rather
 * than a public bootstrap. Reads the session's cached makerspace list (never fetched here,
 * like `useStaffPricingOn`). Fails OPEN while that list or the space is unknown, so a price
 * field is never hidden by a missing cache. Without an id (a form that does not know its
 * space) the field shows when any staff space tracks that domain's charges.
 */
export function useStaffChargesOn(domain: ChargeDomain, makerspaceId?: number): boolean {
  const spaces = useQuery({
    queryKey: ["staff", "makerspaces"],
    queryFn: () => staffRequest<SpaceFlags[]>("/admin/makerspaces"),
    enabled: false,
  });
  if (!Array.isArray(spaces.data) || !spaces.data.length) return true;
  if (makerspaceId === undefined) return spaces.data.some(space => staffChargesOn(space, domain));
  const space = spaces.data.find(row => row.id === makerspaceId);
  return space ? staffChargesOn(space, domain) : true;
}
