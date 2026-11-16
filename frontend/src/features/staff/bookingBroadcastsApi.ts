import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { staffRequest } from "../../lib/api";
import type { Paginated } from "./bookingsApi";

export type BookingCampaign = {
  id: number; space: number; subject: string; body: string; statuses: Array<"pending" | "confirmed">;
  window_start: string; window_end: string; created_at: string;
  status: "draft" | "queued" | "sending" | "sent" | "cancelled" | "failed";
};
export type BookingCampaignInput = Pick<BookingCampaign, "subject" | "body" | "statuses" | "window_start" | "window_end">;
export const bookingCommunicationKeys = {
  campaigns: (tenant: number, resource: number) => ["booking-broadcasts", tenant, resource] as const,
};

export function useBookingBroadcasts(tenant: number, resource: number, page: number) {
  const client = useQueryClient();
  const key = bookingCommunicationKeys.campaigns(tenant, resource);
  const path = `/admin/spaces/${resource}/broadcasts/`;
  const history = useQuery({ queryKey: [...key, page],
    queryFn: () => staffRequest<Paginated<BookingCampaign>>(`${path}?page=${page}`),
    refetchInterval: (query) => query.state.data?.results.some((row) => ["queued", "sending"].includes(row.status)) ? 5000 : false });
  const refresh = () => client.invalidateQueries({ queryKey: key });
  const compose = useMutation({ mutationFn: (input: BookingCampaignInput) => staffRequest<BookingCampaign>(path,
    { method: "POST", body: JSON.stringify(input) }), onSuccess: refresh });
  const action = useMutation({ mutationFn: ({ id, action }: { id: number; action: "queue" | "cancel" }) =>
    staffRequest<BookingCampaign>(`${path}${id}/${action}/`, { method: "POST", body: "{}" }), onSuccess: refresh });
  return { history, compose, action };
}
