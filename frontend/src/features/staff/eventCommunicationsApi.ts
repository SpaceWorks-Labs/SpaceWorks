import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { staffRequest, staffRequestBlob } from "../../lib/api";
import { eventKeys, type Paginated } from "./eventsApiTypes";

export type EventCampaign = {
  id: number; subject: string; body: string; statuses: string[]; attendance: string;
  status: "draft" | "queued" | "sending" | "sent" | "cancelled" | "failed"; created_at: string;
};
export type CampaignInput = Pick<EventCampaign, "subject" | "body" | "statuses" | "attendance">;
export const communicationKeys = {
  campaigns: (tenant: number, event: number) => ["event-broadcasts", tenant, event] as const,
  analytics: (tenant: number, event: number) => [...eventKeys.detail(event), "analytics", tenant] as const,
};

export function useEventBroadcasts(tenant: number, event: number, page: number) {
  const client = useQueryClient();
  const key = communicationKeys.campaigns(tenant, event);
  const path = `/admin/events/${event}/broadcasts/`;
  const history = useQuery({ queryKey: [...key, page],
    queryFn: () => staffRequest<Paginated<EventCampaign>>(`${path}?page=${page}`),
    refetchInterval: (query) => query.state.data?.results.some((row) => ["queued", "sending"].includes(row.status)) ? 5000 : false });
  const refresh = () => client.invalidateQueries({ queryKey: key });
  const compose = useMutation({ mutationFn: (input: CampaignInput) => staffRequest<EventCampaign>(path,
    { method: "POST", body: JSON.stringify(input) }), onSuccess: refresh });
  const action = useMutation({ mutationFn: ({ id, action }: { id: number; action: "queue" | "cancel" }) =>
    staffRequest<EventCampaign>(`${path}${id}/${action}/`, { method: "POST", body: "{}" }), onSuccess: refresh });
  return { history, compose, action };
}

export function useBulkEventInvites(event: number) {
  const client = useQueryClient();
  return useMutation({ mutationFn: (emails: string[]) => staffRequest<{ created: number }>(`/admin/events/${event}/invites/bulk/`,
    { method: "POST", body: JSON.stringify({ emails, send_email: true }) }),
    onSuccess: () => client.invalidateQueries({ queryKey: ["event", event, "invites"] }) });
}

export function useEventAnalytics(tenant: number, event: number) {
  const filters = `subject_kind=event&subject_id=${event}`;
  const path = `/admin/makerspace/${tenant}`;
  const query = useQuery({ queryKey: communicationKeys.analytics(tenant, event), queryFn: () =>
    staffRequest<{ typed_rows: Record<string, unknown>[] }>(`${path}/analytics/event-attendance?${filters}`) });
  const download = useMutation({ mutationFn: ({ key, format }: { key: string; format: "csv" | "pdf" }) =>
    staffRequestBlob(`${path}/reports/${key}/export?${filters}&format=${format}`) });
  return { query, download };
}
