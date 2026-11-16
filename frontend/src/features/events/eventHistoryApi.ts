import { useQuery } from "@tanstack/react-query";

import { memberRequest, staffRequest } from "../../lib/api";

/** Hand-typed from the Phase 2 events contract; both history routes share this shape. */
export type HistoryEvent = { id: number; title: string; starts_at: string; ends_at: string; location: string; status: string };
export type EventHistory = {
  counts: { registered: number; attended: number; cancelled: number; speaking: number };
  /** Newest first, at most 50. */
  registrations: { registration_id: number; status: string; event: HistoryEvent }[];
  /** Newest first, at most 50. */
  speaking: { speaker_id: number; role: "speaker"; occurred_at: string; event: HistoryEvent }[];
};

export const eventHistoryKeys = {
  member: (makerspaceId: number, accountId: number | undefined) => ["member", "event-history", makerspaceId, accountId ?? "me"] as const,
  staff: (makerspaceId: number, userId: number) => ["members", makerspaceId, "member-events", userId] as const,
};

/**
 * The signed-in account's own history here. Works for an account-only attendee (no membership,
 * no membership module); the server answers 403 when the account has nothing here to show.
 */
export function useMemberEventHistory(makerspaceId: number | undefined, accountId?: number, enabled = true) {
  return useQuery({ queryKey: eventHistoryKeys.member(makerspaceId ?? -1, accountId), retry: false,
    enabled: enabled && makerspaceId !== undefined && makerspaceId >= 0,
    queryFn: () => memberRequest<EventHistory>(`/member/makerspaces/${makerspaceId}/event-history/`) });
}

/** One member's events, for the staff member drawer. Needs manage_events or manage_members here. */
export function useStaffMemberEventHistory(makerspaceId: number, userId: number) {
  return useQuery({ queryKey: eventHistoryKeys.staff(makerspaceId, userId), retry: false,
    queryFn: () => staffRequest<EventHistory>(`/admin/makerspaces/${makerspaceId}/members/${userId}/events/`) });
}
