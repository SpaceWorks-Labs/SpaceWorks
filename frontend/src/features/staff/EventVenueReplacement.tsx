import { t } from "@lingui/core/macro";
import { useQuery } from "@tanstack/react-query";
import { useRef, useState } from "react";

import { bookingAccess } from "./bookingStaffPermissions";
import type { BookableSpace, Paginated } from "./bookingsApi";
import { useBookingEligibleMembers, type StaffBookingQuote } from "./staffBookingApi";
import { changedConfirmation, StaffPriceConfirmation } from "./StaffPriceConfirmation";
import { StaffBookingAvailability, toLocalInput } from "./StaffBookingAvailability";
import { certificationText } from "./eventEquipment/machineLinkErrors";
import { PagePager } from "../../components/ui";

type Request = <Result>(url: string, init: RequestInit) => Promise<Result>;
type Props = {
  makerspaceId: number; eventId: number; expectedBookingId: number;
  currentWindow: { starts_at: string; ends_at: string } | null | undefined;
  request: Request; queryKey: readonly unknown[]; onReplaced: () => Promise<void> | void;
  /** P2-1: replace a workshop machine link's booking with one machine's time instead of a room. */
  workshopLinkId?: number;
};

/**
 * Decision 216: book a replacement for the event's rejected or cancelled reservation. The
 * server routes it through ordinary booking admission, availability, pricing and approval;
 * the event keeps its original link and every earlier booking keeps its own debt.
 */
export function EventVenueReplacement({ makerspaceId, eventId, expectedBookingId, currentWindow, request, queryKey, onReplaced, workshopLinkId }: Props) {
  const machine = workshopLinkId !== undefined;
  const [roomId, setRoomId] = useState(0);
  const rooms = useQuery({ queryKey: [...queryKey, "replacement-rooms", workshopLinkId ?? 0], retry: false, gcTime: 0,
    queryFn: ({ signal }) => request<Paginated<BookableSpace>>(`/admin/makerspaces/${makerspaceId}/spaces/?page=1`, { signal }) });
  const eligible = (rooms.data?.results ?? []).filter(room => room.makerspace_id === makerspaceId && room.is_active &&
    (machine ? room.machine != null : room.kind !== "machine" && room.machine == null) && bookingAccess(room).reservations);
  const room = eligible.find(row => row.id === roomId);
  return <fieldset className="grid gap-2">
    <legend className="text-sm font-semibold text-ink">{machine ? t`Replace the machine booking` : t`Replace the room booking`}</legend>
    <p className="text-sm text-muted">{t`The earlier booking stays on record with its own charges and receipts.`}</p>
    <label className="grid gap-1 text-sm">{machine ? t`Machine` : t`Room`}<select className="desk-input" value={roomId} onChange={event => setRoomId(Number(event.target.value))}>
      <option value={0}>{rooms.isPending ? (machine ? t`Loading machines…` : t`Loading rooms…`) : machine ? t`Select a machine` : t`Select a room`}</option>
      {eligible.map(row => <option key={row.id} value={row.id}>{row.name}</option>)}
    </select></label>
    {rooms.isError ? <p className="text-sm text-danger" role="alert">{t`Booking choices are unavailable.`}</p> : null}
    {rooms.isSuccess && !eligible.length ? <p className="text-sm text-muted">{machine ? t`No active machine here takes staff reservations.` : t`No active room here takes staff reservations.`}</p> : null}
    {room ? <ReplacementForm key={room.id} room={room} makerspaceId={makerspaceId} eventId={eventId}
      expectedBookingId={expectedBookingId} currentWindow={currentWindow} request={request} onReplaced={onReplaced}
      workshopLinkId={workshopLinkId} /> : null}
  </fieldset>;
}

function ReplacementForm({ room, makerspaceId, eventId, expectedBookingId, currentWindow, request, onReplaced, workshopLinkId }:
  Omit<Props, "queryKey"> & { room: BookableSpace }) {
  const [page, setPage] = useState(1);
  const [memberId, setMemberId] = useState("");
  const [start, setStart] = useState(toLocalInput(currentWindow?.starts_at));
  const [end, setEnd] = useState(toLocalInput(currentWindow?.ends_at));
  const [confirmation, setConfirmation] = useState<StaffBookingQuote | null>(null);
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState("");
  const ticket = useRef(0);
  const machine = workshopLinkId !== undefined;
  const members = useBookingEligibleMembers(room.id, page);
  const unconfirm = () => { ticket.current += 1; setConfirmation(null); setMessage(""); };
  const slot = () => ({ member_id: Number(memberId), starts_at: new Date(start).toISOString(), ends_at: new Date(end).toISOString() });
  async function act() {
    const mine = ++ticket.current;
    setPending(true); setMessage("");
    try {
      if (!confirmation) {
        const shown = await request<StaffBookingQuote>(`/admin/spaces/${room.id}/bookings/quote/`,
          { method: "POST", body: JSON.stringify(slot()) });
        if (mine === ticket.current) setConfirmation(shown);
        return;
      }
      const path = workshopLinkId === undefined ? "booking-link/replacement" : `workshop-machines/${workshopLinkId}/replacement`;
      await request(`/admin/makerspace/${makerspaceId}/events/${eventId}/${path}`, {
        method: "POST", body: JSON.stringify({ expected_booking_id: expectedBookingId, space_id: room.id,
          ...slot(), price_confirmation: confirmation.price_confirmation }) });
      await onReplaced();
    } catch (error) {
      if (mine !== ticket.current) return;
      const next = changedConfirmation(error);
      setConfirmation(next);
      setMessage(next ? (machine ? t`The machine time price changed. Review the new price before replacing.` : t`The room price changed. Review the new price before replacing.`)
        : certificationText(error) ?? (error instanceof Error ? error.message : t`The booking could not be replaced.`));
    } finally {
      if (mine === ticket.current) setPending(false);
    }
  }
  return <div className="grid gap-2">
    <label className="grid gap-1 text-sm">{t`Member`}<select className="desk-input" value={memberId} onChange={event => { setMemberId(event.target.value); unconfirm(); }}>
      <option value="">{members.isLoading ? t`Loading members…` : t`Select a member`}</option>
      {members.data?.results.map(member => <option key={member.member_id} value={member.member_id}>{member.display_name}</option>)}
    </select></label>
    <PagePager page={page} setPage={next => { setPage(next); setMemberId(""); unconfirm(); }} next={members.data?.next} />
    <label className="grid gap-1 text-sm">{t`Starts (your local time)`}<input className="desk-input" type="datetime-local" value={start} onChange={event => { setStart(event.target.value); unconfirm(); }} /></label>
    <label className="grid gap-1 text-sm">{t`Ends (your local time)`}<input className="desk-input" type="datetime-local" value={end} onChange={event => { setEnd(event.target.value); unconfirm(); }} /></label>
    <StaffBookingAvailability spaceId={room.id} start={start} end={end} />
    {confirmation ? <StaffPriceConfirmation confirmation={confirmation} approval={room.approval_mode === "approve"} machine={machine} /> : null}
    {message ? <p className="text-sm text-danger" role="alert">{message}</p> : null}
    <button type="button" className="desk-button w-fit" disabled={pending || !memberId || !start || !end} onClick={() => { void act(); }}>
      {confirmation ? t`Confirm price and replace booking` : t`Review price`}</button>
  </div>;
}
