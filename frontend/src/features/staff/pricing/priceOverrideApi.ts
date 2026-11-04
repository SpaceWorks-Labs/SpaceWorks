import { useMutation, useQuery, useQueryClient, type QueryKey } from "@tanstack/react-query";

import type {
  PriceOverrideCard, PriceOverrideCardTargetTypeEnum, PriceOverrideComponent, PriceOverrideWrite,
} from "../../../generated/api";
import { staffRequest } from "../../../lib/api";
import { capabilityOn } from "../../../lib/features";

export type { PriceOverrideCard, PriceOverrideComponent, PriceOverrideWrite };
export type PriceTargetType = PriceOverrideCardTargetTypeEnum;

type SpaceFlags = { id: number; enabled_modules?: string[]; enabled_features?: string[] };

export const priceOverrideKey = (makerspaceId: number, targetType: PriceTargetType, targetId: number) =>
  ["pricing-override", makerspaceId, targetType, targetId] as const;

const overridePath = (makerspaceId: number, targetType: PriceTargetType, targetId: number) =>
  `/admin/makerspace/${makerspaceId}/pricing/overrides/${targetType}/${targetId}`;

/**
 * Is `charges.pricing` on? Read from the staff session's cached makerspace list (never fetched here).
 * `undefined` means this screen cannot tell; the server still answers 404 `pricing_disabled` then.
 * Without an id (a form that does not know its space) any space with price lists counts.
 */
export function useStaffPricingOn(makerspaceId?: number): boolean | undefined {
  const spaces = useQuery({
    queryKey: ["staff", "makerspaces"],
    queryFn: () => staffRequest<SpaceFlags[]>("/admin/makerspaces"),
    enabled: false,
  });
  if (!Array.isArray(spaces.data)) return undefined;
  if (makerspaceId === undefined) return spaces.data.some(space => capabilityOn(space, "charges.pricing"));
  const space = spaces.data.find(row => row.id === makerspaceId);
  return space ? capabilityOn(space, "charges.pricing") : undefined;
}

export function usePriceOverride(makerspaceId: number, targetType: PriceTargetType, targetId: number, enabled: boolean) {
  return useQuery({
    queryKey: priceOverrideKey(makerspaceId, targetType, targetId),
    queryFn: () => staffRequest<PriceOverrideCard>(overridePath(makerspaceId, targetType, targetId)),
    enabled,
    retry: false,
    staleTime: 30_000,
  });
}

/**
 * A custom deposit or room price is written to the item's own price field, so the host's own
 * query is refreshed too -- otherwise its form would save the old value back over it.
 */
function hostKeys(makerspaceId: number, targetType: PriceTargetType, targetId: number): QueryKey[] {
  if (targetType === "inventory_product") return [["inventory", makerspaceId]];
  if (targetType === "bookable_space") return [["booking-space", targetId], ["bookings", makerspaceId]];
  return [];
}

export function useSavePriceOverride(makerspaceId: number, targetType: PriceTargetType, targetId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: PriceOverrideWrite) => staffRequest<PriceOverrideCard>(overridePath(makerspaceId, targetType, targetId), {
      method: "PUT", body: JSON.stringify(body),
    }),
    onSuccess: async (card) => {
      queryClient.setQueryData(priceOverrideKey(makerspaceId, targetType, targetId), card);
      await Promise.all(hostKeys(makerspaceId, targetType, targetId).map(queryKey => queryClient.invalidateQueries({ queryKey })));
    },
  });
}

/** Where an effective price comes from, in words (`effective_source` from the card). */
export const SOURCE_WORDS: Record<string, string> = {
  default: "space default",
  free_default: "space is free",
  override: "this item's price",
  override_free: "free for this item",
  item: "this item's own price",
  type: "machine type price",
  type_free: "machine type is free",
  legacy: "not priced",
  none: "not priced",
};

export const sourceWords = (source: string) => SOURCE_WORDS[source] ?? "not priced";

export const UNIT_WORDS: Record<string, string> = {
  item: "per item", item_day: "per item per day", hour: "per hour", material_unit: "per unit of material",
  job: "per job", booking: "per booking", registration: "per registration", day: "per day", loan: "per loan",
  term: "per membership term", once: "once",
};

export function isPriceOverrideCard(value: unknown): value is PriceOverrideCard {
  return Boolean(value && typeof value === "object" && Array.isArray((value as PriceOverrideCard).components));
}
