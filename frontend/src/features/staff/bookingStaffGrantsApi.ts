import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { staffRequest } from "../../lib/api";
import type { Paginated, BookableSpace } from "./bookingsApi";
import type { BookingPermission } from "./bookingStaffPermissions";

export type BookingStaffGrant = {
  id: number; makerspace: number; space: number;
  user: number; permissions: BookingPermission[]; granted_by: number | null;
  created_at: string; revoked_at: string | null; revoked_by: number | null;
};
export type BookingStaffInvite = {
  id: number; permissions: BookingPermission[]; expires_at: string;
  redeemed_at: string | null; revoked_at: string | null;
};
export type StaffGrantTarget = { id: number };
const base = (target: StaffGrantTarget) => `/admin/spaces/${target.id}`;
export const bookingStaffGrantKeys = {
  resource: (target: StaffGrantTarget) => ["booking-staff-access", target.id] as const,
  accessible: ["bookings", "accessible"] as const,
};

export function useBookingStaffGrants(target: StaffGrantTarget, page: number) {
  return useQuery({ queryKey: [...bookingStaffGrantKeys.resource(target), "grants", page],
    queryFn: () => staffRequest<Paginated<BookingStaffGrant>>(`${base(target)}/staff-grants/?page=${page}`) });
}
export function useBookingStaffInvites(target: StaffGrantTarget, page: number) {
  return useQuery({ queryKey: [...bookingStaffGrantKeys.resource(target), "invites", page],
    queryFn: () => staffRequest<Paginated<BookingStaffInvite>>(`${base(target)}/staff-invites/?page=${page}`) });
}
export function useBookingStaffGrantActions(target: StaffGrantTarget) {
  const client = useQueryClient();
  const invalidate = async () => { await Promise.all([
    client.invalidateQueries({ queryKey: bookingStaffGrantKeys.resource(target) }),
    client.invalidateQueries({ queryKey: bookingStaffGrantKeys.accessible }),
    client.invalidateQueries({ queryKey: ["booking-space", target.id] }),
  ]); };
  const invite = useMutation({ mutationFn: (payload: { email: string; send_email: boolean; permissions: BookingPermission[] }) =>
    staffRequest<BookingStaffInvite & { token: string }>(`${base(target)}/staff-invites/`, {
      method: "POST", body: JSON.stringify(payload),
    }), onSuccess: invalidate });
  const update = useMutation({ mutationFn: ({ id, permissions }: { id: number; permissions: BookingPermission[] }) =>
    staffRequest<BookingStaffGrant>(`/admin/booking-staff-grants/${id}/`, {
      method: "PATCH", body: JSON.stringify({ permissions }),
    }), onSuccess: invalidate });
  const revoke = useMutation({ mutationFn: (id: number) => staffRequest<BookingStaffGrant>(`/admin/booking-staff-grants/${id}/revoke/`, {
    method: "POST", body: JSON.stringify({}),
  }), onSuccess: invalidate });
  const revokeInvite = useMutation({ mutationFn: (id: number) => staffRequest<BookingStaffInvite>(`/admin/booking-staff-invites/${id}/revoke/`, {
    method: "POST", body: JSON.stringify({}),
  }), onSuccess: invalidate });
  return { invite, update, revoke, revokeInvite };
}
export function useAccessibleBookingSpaces(page: number, makerspaceId?: number) {
  return useQuery({ queryKey: [...bookingStaffGrantKeys.accessible, makerspaceId ?? "all", page],
    queryFn: () => staffRequest<Paginated<BookableSpace>>(`/admin/accessible-booking-spaces/?page=${page}${makerspaceId ? `&makerspace_id=${makerspaceId}` : ""}`),
    refetchInterval: 60_000 });
}
