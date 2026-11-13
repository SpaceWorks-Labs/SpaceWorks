import { useQuery } from "@tanstack/react-query";

import { staffRequest } from "../../lib/api";
import type { ChargeDomain } from "../../lib/charges";
import { capabilityOn } from "../../lib/features";
import { readStoredMakerspace } from "./staffTabs";

type SpaceFlags = { id: number; enabled_modules?: string[]; enabled_features?: string[] };

/** The backend's `charge_tracking_enabled`: the `charges.enabled` master switch AND the domain's key. */
export function staffChargesOn(space: Omit<SpaceFlags, "id">, domain: ChargeDomain) {
  return capabilityOn(space, "charges.enabled") && capabilityOn(space, `charges.${domain}`);
}

/**
 * Staff-console twin of `useChargesOn` (#184) for editors that hold a makerspace id rather
 * than a public bootstrap. Reads the session's cached makerspace list (never fetched here,
 * like `useStaffPricingOn`). Fails OPEN while that list or the space is unknown, so a price
 * field is never hidden by a missing cache. Without an id the console's selected space is
 * used (a multi-space staff member must not see prices for a free space because another
 * space charges); only with no selection does the field show when any staff space tracks
 * that domain's charges.
 */
export function useStaffChargesOn(domain: ChargeDomain, makerspaceId?: number): boolean {
  const spaces = useQuery({
    queryKey: ["staff", "makerspaces"],
    queryFn: () => staffRequest<SpaceFlags[]>("/admin/makerspaces"),
    enabled: false,
  });
  if (!Array.isArray(spaces.data) || !spaces.data.length) return true;
  const id = makerspaceId ?? readStoredMakerspace() ?? undefined;
  if (id === undefined) return spaces.data.some(space => staffChargesOn(space, domain));
  const space = spaces.data.find(row => row.id === id);
  return space ? staffChargesOn(space, domain) : true;
}
