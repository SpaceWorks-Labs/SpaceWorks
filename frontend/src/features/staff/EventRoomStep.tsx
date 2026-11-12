import { t } from "@lingui/core/macro";
import { useQuery } from "@tanstack/react-query";
import { useContext, useState } from "react";

import { staffRequest } from "../../lib/api";
import { StaffListContext } from "./StaffListContext";
import { bookingAccess } from "./bookingStaffPermissions";
import type { BookableSpace, Paginated } from "./bookingsApi";
import { useEventRoomChoices, type EventRoomChoice, type RoomMode, type RoomStep } from "./eventVenueApi";
import { EventRoomBookingChoices, EventRoomMemberPrice } from "./EventRoomStepParts";
import { StaffBookingAvailability } from "./StaffBookingAvailability";
import { PagePager } from "../../components/ui";
import { LogoLoader } from "../../components/LogoLoader";

export type RoomChoice = { mode: "none" | RoomMode; space_id: number; member_id: number; booking_id: number; price_confirmation: string; note: string };
export const emptyRoomChoice: RoomChoice = { mode: "none", space_id: 0, member_id: 0, booking_id: 0, price_confirmation: "", note: "" };

/** The `room` body for `events/with-room`, or null when the choice is incomplete (or "no room"). */
export function roomStepPayload(choice: RoomChoice): RoomStep | null {
  const note = choice.note.trim() ? { note: choice.note.trim() } : {};
  if (choice.mode === "link") return choice.booking_id ? { mode: "link", booking_id: choice.booking_id } : null;
  if (choice.mode === "none" || !choice.space_id) return null;
  if (choice.mode === "book") return choice.member_id && choice.price_confirmation
    ? { mode: "book", space_id: choice.space_id, member_id: choice.member_id, price_confirmation: choice.price_confirmation, ...note } : null;
  return { mode: choice.mode, space_id: choice.space_id, ...note };
}

function iso(local: string) {
  const date = new Date(local);
  return local && !Number.isNaN(date.getTime()) ? date.toISOString() : "";
}

/**
 * Decision 223 G6: the optional Venue step of "New event". The organizer sees the room's
 * capacity, approval mode and free/busy for the event window before the draft is created;
 * the server then requests, books, house-books or links the room in the same call.
 */
