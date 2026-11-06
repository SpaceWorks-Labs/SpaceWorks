import { createContext, useContext } from "react";
import { useQuery } from "@tanstack/react-query";

import { staffRequest } from "../../lib/api";
import type { ChargeDomain } from "../../lib/charges";
import { capabilityOn } from "../../lib/features";

type SpaceFlags = { id: number; enabled_modules?: string[]; enabled_features?: string[] };

/** The backend's `charge_tracking_enabled`: the `charges.enabled` master switch AND the domain's key. */
export function staffChargesOn(space: Omit<SpaceFlags, "id">, domain: ChargeDomain) {
  return capabilityOn(space, "charges.enabled") && capabilityOn(space, `charges.${domain}`);
}

/** The console's active space (StaffTabContent), the default when a caller passes no id (R4 audit B). */
export const StaffChargeSpaceContext = createContext<number | undefined>(undefined);

/**
 * Staff-console twin of `useChargesOn` (#184) for editors that hold a makerspace id rather
 * than a public bootstrap. Reads the session's cached makerspace list (never fetched here,
 * like `useStaffPricingOn`). Fails OPEN while that list or the space is unknown, so a price
 * field is never hidden by a missing cache. Without an id the console's active space is used;
 * only outside the console (no active space) does the field show when any staff space tracks
 * that domain's charges -- otherwise a free space showed prices whenever another space charged.
 */
export function useStaffChargesOn(domain: ChargeDomain, explicitId?: number): boolean {
  const activeId = useContext(StaffChargeSpaceContext);
  const makerspaceId = explicitId ?? activeId;
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
