import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { staffRequest } from "../../../lib/api";

// Hand-written mirrors of `apps/events/views_equipment_window.py` and `views_equipment_desk.py`
// (decision 221b) until `src/generated/api.ts` is regenerated.
export type WindowStatus = "available" | "limited" | "unavailable";
export type WindowRow = {
  product_id: number; name: string; event_only: boolean; status: WindowStatus;
  /** Exact counts arrive only for staff who also hold view_inventory (`counts_visible`). */
  free?: number; committed?: number; back_before_window?: number; lendable?: number;
};
export type WindowAvailability = {
  window: { starts_at: string; return_due_at: string };
  equipment_return_hours: number | null;
  counts_visible: boolean;
  results: WindowRow[];
};
export type PlanLine = { product_id: number; quantity: number };
export type PlanBody = {
  operation_id: string; requested_for: string; lines: PlanLine[];
  participants: { registration_id: number; lines?: PlanLine[] }[]; dry_run?: boolean;
};
export type PlanTotal = { product_id: number; requested: number; status: "ok" | "short"; free?: number };
export type PlanResult = {
  registration_id: number; outcome: "created" | "replayed" | "error";
  request_id?: number; status?: string; code?: string;
};
export type PlanResponse = { dry_run: boolean; totals: PlanTotal[]; results: PlanResult[] };

/** The picker of public requestable equipment for an event (`equipment-request-products`). */
export type PickerRow = { id: number; name: string; event_only?: boolean };
export type PickerPage = { results: PickerRow[]; next: string | null; previous: string | null };

const base = (makerspaceId: number, eventId: number) => `/admin/makerspace/${makerspaceId}/events/${eventId}`;

export const eventEquipmentKeys = {
  event: (makerspaceId: number, eventId: number) => ["event-equipment", makerspaceId, eventId] as const,
  desk: (makerspaceId: number, eventId: number) => ["event-equipment-desk", makerspaceId, eventId] as const,
};

export function useEquipmentPicker(makerspaceId: number, eventId: number, page: number, enabled: boolean) {
  return useQuery({
    queryKey: [...eventEquipmentKeys.event(makerspaceId, eventId), "picker", page], enabled, retry: false,
    queryFn: ({ signal }) => staffRequest<PickerPage>(`${base(makerspaceId, eventId)}/equipment-request-products?page=${page}`, { signal }),
  });
}

/** Free versus committed units for the event window, from the availability owner (reserves nothing). */
export function useWindowAvailability(makerspaceId: number, eventId: number, productIds: number[]) {
  const ids = [...new Set(productIds)].sort((a, b) => a - b).slice(0, 50);
  return useQuery({
    queryKey: [...eventEquipmentKeys.event(makerspaceId, eventId), "availability", ids.join(",")],
    enabled: ids.length > 0, retry: false,
    queryFn: ({ signal }) => staffRequest<WindowAvailability>(
      `${base(makerspaceId, eventId)}/equipment-availability?product_ids=${ids.join(",")}`, { signal }),
  });
}

export function useEquipmentPlan(makerspaceId: number, eventId: number) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: PlanBody) => staffRequest<PlanResponse>(`${base(makerspaceId, eventId)}/equipment-plan`, {
      method: "POST", body: JSON.stringify(body),
    }),
    onSuccess: (data) => {
      if (data.dry_run) return;
      // New pending requests: the desk counts and the window figures move.
      void client.invalidateQueries({ queryKey: eventEquipmentKeys.desk(makerspaceId, eventId) });
      void client.invalidateQueries({ queryKey: eventEquipmentKeys.event(makerspaceId, eventId) });
    },
  });
}

export function useReturnWindow(makerspaceId: number, eventId: number) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (hours: number | null) => staffRequest<{ equipment_return_hours: number | null }>(
      `${base(makerspaceId, eventId)}/equipment-desk`, { method: "PATCH", body: JSON.stringify({ equipment_return_hours: hours }) }),
    onSuccess: () => Promise.all([
      client.invalidateQueries({ queryKey: eventEquipmentKeys.desk(makerspaceId, eventId) }),
      client.invalidateQueries({ queryKey: eventEquipmentKeys.event(makerspaceId, eventId) }),
    ]),
  });
}
