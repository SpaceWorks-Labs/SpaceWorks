import { t } from "@lingui/core/macro";
import { RouteLink } from "../../components/ui/RouteLink";
import { useCrossLink } from "./crossLinks/staffHref";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useContext, useRef, useState } from "react";

import { staffRequest, StructuredApiError } from "../../lib/api";
import { getSessionOwner } from "../../lib/api/sessionTokens";
import { useIntakeScope } from "../inventory/useIntakeScope";
import { formatLocale } from "../../lib/format";
import { StaffListContext } from "./StaffListContext";
import { bookingAccess } from "./bookingStaffPermissions";
import { StaffBookingReadiness } from "./BookingReadiness";
import type { BookableSpace, Booking, Paginated } from "./bookingsApi";
import type { VenueConflict } from "./EventVenueConflicts";
import { EventVenueNotices } from "./EventVenueNotices";
import { EventVenueReplacement } from "./EventVenueReplacement";
import { EventWorkshopMachines } from "./EventWorkshopMachines";
import { venueWarningText, type VenueWarning } from "./eventVenueApi";
import { StaffBookingForm } from "./StaffBookingForm";
import { EventPanelPager } from "./EventPanelPager";

type Window = { starts_at: string; ends_at: string };
type Link = {
  generation: string | null;
  revision: number;
  events_epoch: string;
  bookings_epoch: string;
  state: "absent" | "linked" | "booking_unavailable";
  booking_id: number | null;
  billing_owner: "booking" | null;
  event_window?: Window;
  booking_window?: Window | null;
  reservation_state?: "pending" | "confirmed" | "historical" | "unavailable";
  sync: "matched" | "different" | "unavailable";
  fee_state?: "none" | "free_no_debt" | "configured" | "historical_debt";
  current_booking_id?: number | null;
  replaceable?: boolean;
  history?: { booking_id: number; status: string }[];
  event_status?: "draft" | "published" | "cancelled" | "completed";
  coverage?: "covers" | "not_covered";
  current_space_id?: number;
  conflicts?: VenueConflict[];
};
type LinkBody = {
  operation_id: string;
  expected_generation: string | null;
  expected_revision: number;
  expected_events_epoch: string;
  expected_bookings_epoch: string;
  confirm_billing_owner: "booking";
  existing_booking_id: number;
  /** Decision 223 G4: link a booking that covers only part of the event (audited). */
  allow_partial_coverage?: boolean;
};
type Scope = { makerspaceId: number; eventId: number; readOnly: boolean; active?: boolean };

function displayWindow(window: Window) {
  const format = (value: string) => new Date(value).toLocaleString(formatLocale());
  return `${format(window.starts_at)} – ${format(window.ends_at)}`;
}

export function EventVenueBookingPanel(props: Scope) {
  const { actorId, makerspace, actions, isSuperadmin } = useContext(StaffListContext);
  const modules = makerspace?.enabled_modules;
  const session = useIntakeScope();
  if (!actorId || session.owner !== String(actorId) || makerspace?.id !== props.makerspaceId ||
      !modules?.includes("events") || !modules.includes("bookings") ||
      !(isSuperadmin || actions?.includes("manage_events") && actions.includes("manage_bookings"))) return null;
  return <VenueBooking key={JSON.stringify([session.context, actorId, props.makerspaceId, props.eventId])} {...props} actorId={actorId} context={session.context} />;
}

