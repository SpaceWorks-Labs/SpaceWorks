import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { staffRequest } from "../../lib/api";
import type { Paginated, StaffEvent } from "./eventsApi";
import type { EventPermission } from "./eventStaffPermissions";

export type EventStaffGrant = {
  id: number; makerspace: number; event: number | null; series: number | null;
  user: number; permissions: EventPermission[]; role_label?: string; granted_by: number | null;
  created_at: string; revoked_at: string | null; revoked_by: number | null;
};
export type EventStaffInvite = {
  id: number; permissions: EventPermission[]; role_label?: string; expires_at: string;
  redeemed_at: string | null; revoked_at: string | null;
  // Decision 221(i): [] = every track; null = no start/end limit.
  track_ids?: number[]; valid_from?: string | null; valid_until?: string | null;
};
export type EventStaffInvitePayload = {
  email: string; send_email: boolean; permissions: EventPermission[]; role_label?: string;
  track_ids?: number[]; valid_from?: string | null; valid_until?: string | null;
};
export type StaffGrantTarget = { kind: "event" | "series"; id: number };
const base = (target: StaffGrantTarget) => `/admin/${target.kind === "event" ? "events" : "event-series"}/${target.id}`;
export const eventStaffGrantKeys = {
  resource: (target: StaffGrantTarget) => ["event-staff-access", target.kind, target.id] as const,
  accessible: ["events", "accessible"] as const,
};

export function useEventStaffGrants(target: StaffGrantTarget, page: number, enabled = true) {
  return useQuery({ queryKey: [...eventStaffGrantKeys.resource(target), "grants", page], enabled,
    queryFn: () => staffRequest<Paginated<EventStaffGrant>>(`${base(target)}/staff-grants/?page=${page}`) });
}
export function useEventStaffInvites(target: StaffGrantTarget, page: number) {
  return useQuery({ queryKey: [...eventStaffGrantKeys.resource(target), "invites", page],
    queryFn: () => staffRequest<Paginated<EventStaffInvite>>(`${base(target)}/staff-invites/?page=${page}`) });
}
export function useEventStaffGrantActions(target: StaffGrantTarget) {
  const client = useQueryClient();
  const invalidate = async () => { await Promise.all([
    client.invalidateQueries({ queryKey: eventStaffGrantKeys.resource(target) }),
    client.invalidateQueries({ queryKey: eventStaffGrantKeys.accessible }),
    client.invalidateQueries({ queryKey: target.kind === "event" ? ["event", target.id] : ["event-series", target.id, "detail"] }),
  ]); };
  const invite = useMutation({ mutationFn: (payload: EventStaffInvitePayload) =>
    staffRequest<EventStaffInvite & { token: string }>(`${base(target)}/staff-invites/`, {
      method: "POST", body: JSON.stringify(payload),
    }), onSuccess: invalidate });
  const update = useMutation({ mutationFn: ({ id, permissions, role_label }: { id: number; permissions: EventPermission[]; role_label?: string }) =>
    staffRequest<EventStaffGrant>(`/admin/event-staff-grants/${id}/`, {
      method: "PATCH", body: JSON.stringify(role_label === undefined ? { permissions } : { permissions, role_label }),
    }), onSuccess: invalidate });
  const revoke = useMutation({ mutationFn: (id: number) => staffRequest<EventStaffGrant>(`/admin/event-staff-grants/${id}/revoke/`, {
    method: "POST", body: JSON.stringify({}),
  }), onSuccess: invalidate });
  const revokeInvite = useMutation({ mutationFn: (id: number) => staffRequest<EventStaffInvite>(`/admin/event-staff-invites/${id}/revoke/`, {
    method: "POST", body: JSON.stringify({}),
  }), onSuccess: invalidate });
  return { invite, update, revoke, revokeInvite };
}
export function useAccessibleEvents(page: number, makerspaceId?: number) {
  return useQuery({ queryKey: [...eventStaffGrantKeys.accessible, makerspaceId ?? "all", page],
    queryFn: () => staffRequest<Paginated<StaffEvent>>(`/admin/accessible-events/?page=${page}${makerspaceId ? `&makerspace_id=${makerspaceId}` : ""}`),
    refetchInterval: 60_000 });
}
