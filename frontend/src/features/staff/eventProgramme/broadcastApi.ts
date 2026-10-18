import { useMutation, useQueryClient } from "@tanstack/react-query";
import { staffRequest } from "../../../lib/api";
import { communicationKeys } from "../eventCommunicationsApi";
import { isProtectedDenial } from "./sessionScope";
export type BroadcastCta = { kind: "https"; label: string; url: string } | { kind: "navigation"; label: string; target: "event" | "ticket" };
export type BroadcastDraft = { subject: string; body: string; statuses: string[]; attendance: string; render_schema_version: 2; design: "classic" | "bold" | "minimal"; ctas: BroadcastCta[] };
export type BroadcastCampaign = Omit<BroadcastDraft, "render_schema_version"> & { render_schema_version: 1 | 2; id: number; version: number; status: string; available_at: string | null };
export type BroadcastPreview = { preview_id: number; revision: string; recipient_count: number; desktop_html: string; mobile_html: string; subject: string; text: string };
export function useBroadcastCreate(tenant: number, event: number) {
  const client = useQueryClient();
  return useMutation({ mutationFn: ({ operation_id, draft }: { operation_id: string; draft: BroadcastDraft }) => staffRequest<BroadcastCampaign>(`/admin/events/${event}/broadcasts/`, { method: "POST", headers: { "Idempotency-Key": operation_id }, body: JSON.stringify(draft) }), onSuccess: () => client.invalidateQueries({ queryKey: communicationKeys.campaigns(tenant, event) }), onError: error => { if (isProtectedDenial(error)) void client.invalidateQueries({ queryKey: communicationKeys.campaigns(tenant, event) }); } });
}
export function useBroadcastCommand<T>(tenant: number, event: number, campaign: number, action: "preview" | "test" | "schedule" | "cancel") {
  const client = useQueryClient();
  return useMutation({ mutationFn: (body: Record<string, unknown> & { operation_id?: string }) => staffRequest<T>(`/admin/events/${event}/broadcasts/${campaign}/${action}/`, { method: "POST", ...(body.operation_id ? { headers: { "Idempotency-Key": body.operation_id } } : {}), body: JSON.stringify(body) }),
    onSuccess: () => client.invalidateQueries({ queryKey: communicationKeys.campaigns(tenant, event) }), onError: error => { if (isProtectedDenial(error)) void client.invalidateQueries({ queryKey: communicationKeys.campaigns(tenant, event) }); } });
}
