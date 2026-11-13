import { t } from "@lingui/core/macro";
import { QueryClientContext } from "@tanstack/react-query";
import { useContext } from "react";

import { staffRequest } from "../../../lib/api";
import { capabilityOn } from "../../../lib/features";

/** Lane L24 (#163A): lowering a price after people paid opens a staff-approved refund case per paid item. */
export const PRICE_DROP_FEATURE = "charges.price_drop_refunds";

export type PriceDropItem = {
  area: "bookings" | "events" | "machines" | "membership";
  item_type: string;
  item_id: number;
  label: string;
  starts_at: string | null;
  payment_id: number;
  currency: string;
  paid: string;
  before: string;
  after: string;
  difference: string;
  case_id: number | null;
};

export type PriceDropReport = {
  count: number;
  truncated: boolean;
  items: PriceDropItem[];
  totals: { currency: string; difference: string }[];
};

type SpaceFlags = { id: number; enabled_modules?: string[]; enabled_features?: string[] };

/**
 * Is `charges.price_drop_refunds` on? Read from the staff session's cached makerspace list
 * (never fetched here, and without a provider -- as in a form rendered on its own -- it is off).
 * Without an id, any space with it on counts; the server then answers 404
 * `price_drop_disabled` for a space where it is off, and the save simply goes ahead.
 */
export function usePriceDropOn(makerspaceId?: number): boolean {
  const client = useContext(QueryClientContext);
  const spaces = client?.getQueryData<SpaceFlags[]>(["staff", "makerspaces"]);
  if (!Array.isArray(spaces)) return false;
  if (makerspaceId === undefined) return spaces.some(space => capabilityOn(space, PRICE_DROP_FEATURE));
  const space = spaces.find(row => row.id === makerspaceId);
  return space ? capabilityOn(space, PRICE_DROP_FEATURE) : false;
}

/**
 * Ask the server what a price save WOULD refund: the same request with `?price_drop_preview=1`.
 * The server runs the save and rolls it back, so the list matches the real save exactly.
 * `null` means there is nothing to show (the switch is off there, or the save itself is
 * invalid -- the real save reports that error in the form as usual).
 */
export async function previewPriceDrop(path: string, method: string, body: unknown): Promise<PriceDropReport | null> {
  const url = `${path}${path.includes("?") ? "&" : "?"}price_drop_preview=1`;
  try {
    const result = await staffRequest<{ price_drop: PriceDropReport }>(url, { method, body: JSON.stringify(body) });
    return result.price_drop;
  } catch {
    // 404 switched off, 400 invalid, 409 frozen, or offline: nothing to preview. The real save
    // runs next and shows its own error in the form.
    return null;
  }
}

export const AREA_LABELS: Record<PriceDropItem["area"], string> = {
  bookings: t`Booking`, events: t`Ticket`, machines: t`Machine job`, membership: t`Membership`,
};
