import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { staffRequest } from "../../lib/api";
import type { DepartureInput, DepartureOutcome } from "../bookings/DepartureForm";
import type { Booking, BookingStatus, Paginated } from "./bookingsApi";

/** Hand-typed until the integrator regenerates the OpenAPI client. */
export type QueueStatus = BookingStatus | "all";
export type BookingIssue = {
  id: number; booking_id: number; space_id: number; space_name: string; booker_name: string;
  starts_at: string; ends_at: string; outcome: Exclude<DepartureOutcome, "all_good">; remark: string;
  source: "staff" | "member"; created_at: string; resolved_at: string | null; resolution_note: string;
};
export type IssuePage = Paginated<BookingIssue> & { open_count: number };

export const queueKeys = {
  queue: (makerspaceId: number) => ["booking-queue", makerspaceId] as const,
  issues: (makerspaceId: number) => ["booking-issues", makerspaceId] as const,
};

/** Requests across every space this actor manages reservations for (newest decisions first in the UI). */
export function useBookingQueue(makerspaceId: number, status: QueueStatus, page: number, space?: number) {
  const query = new URLSearchParams({ status, page: String(page), ordering: status === "pending" ? "created_at" : "starts_at" });
  if (space) query.set("space", String(space));
  return useQuery({
    queryKey: [...queueKeys.queue(makerspaceId), status, page, space ?? ""],
    queryFn: () => staffRequest<Paginated<Booking>>(`/admin/makerspaces/${makerspaceId}/bookings/?${query}`),
  });
}

export function useBookingIssues(makerspaceId: number, status: "open" | "resolved" | "all", page = 1, space?: number) {
  const query = new URLSearchParams({ status, page: String(page) });
  if (space) query.set("space", String(space));
  return useQuery({
    queryKey: [...queueKeys.issues(makerspaceId), status, page, space ?? ""],
    queryFn: () => staffRequest<IssuePage>(`/admin/makerspaces/${makerspaceId}/booking-issues/?${query}`),
  });
}

function useBookingRefresh(makerspaceId: number) {
  const client = useQueryClient();
  return () => Promise.all([
    client.invalidateQueries({ queryKey: queueKeys.queue(makerspaceId) }),
    client.invalidateQueries({ queryKey: queueKeys.issues(makerspaceId) }),
    client.invalidateQueries({ queryKey: ["booking-space"] }),
    client.invalidateQueries({ queryKey: ["bookings", makerspaceId] }),
    client.invalidateQueries({ queryKey: ["operations-report"] }),
  ]);
}

export function useResolveIssue(makerspaceId: number) {
  const refresh = useBookingRefresh(makerspaceId);
  return useMutation({
    mutationFn: ({ id, note }: { id: number; note: string }) => staffRequest<BookingIssue>(
      `/admin/booking-issues/${id}/resolve/`, { method: "POST", body: JSON.stringify({ note }) }),
    onSuccess: refresh,
  });
}

/** Staff check-out for one booking; returns the arrival projection (departed_at, can_depart). */
export function useRecordDeparture(makerspaceId: number, spaceId: number) {
  const refresh = useBookingRefresh(makerspaceId);
  return useMutation({
    mutationFn: ({ bookingId, ...input }: DepartureInput & { bookingId: number }) => staffRequest<{ departed_at: string | null; can_depart: boolean }>(
      `/admin/spaces/${spaceId}/arrival/${bookingId}/depart/`, { method: "POST", body: JSON.stringify(input) }),
    onSuccess: refresh,
  });
}