function VenueBooking({ makerspaceId, eventId, actorId, readOnly, active = true, context }: Scope & { actorId: number; context: ReturnType<typeof useIntakeScope>["context"] }) {
  const client = useQueryClient();
  const crossLink = useCrossLink();
  const [open, setOpen] = useState(false);
  const [roomPage, setRoomPage] = useState(1);
  const [bookingPage, setBookingPage] = useState(1);
  const [roomId, setRoomId] = useState(0);
  const [bookingId, setBookingId] = useState(0);
  const [confirmed, setConfirmed] = useState(false);
  // 3B handoff: a booking just created here is only a CANDIDATE until staff confirm the link.
  const [bookingOpen, setBookingOpen] = useState(false);
  const [candidate, setCandidate] = useState(0);
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState("");
  const [uncertain, setUncertain] = useState(false);
  // A link refused as partial coverage keeps its intent so staff can confirm "link anyway".
  const [partial, setPartial] = useState<LinkBody | null>(null);
  const [warnings, setWarnings] = useState<VenueWarning[]>([]);
  const intent = useRef<LinkBody | null>(null);
  const inFlight = useRef(false);
  const path = `/admin/makerspace/${makerspaceId}/events/${eventId}/booking-link`;
  const key = ["event-venue-booking", context, actorId, makerspaceId, eventId] as const;
  const request = <Result,>(url: string, init: RequestInit) => {
    if (getSessionOwner(context) !== String(actorId)) return Promise.reject(new Error(t`Staff session changed`));
    return staffRequest<Result>(url, init);
  };
  const query = useQuery({ queryKey: key, enabled: active && open, retry: false, gcTime: 0,
    queryFn: ({ signal }) => request<Link>(path, { signal }) });
  const link = !query.isError && !query.isFetching ? query.data : undefined;
  const canLink = !readOnly && link?.state === "absent" && (link.fee_state === "none" || link.fee_state === "free_no_debt");
  const rooms = useQuery({ queryKey: [...key, "rooms", roomPage], enabled: active && open && canLink && !uncertain,
    retry: false, gcTime: 0, queryFn: ({ signal }) => request<Paginated<BookableSpace>>(
      `/admin/makerspaces/${makerspaceId}/spaces/?page=${roomPage}`, { signal }) });
  const eligibleRooms = rooms.isError ? [] : (rooms.data?.results ?? []).filter(room =>
    room.makerspace_id === makerspaceId && room.is_active && room.kind !== "machine" && room.machine == null && bookingAccess(room).reservations);
  const roomSelected = eligibleRooms.some(room => room.id === roomId);
  const bookings = useQuery({ queryKey: [...key, "bookings", roomId, bookingPage],
    enabled: active && open && canLink && roomSelected && !uncertain, retry: false, gcTime: 0,
    queryFn: ({ signal }) => request<Paginated<Booking>>(
      `/admin/spaces/${roomId}/bookings/?page=${bookingPage}&ordering=starts_at`, { signal }) });
  const choices = bookings.isError ? [] : (bookings.data?.results ?? []).filter(booking =>
    booking.space_id === roomId && ["pending", "confirmed"].includes(booking.status));
  const choice = choices.find(booking => booking.id === bookingId);
  const room = eligibleRooms.find(row => row.id === roomId);
  const target = choice?.id ?? (candidate && roomSelected ? candidate : 0);

  async function linkBooking(anyway = false) {
    if (inFlight.current || !active || !open || !canLink || !link || getSessionOwner(context) !== String(actorId)) return;
    if (anyway && partial) intent.current = { ...partial, operation_id: crypto.randomUUID(), allow_partial_coverage: true };
    setPartial(null);
    if (!intent.current) {
      if (!confirmed || !Number.isSafeInteger(target) || target < 1) return;
      intent.current = {
        operation_id: crypto.randomUUID(), expected_generation: link.generation, expected_revision: link.revision,
        expected_events_epoch: link.events_epoch, expected_bookings_epoch: link.bookings_epoch,
        confirm_billing_owner: "booking", existing_booking_id: target,
      };
    }
    const body = intent.current;
    inFlight.current = true;
    setPending(true);
    setMessage("");
    try {
      const linked = await request<{ warnings?: VenueWarning[] }>(path, { method: "POST", body: JSON.stringify(body) });
      setWarnings(Array.isArray(linked?.warnings) ? linked.warnings : []);
      intent.current = null;
      setUncertain(false);
      setConfirmed(false);
      setCandidate(0);
      await client.invalidateQueries({ queryKey: key, exact: true });
    } catch (error) {
      if (!uncertain && error instanceof StructuredApiError && [400, 401, 403, 404, 409, 423].includes(error.status)) {
        intent.current = null;
        setConfirmed(false);
        if (error.code === "booking_does_not_cover_event" && !body.allow_partial_coverage) {
          setPartial(body);
          setMessage(t`This booking does not cover the whole event time. Link it anyway, or choose a booking that covers the event.`);
          return;
        }
        setMessage(error.code === "room_out_of_service"
          ? t`Room out of service: this room refuses bookings during the event. Choose another room or wait until it is back in service.`
          : t`The booking could not be linked. Review the current venue and billing information before trying again.`);
        await client.invalidateQueries({ queryKey: key, exact: true });
      } else {
        setUncertain(true);
        setMessage(t`The link could not be confirmed. Retry the same operation or check the current venue before starting again.`);
      }
    } finally {
      inFlight.current = false;
      setPending(false);
    }
  }

  const linkedBookingId = link?.current_booking_id ?? link?.booking_id;
  const bookingLink = linkedBookingId && link?.current_space_id
    ? crossLink("bookings", { space: link.current_space_id, booking: linkedBookingId, bookingTab: "requests" }) : undefined;
  return <section className="grid gap-2" data-replay-block>
    <button type="button" className="desk-button w-fit" disabled={pending} aria-expanded={open}
      onClick={() => setOpen(value => !value)}>{open ? t`Hide venue booking` : t`Manage venue booking`}</button>
    {open ? <>
      {query.isPending || query.isFetching ? <p role="status">{t`Checking venue booking…`}</p> : null}
      {query.isError ? <p role="alert">{t`The venue booking is unavailable for your access.`}</p> : null}
      {link?.state === "booking_unavailable" ? <p>{t`The original linked booking is unavailable. Review venue billing with staff.`}</p> : null}
      {link?.state === "linked" && link.event_window && link.booking_window ? <div>
        <p>{t`Booking #${link.current_booking_id ?? link.booking_id ?? ""} is linked and owns venue billing.`}</p>
        {/* EB8: the linked booking opens in its room's agenda in Bookings. */}
        {bookingLink ? <RouteLink className="desk-button w-fit" href={bookingLink}>{t`Open the booking in Bookings`}</RouteLink> : null}
        {link.history?.length ? <p>{t`Earlier bookings kept on record: ${link.history.map(row => `#${row.booking_id} (${row.status})`).join(", ")}`}</p> : null}
        <p>{t`Event: ${displayWindow(link.event_window)}`}</p>
        <p>{t`Booking: ${displayWindow(link.booking_window)}`}</p>
        {link.reservation_state === "pending" ? <p role="status">{t`The room booking is awaiting approval.`}</p> : null}
        {link.reservation_state === "unavailable" ? <p role="status">{t`The linked booking no longer reserves the room. Review the venue with staff.`}</p> : null}
        {link.reservation_state === "historical" ? <p>{t`This booking is retained for history.`}</p> : null}
        {link.sync === "different" ? <p role="status">{t`The event and booking times differ. Review both schedules.`}</p> : null}
        <EventVenueNotices eventStatus={link.event_status} coverage={link.coverage} reservationState={link.reservation_state}
          bookingId={link.current_booking_id} spaceId={link.current_space_id} conflicts={link.conflicts} />
      </div> : null}
      {link?.state === "linked" && (!link.event_window || !link.booking_window) ? <p role="alert">{t`The linked booking details are unavailable.`}</p> : null}
      {!readOnly && link?.state === "linked" && link.replaceable && link.current_booking_id ? <EventVenueReplacement
        makerspaceId={makerspaceId} eventId={eventId} expectedBookingId={link.current_booking_id}
        currentWindow={link.event_window ?? link.booking_window} request={request} queryKey={key}
        onReplaced={() => client.invalidateQueries({ queryKey: key, exact: true })} /> : null}
      {link?.state === "absent" && (link.fee_state === "configured" || link.fee_state === "historical_debt")
        ? <p>{t`Existing event venue fees need review before a booking can be linked.`}</p> : null}
      {message ? <p role="alert">{message}</p> : null}
      {partial ? <button type="button" className="desk-button w-fit" disabled={pending} onClick={() => { void linkBooking(true); }}>{t`Link anyway (partial coverage)`}</button> : null}
      {warnings.length ? <ul className="grid list-disc gap-1 pl-5 text-sm" role="status" aria-label={t`Link warnings`}>
        {warnings.map(warning => <li key={warning.code}>{venueWarningText(warning)}</li>)}</ul> : null}
      {canLink ? <>
        {uncertain ? <div className="flex flex-wrap gap-2">
          <button type="button" className="desk-button" disabled={pending} onClick={() => { void linkBooking(); }}>{t`Retry the same link`}</button>
          <button type="button" className="desk-button" disabled={pending} onClick={() => { void query.refetch(); }}>{t`Check current venue`}</button>
        </div> : <fieldset className="grid gap-2" disabled={pending}>
          <legend>{t`Link an existing booking`}</legend>
          <label>{t`Room`} <select className="desk-input" value={roomId} onChange={event => {
            setRoomId(Number(event.target.value)); setBookingId(0); setBookingPage(1); setConfirmed(false);
            setCandidate(0); setBookingOpen(false);
          }}>
            <option value={0}>{t`Select a room`}</option>
            {eligibleRooms.map(room => <option key={room.id} value={room.id}>{room.name}</option>)}
          </select></label>
          <EventPanelPager page={roomPage} count={rooms.data?.count} next={rooms.data?.next}
            setPage={next => { setRoomPage(next); setRoomId(0); setBookingId(0); setBookingPage(1); setConfirmed(false); setCandidate(0); setBookingOpen(false); }} />
          {roomSelected && link?.event_window ? <StaffBookingReadiness key={roomId} spaceId={roomId} memberId=""
            start={link.event_window.starts_at} end={link.event_window.ends_at} /> : null}
          {roomSelected ? <>
            <label>{t`Booking`} <select className="desk-input" value={bookingId} onChange={event => {
              setBookingId(Number(event.target.value)); setConfirmed(false); setCandidate(0);
            }}>
              <option value={0}>{t`Select a booking`}</option>
              {choices.map(booking => <option key={booking.id} value={booking.id}>#{booking.id} · {displayWindow(booking)} · {booking.status === "pending" ? t`Pending` : t`Confirmed`}</option>)}
            </select></label>
            <EventPanelPager page={bookingPage} count={bookings.data?.count} next={bookings.data?.next}
              setPage={next => { setBookingPage(next); setBookingId(0); setConfirmed(false); }} />
          </> : null}
          {room && !choice ? <>
            <button type="button" className="desk-button w-fit" aria-expanded={bookingOpen} onClick={() => setBookingOpen(value => !value)}>
              {bookingOpen ? t`Hide new booking` : t`Book this room for a member`}</button>
            {bookingOpen ? <StaffBookingForm makerspaceId={makerspaceId} space={room} initialWindow={link?.event_window} onSingleCreated={id => {
              setCandidate(id); setConfirmed(false); setBookingOpen(false);
              void client.invalidateQueries({ queryKey: [...key, "bookings", roomId] });
            }} /> : null}
            {candidate ? <p role="status">{t`Booking #${candidate} was created. It is not linked to this event until you confirm below.`}</p> : null}
          </> : null}
          {rooms.isError || bookings.isError ? <p role="alert">{t`Booking choices are unavailable.`}</p> : null}
          {target ? <label><input type="checkbox" checked={confirmed} onChange={event => setConfirmed(event.target.checked)} />
            {t`I confirm that the booking owns venue billing.`}</label> : null}
          <button type="button" className="desk-button w-fit" disabled={!target || !confirmed}
            onClick={() => { void linkBooking(); }}>{t`Link booking`}</button>
        </fieldset>}
      </> : null}
      <EventWorkshopMachines makerspaceId={makerspaceId} eventId={eventId} readOnly={readOnly} request={request} queryKey={key} />
    </> : null}
  </section>;
}