export function EventRoomStep({ makerspaceId, start, end, capacity, value, onChange }: {
  makerspaceId: number; start: string; end: string; capacity: number; value: RoomChoice; onChange: (next: RoomChoice) => void;
}) {
  const { actions, isSuperadmin } = useContext(StaffListContext);
  const [page, setPage] = useState(1);
  const rooms = useQuery({ queryKey: ["bookings", makerspaceId, "spaces", "event-room-step", page], retry: false,
    queryFn: () => staffRequest<Paginated<BookableSpace>>(`/admin/makerspaces/${makerspaceId}/spaces/?page=${page}`) });
  const eligible = (rooms.data?.results ?? []).filter(room => room.is_active && room.kind !== "machine" && room.machine == null);
  const room = eligible.find(row => row.id === value.space_id);
  // An organizer without the booking role cannot list `spaces/`; a room request reads the
  // id/name/capacity-only room choices instead (0.12.0), so "Request a room" is never empty for them.
  const useChoices = !isSuperadmin && !actions?.includes("manage_bookings") && value.mode === "request";
  const choices = useEventRoomChoices(makerspaceId, useChoices);
  const options: Omit<EventRoomChoice, "status">[] = useChoices ? choices.data?.results ?? []
    : eligible.map(row => ({ id: row.id, name: row.name, capacity: row.capacity, needs_approval: row.approval_mode === "approve" }));
  const listing = useChoices ? choices : rooms;
  const option = options.find(row => row.id === value.space_id);
  const manages = (space?: BookableSpace) => Boolean(isSuperadmin || actions?.includes("manage_bookings") || (space && bookingAccess(space).reservations));
  const canLink = Boolean(isSuperadmin || (actions?.includes("manage_events") && actions.includes("manage_bookings")));
  const startsAt = iso(start);
  const endsAt = iso(end);
  const windowReady = Boolean(startsAt && endsAt && endsAt > startsAt);
  const set = (patch: Partial<RoomChoice>) => onChange({ ...value, ...patch });
  const modes: { mode: RoomChoice["mode"]; label: string; hint: string; show: boolean }[] = [
    { mode: "none", label: t`No room for now`, hint: t`You can link a room later from the event.`, show: true },
    { mode: "request", label: t`Request a room`, hint: t`Books the room in your name. Rooms that need approval stay pending and hold the time tentatively.`, show: true },
    { mode: "house", label: t`House booking (no member, no charge)`, hint: t`For events the space runs itself. Confirmed straight away; uses no plan hours.`, show: manages() || eligible.some(manages) },
    { mode: "book", label: t`Book for a member`, hint: t`The member is the booker and any room charge is theirs.`, show: manages() || eligible.some(manages) },
    { mode: "link", label: t`Link an existing booking`, hint: t`The booking must cover the whole event.`, show: canLink },
  ];
  return <fieldset className="grid gap-3 rounded-lg border border-line p-3 text-sm" aria-describedby="event-room-step-help">
    <legend className="px-1 font-semibold text-ink">{t`Venue (optional)`}</legend>
    <p id="event-room-step-help" className="text-muted">{t`Choose how this event gets its room. Nothing is published or charged until you publish.`}</p>
    <div className="grid gap-2" role="radiogroup" aria-label={t`Room option`}>
      {modes.filter(row => row.show).map(row => <label key={row.mode} className="flex min-h-11 items-start gap-2">
        <input type="radio" name="event-room-mode" className="mt-1 h-4 w-4" checked={value.mode === row.mode}
          onChange={() => onChange({ ...emptyRoomChoice, mode: row.mode, space_id: value.space_id, note: value.note })} />
        <span><span className="font-medium text-ink">{row.label}</span><span className="block text-muted">{row.hint}</span></span>
      </label>)}
    </div>
    {value.mode !== "none" ? <>
      {!windowReady ? <p role="status" className="text-muted">{t`Set the event's start and end first to check rooms for that time.`}</p> : null}
      {listing.isPending ? <LogoLoader label={t`Loading rooms…`} size={48} className="min-h-16 py-3" /> : null}
      {listing.isError || (listing.isSuccess && !options.length) ? <p role="alert">{t`No rooms are available to you here. Ask a Booking Manager, or create the event without a room.`}</p> : null}
      {options.length ? <label className="grid gap-1">{t`Room`}
        <select className="desk-input" value={value.space_id} onChange={change => set({ space_id: Number(change.target.value), member_id: 0, booking_id: 0, price_confirmation: "" })}>
          <option value={0}>{t`Select a room`}</option>
          {options.map(row => <option key={row.id} value={row.id}>{row.name}{row.capacity ? ` · ${t`${row.capacity} places`}` : ""}{row.needs_approval ? ` · ${t`needs approval`}` : ""}</option>)}
        </select></label> : null}
      {!useChoices ? <PagePager page={page} setPage={setPage} next={rooms.data?.next} /> : null}
      {option && capacity > 0 && option.capacity > 0 && capacity > option.capacity
        ? <p role="status" className="text-warn-ink">{t`The event allows ${capacity} places but ${option.name} holds ${option.capacity}. You can still continue.`}</p> : null}
      {option && option.needs_approval && value.mode === "request"
        ? <p className="text-muted">{t`${option.name} needs approval. The request waits in the Booking Manager's queue with this event's name.`}</p> : null}
      {room && windowReady && manages(room) ? <StaffBookingAvailability spaceId={room.id} start={start} end={end} /> : null}
      {room && windowReady && value.mode === "book" ? <EventRoomMemberPrice space={room} startsAt={startsAt} endsAt={endsAt} value={value} onChange={set} /> : null}
      {room && windowReady && value.mode === "link" ? <EventRoomBookingChoices spaceId={room.id} startsAt={startsAt} endsAt={endsAt} value={value.booking_id} onChange={id => set({ booking_id: id })} /> : null}
      {value.mode !== "link" ? <label className="grid gap-1">{t`Note for the booking (optional)`}
        <textarea className="desk-input" maxLength={5000} value={value.note} onChange={change => set({ note: change.target.value })} /></label> : null}
    </> : null}
  </fieldset>;
}
