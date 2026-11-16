import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { staffRequest } from "../../../../../lib/api";
import type { ConsumableKind, ConsumableUnit, EstimateBy, ProfileAttributes, RecordBy } from "./profileUnits";

/** One row of a machine type's consumable profile (decision 341). */
export type ConsumableDefinition = {
  id: number; machine_type: number; key: string; name: string; kind: ConsumableKind; unit: ConsumableUnit; attributes: ProfileAttributes;
  required: boolean; estimate_by: EstimateBy; record_by: RecordBy[]; unit_price: string | null; consumable_pool: number | null;
  consumable_pool_label?: string; product: number | null; product_name?: string; position: number; is_active: boolean;
  template_key?: string; in_use?: boolean; created_at?: string; updated_at?: string;
};
export type ConsumableInput = Pick<ConsumableDefinition, "key" | "name" | "kind" | "unit" | "attributes" | "required" | "estimate_by"
  | "record_by" | "unit_price" | "consumable_pool" | "product" | "position" | "is_active">;
export type ConsumableStock = { pools: { id: number; label: string; unit: string; remaining: string | number }[]; products: { id: number; name: string }[] };

const base = (makerspaceId: number, typeId: number) => `/admin/makerspaces/${makerspaceId}/machine-types/${typeId}`;
export const profileKey = (makerspaceId: number, typeId: number) => ["machine-type-consumables", makerspaceId, typeId] as const;
const send = (method: string, body?: unknown) => ({ method, ...(body === undefined ? {} : { body: JSON.stringify(body) }) });

export function useConsumableProfile(makerspaceId: number, typeId: number, enabled = true) {
  return useQuery({ queryKey: profileKey(makerspaceId, typeId), enabled, retry: false,
    queryFn: async () => {
      const data = await staffRequest<ConsumableDefinition[] | { results: ConsumableDefinition[] }>(`${base(makerspaceId, typeId)}/consumables`);
      return Array.isArray(data) ? data : data.results;
    } });
}

export function useConsumableStock(makerspaceId: number, typeId: number, query: string, enabled = true) {
  return useQuery({ queryKey: ["machine-type-consumable-stock", makerspaceId, typeId, query], retry: false, enabled,
    queryFn: () => staffRequest<ConsumableStock>(`${base(makerspaceId, typeId)}/consumable-stock${query ? `?q=${encodeURIComponent(query)}` : ""}`) });
}

export function useProfileMutations(makerspaceId: number, typeId: number) {
  const client = useQueryClient();
  const refresh = () => client.invalidateQueries({ queryKey: profileKey(makerspaceId, typeId) });
  const root = `${base(makerspaceId, typeId)}/consumables`;
  return {
    create: useMutation({ mutationFn: (body: ConsumableInput) => staffRequest<ConsumableDefinition>(root, send("POST", body)), onSuccess: refresh }),
    update: useMutation({ mutationFn: ({ id, body }: { id: number; body: Partial<ConsumableInput> }) =>
      staffRequest<ConsumableDefinition>(`${root}/${id}`, send("PATCH", body)), onSuccess: refresh }),
    remove: useMutation({ mutationFn: (id: number) => staffRequest<{ outcome: "deleted" | "deactivated" }>(`${root}/${id}`, send("DELETE")), onSuccess: refresh }),
  };
}
