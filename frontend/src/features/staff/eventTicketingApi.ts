import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { staffRequest } from "../../lib/api";
import type { Paginated } from "./eventsApiTypes";

export type EventCode = {
  id: number; max_uses: number; uses: number; expires_at: string | null;
  revoked_at: string | null; code?: string;
};
export type EventPromo = EventCode & { percent_off: number; amount_off: string };
export type StaffTicket = {
  id: number; name: string; amount: string; audience: "member" | "public";
  capacity: number; sales_start_at: string | null; sales_end_at: string | null;
  is_active?: boolean;
  /** Registrations that used this type; once any exist, price and audience are fixed. */
  registration_count?: number;
};
/** Release 2 L6 (G29): order options on a ticket type. */
export type TicketOrderFields = { tier_group: string; tier_rank: number; pricing_mode: "fixed" | "pwyw"; min_amount: string;
  seats_per_ticket: number; is_hidden: boolean; min_quantity: number; per_order_limit: number };
export type StaffTicketPatch = Partial<Pick<StaffTicket, "name" | "amount" | "audience" | "capacity" | "sales_start_at" | "sales_end_at" | "is_active">>
  & Partial<TicketOrderFields>;

type TicketingKind = "invites" | "promo-codes" | "ticket-types";

/** A ticketing change alters the staff list and what the public event page offers. */
function useTicketingRefresh(eventId: number, kind: TicketingKind) {
  const client = useQueryClient();
  return () => Promise.all([
    client.invalidateQueries({ queryKey: ["event", eventId, kind] }),
    client.invalidateQueries({ queryKey: ["public-events"] }),
    client.invalidateQueries({ queryKey: ["public-event"] }),
  ]);
}

export function useEventTicketing<T>(eventId: number, kind: TicketingKind, page = 1) {
  const key = ["event", eventId, kind];
  const path = `/admin/events/${eventId}/${kind}/`;
  const rows = useQuery({ queryKey: [...key, page], queryFn: () => staffRequest<Paginated<T>>(`${path}?page=${page}`) });
  const refresh = useTicketingRefresh(eventId, kind);
  const create = useMutation({ mutationFn: (payload: Record<string, unknown>) => staffRequest<T>(path, { method: "POST", body: JSON.stringify(payload) }), onSuccess: refresh });
  const revoke = useMutation({
    mutationFn: (id: number) => staffRequest<T>(`/admin/${kind === "invites" ? "event-invites" : "event-promos"}/${id}/revoke/`, { method: "POST", body: "{}" }),
    onSuccess: refresh,
  });
  return { rows, create, revoke };
}

/** Edit or delete one ticket type. A referenced type answers 409 `ticket_type_referenced`. */
export function useTicketTypeChanges(eventId: number) {
  const refresh = useTicketingRefresh(eventId, "ticket-types");
  const update = useMutation({ onSuccess: refresh, mutationFn: ({ id, patch }: { id: number; patch: StaffTicketPatch }) =>
    staffRequest<StaffTicket>(`/admin/event-ticket-types/${id}/`, { method: "PATCH", body: JSON.stringify(patch) }) });
  const remove = useMutation({ onSuccess: refresh, mutationFn: (id: number) =>
    staffRequest<void>(`/admin/event-ticket-types/${id}/`, { method: "DELETE" }) });
  return { update, remove };
}

/** Select controls need all options while the API retains its normal pagination. */
export async function eventOptions<T>(path: string): Promise<T[]> {
  const result: T[] = [];
  for (let page = 1; ; page += 1) {
    const response = await staffRequest<Paginated<T>>(`${path}?page=${page}`);
    result.push(...response.results);
    if (!response.next) return result;
  }
}
