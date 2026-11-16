import { useQuery } from "@tanstack/react-query";

import { staffRequest, StructuredApiError } from "../../../lib/api";

/**
 * Decision 242(g): the Event Manager reads an event's own loans and guest passes, read-only,
 * scoped to that event, with no stock counts. Hand-typed from
 * backend/apps/events/views_event_loans_passes.py until the client is regenerated.
 * `enabled: false` means lending / guest passes are off for the space; a 403/404 hides the section.
 */
export type EventLoanRow = {
  request_id: number; status: string; holder: string; issued_at: string | null; due_at: string | null;
  items: { product_name: string; requested: number; issued: number; returned: number }[];
};
export type EventGuestPassRow = { id: number; kind: string; status: string; holder: string; valid_until: string };
type Listing<T> = { enabled: boolean; results: T[] };

function useEventList<T>(eventId: number, path: "loans" | "guest-passes", enabled: boolean) {
  const query = useQuery({
    queryKey: ["event", eventId, "linked", path],
    enabled,
    retry: false,
    queryFn: ({ signal }) => staffRequest<Listing<T>>(`/admin/events/${eventId}/${path}/`, { signal }),
  });
  const status = query.error instanceof StructuredApiError ? query.error.status : undefined;
  const rows = query.data?.results ?? [];
  return { query, rows, count: rows.length, hidden: status === 403 || status === 404 || query.data?.enabled === false };
}

export const useEventLoans = (eventId: number, enabled = true) => useEventList<EventLoanRow>(eventId, "loans", enabled);
export const useEventGuestPasses = (eventId: number, enabled = true) => useEventList<EventGuestPassRow>(eventId, "guest-passes", enabled);
