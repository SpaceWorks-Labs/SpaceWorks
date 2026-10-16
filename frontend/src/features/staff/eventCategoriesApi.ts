import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { staffRequest } from "../../lib/api";
import { eventOptions } from "./eventTicketingApi";

/** `event_count` arrives with the Phase 2 contract; a category in use cannot be deleted (409 `category_referenced`). */
export type EventCategory = { id: number; name: string; slug: string; event_count?: number };
export type EventCategoryInput = { name: string; slug: string };

export const eventCategoryKeys = { list: (makerspaceId: number) => ["event-categories", makerspaceId] as const };
const path = (makerspaceId: number) => `/admin/makerspaces/${makerspaceId}/event-categories/`;

export function useEventCategories(makerspaceId: number) {
  return useQuery({ queryKey: eventCategoryKeys.list(makerspaceId), queryFn: () => eventOptions<EventCategory>(path(makerspaceId)) });
}

export function useEventCategoryChanges(makerspaceId: number) {
  const client = useQueryClient();
  const refresh = () => client.invalidateQueries({ queryKey: eventCategoryKeys.list(makerspaceId) });
  const create = useMutation({ mutationFn: (input: EventCategoryInput) => staffRequest<EventCategory>(path(makerspaceId), { method: "POST", body: JSON.stringify(input) }),
    onSuccess: async (row) => { await refresh(); return row; } });
  const update = useMutation({ onSuccess: refresh, mutationFn: ({ id, input }: { id: number; input: Partial<EventCategoryInput> }) =>
    staffRequest<EventCategory>(`${path(makerspaceId)}${id}/`, { method: "PATCH", body: JSON.stringify(input) }) });
  const remove = useMutation({ onSuccess: refresh, mutationFn: (id: number) =>
    staffRequest<void>(`${path(makerspaceId)}${id}/`, { method: "DELETE" }) });
  return { create, update, remove };
}
