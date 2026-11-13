import { t } from "@lingui/core/macro";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { staffRequest } from "../../lib/api";
import { eventKeys, type EventCreatePayload, type StaffEvent } from "./eventsApiTypes";
import { organizedEventKeys } from "./organizedEventsApi";

/** Decision 223 (g, m): the read-only venue panel the publish dialog and co-organizers read. Hand-typed. */
export type VenueStateName = "none" | "confirmed" | "pending" | "blocked";
export type VenueState = {
  state: VenueStateName;
  reason: "" | "rejected" | "cancelled" | "missing" | "unavailable" | string;
  booking_id: number | null;
  booking_status?: string;
  space_id?: number;
  space_name?: string;
  coverage?: "covers" | "not_covered";
  is_house?: boolean;
};
export type VenueWarning = { code: string; event_capacity?: number; room_capacity?: number };
export type VenueOffer = {
  action: "cancel_booking" | "move_booking" | "change_venue_fee";
  booking_id: number | null;
  route: string;
  allowed: boolean;
  proposed_window?: { starts_at: string; ends_at: string } | null;
  fee_status?: string | null;
};
export type VenuePanel = {
  event_id: number;
  event_status: string;
  event_window: { starts_at: string; ends_at: string };
  venue: VenueState;
  warnings: VenueWarning[];
  requires_override: boolean;
  can_publish: boolean;
  venue_fee: { will_charge_on_publish: boolean; payer_id?: number | null; mode?: string } | null;
  offers: VenueOffer[];
  can_manage_booking: boolean;
};

export type RoomMode = "request" | "book" | "house" | "link";
export type RoomStep = {
  mode: RoomMode;
  space_id?: number;
  member_id?: number;
  booking_id?: number;
  price_confirmation?: string;
  note?: string;
};
export type RoomResult = {
  mode: RoomMode;
  status: "linked" | "failed";
  booking_id: number | null;
  booking_status: string | null;
  code?: string;
  detail?: string;
  orphan_booking_id?: number | null;
};

/** One room an organizer may pick in the room step, even without a booking role (0.12.0). Hand-typed. */
export type EventRoomChoice = {
  id: number;
  name: string;
  capacity: number;
  needs_approval: boolean;
  status: "available" | "approval_required";
};

export const venueKeys = {
  panel: (makerspaceId: number, eventId: number) => ["event-venue", makerspaceId, eventId] as const,
  roomChoices: (makerspaceId: number) => ["event-venue", makerspaceId, "room-choices"] as const,
};

/** `manage_events` + bookings module: the rooms an organizer may request, without booker identities. */
export function useEventRoomChoices(makerspaceId: number, enabled: boolean) {
  return useQuery({
    queryKey: venueKeys.roomChoices(makerspaceId), enabled, retry: false,
    queryFn: ({ signal }) => staffRequest<{ results: EventRoomChoice[] }>(
      `/admin/makerspace/${makerspaceId}/event-room-choices`, { signal }),
  });
}

export function useEventVenue(makerspaceId: number, eventId: number, enabled = true) {
  return useQuery({
    queryKey: venueKeys.panel(makerspaceId, eventId), enabled, retry: false,
    queryFn: ({ signal }) => staffRequest<VenuePanel>(`/admin/makerspace/${makerspaceId}/events/${eventId}/venue`, { signal }),
  });
}

export function useCreateEventWithRoom(makerspaceId: number) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: { event: EventCreatePayload; room: RoomStep }) => staffRequest<{ event: StaffEvent; room: RoomResult }>(
      `/admin/makerspace/${makerspaceId}/events/with-room`, { method: "POST", body: JSON.stringify(body) }),
    onSuccess: async ({ event }) => { await Promise.all([
      client.invalidateQueries({ queryKey: eventKeys.list(makerspaceId) }),
      client.invalidateQueries({ queryKey: eventKeys.detail(event.id) }),
      client.invalidateQueries({ queryKey: organizedEventKeys.all }),
      client.invalidateQueries({ queryKey: ["events", "accessible"] }),
      client.invalidateQueries({ queryKey: ["booking-queue", makerspaceId] }),
      client.invalidateQueries({ queryKey: ["booking-space"] }),
      client.invalidateQueries({ queryKey: ["bookings", makerspaceId] }),
    ]); },
  });
}

/** Plain-language venue state for every venue surface. */
export function venueStateText(venue: VenueState) {
  const room = venue.space_name ?? t`the room`;
  if (venue.state === "none") return t`No room is linked to this event.`;
  if (venue.state === "confirmed") return venue.is_house ? t`${room} is booked for this event (house booking).` : t`${room} is booked for this event.`;
  if (venue.state === "pending") return t`${room} is requested and awaits approval. Its time is held tentatively.`;
  if (venue.reason === "rejected") return t`The booking for ${room} was rejected.`;
  if (venue.reason === "cancelled") return t`The booking for ${room} was cancelled.`;
  if (venue.reason === "unavailable") return t`${room} is no longer bookable.`;
  return t`The linked room booking no longer exists.`;
}

export function venueWarningText(warning: VenueWarning) {
  switch (warning.code) {
    case "venue_pending": return t`The room booking is still awaiting approval. The event can be published, but the room is not confirmed yet.`;
    case "venue_not_covered": return t`The room booking does not cover the whole event time. Move the booking or change the event time.`;
    case "event_capacity_above_room": return warning.event_capacity && warning.room_capacity
      ? t`The event allows ${warning.event_capacity} places but the room holds ${warning.room_capacity}.`
      : t`The event allows more places than the room holds.`;
    case "audience_falls_back_to_accounts": return t`Membership is off, so publishing opens registration to any signed-in account instead of members only.`;
    default: return t`Check the venue before publishing.`;
  }
}

/** Copy for the room-step failure codes the server reports (`room.code`). */
export function roomFailureText(result: Pick<RoomResult, "code" | "detail">) {
  switch (result.code) {
    case "room_unavailable": return t`The room is already booked at this time.`;
    case "room_out_of_service": return t`The room is out of service during the event.`;
    case "booking_does_not_cover_event": return t`That booking does not cover the event's time.`;
    case "price_changed": return t`The room price changed. Review the price again from the venue panel.`;
    case "not_found": return t`The room or booking is not available to you.`;
    case "permission_denied": return t`You are not allowed to book this room.`;
    default: return result.detail || t`The room step could not be completed.`;
  }
}
