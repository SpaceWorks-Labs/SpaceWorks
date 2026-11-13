import { t } from "@lingui/core/macro";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useContext, useState } from "react";

import { ConfirmDialog, PagePager } from "../../components/ui";
import { StructuredApiError } from "../../lib/api";
import { formatLocale } from "../../lib/format";
import { bookingAccess } from "./bookingStaffPermissions";
import type { BookableSpace, Booking, Paginated } from "./bookingsApi";
import { VenueConflictList, type VenueConflict } from "./EventVenueConflicts";
import { EventVenueReplacement } from "./EventVenueReplacement";
import { StaffBookingForm } from "./StaffBookingForm";
import { StaffListContext } from "./StaffListContext";
import { machineAccessText } from "./eventEquipment/machineLinkErrors";
import { LogoLoader } from "../../components/LogoLoader";

type Window = { starts_at: string; ends_at: string };
type Request = <Result>(url: string, init: RequestInit) => Promise<Result>;
type Row = {
  link_id: number; state: "linked" | "booking_unavailable"; booking_id: number | null;
  current_booking_id?: number; current_status?: string; space_name?: string; machine_name?: string;
  booking_window?: Window; reservation_state?: "pending" | "confirmed" | "historical" | "unavailable";
  replaceable?: boolean; history?: { booking_id: number; status: string }[];
  warnings?: { code: string; state: "blocked" | "warning"; detail: string }[];
  conflicts?: VenueConflict[];
};
type Listing = { event_window: Window; event_status: string; results: Row[]; withheld: number; max_links: number };
type Props = { makerspaceId: number; eventId: number; readOnly: boolean; request: Request; queryKey: readonly unknown[] };

function span(window: Window) {
  const format = (value: string) => new Date(value).toLocaleString(formatLocale());
  return `${format(window.starts_at)} – ${format(window.ends_at)}`;
}

/** Readiness warnings a server-reported conflict already explains are not repeated. */
const COVERED: Record<string, VenueConflict["code"][]> = {
  room_outage: ["room_out_of_service", "room_outage_warning"], machine_repair: ["machine_under_repair"],
};

function statusText(state: Row["reservation_state"]) {
  if (state === "pending") return t`Awaiting approval`;
  if (state === "confirmed") return t`Confirmed`;
  if (state === "historical") return t`Kept for history`;
  return t`Unavailable`;
}

/**
 * P2-1: machine-time bookings a workshop uses, beside the event's one room link. Each machine
 * booking keeps its own machine-time charge; linking never adds a venue or room charge. The
 * server checks event, booking and machine (per-type) authority independently.
 */
export function EventWorkshopMachines(props: Props) {
  const { makerspace } = useContext(StaffListContext);
  if (makerspace?.id !== props.makerspaceId || !makerspace.enabled_modules?.includes("machines")) return null;
  return <WorkshopMachines {...props} />;
}

function WorkshopMachines({ makerspaceId, eventId, readOnly, request, queryKey }: Props) {
  const client = useQueryClient();
  const key = [...queryKey, "workshop-machines"] as const;
  const path = `/admin/makerspace/${makerspaceId}/events/${eventId}/workshop-machines`;
  const listing = useQuery({ queryKey: key, retry: false, gcTime: 0, queryFn: ({ signal }) => request<Listing>(path, { signal }) });
  const refresh = () => client.invalidateQueries({ queryKey: key, exact: true });
  const data = listing.isError ? undefined : listing.data;
  const canLink = !readOnly && data !== undefined && ["draft", "published"].includes(data.event_status)
    && data.results.length + data.withheld < data.max_links;
  return <section className="grid gap-2" aria-label={t`Workshop machines`}>
    <h4 className="title-section">{t`Workshop machines`}</h4>
    {listing.isPending ? <LogoLoader label={t`Checking workshop machines…`} size={48} className="min-h-16 py-3" /> : null}
    {listing.isError ? <p role="alert">{t`Workshop machines are unavailable for your access.`}</p> : null}
    {data ? <>
      {data.results.length ? <ul className="grid gap-2" aria-label={t`Linked machine bookings`}>
        {data.results.map(row => <li key={row.link_id} className="rounded-md border border-line p-2">
          <MachineRow row={row} readOnly={readOnly} makerspaceId={makerspaceId} eventId={eventId}
            eventWindow={data.event_window} request={request} queryKey={key} onReplaced={refresh} />
        </li>)}
      </ul> : <p className="text-sm text-muted">{t`No machine bookings are linked to this event.`}</p>}
      {data.withheld ? <p className="text-sm text-muted">{t`Other linked machine bookings: ${data.withheld} (you cannot manage their machines).`}</p> : null}
      {canLink ? <LinkMachine makerspaceId={makerspaceId} path={path} eventWindow={data.event_window} request={request}
        queryKey={key} linked={data.results.map(row => row.current_booking_id ?? 0)} onLinked={refresh} /> : null}
    </> : null}
  </section>;
}

function MachineRow({ row, readOnly, makerspaceId, eventId, eventWindow, request, queryKey, onReplaced }: {
  row: Row; readOnly: boolean; makerspaceId: number; eventId: number; eventWindow: Window;
  request: Request; queryKey: readonly unknown[]; onReplaced: () => Promise<void>;
}) {
  const [replacing, setReplacing] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [unlinking, setUnlinking] = useState(false);
  const [problem, setProblem] = useState("");
  // Ends the link only: the booking, its machine-time charge and receipts are kept (221b).
  async function unlink() {
    setUnlinking(true); setProblem("");
    try {
      await request(`/admin/makerspace/${makerspaceId}/events/${eventId}/workshop-machines/${row.link_id}`, { method: "DELETE" });
      setConfirming(false);
      await onReplaced();
    } catch {
      setProblem(t`The machine booking could not be unlinked. Check your access, then try again.`);
      setConfirming(false);
    } finally {
      setUnlinking(false);
    }
  }
  const unlinkControls = readOnly ? null : <>
    <button type="button" className="desk-button-danger-outline w-fit" disabled={unlinking} onClick={() => setConfirming(true)}
      aria-label={t`Unlink machine booking #${row.current_booking_id ?? row.booking_id ?? ""}`}>{t`Unlink`}</button>
    {problem ? <p className="text-sm text-danger" role="alert">{problem}</p> : null}
    <ConfirmDialog open={confirming} title={t`Unlink this machine booking?`} tone="danger" confirmLabel={t`Unlink`} pending={unlinking}
      message={t`The booking stays as it is, with its machine-time charge and receipts. It is only no longer part of this event, and you can link it again later.`}
      onCancel={() => setConfirming(false)} onConfirm={() => { void unlink(); }} />
  </>;
  if (row.state === "booking_unavailable") return <div className="grid gap-1 text-sm"><p>{t`The linked machine booking is unavailable.`}</p>{unlinkControls}</div>;
  return <div className="grid gap-1 text-sm">
    <p><strong>{row.machine_name || row.space_name}</strong> · {t`Booking #${row.current_booking_id ?? ""}`} · {statusText(row.reservation_state)}</p>
    {row.booking_window ? <p>{span(row.booking_window)}</p> : null}
    {row.history?.length ? <p>{t`Earlier bookings kept on record: ${row.history.map(old => `#${old.booking_id} (${old.status})`).join(", ")}`}</p> : null}
    <VenueConflictList conflicts={row.conflicts} machine />
    {row.warnings?.filter(warning => !(COVERED[warning.code] ?? []).some(code => row.conflicts?.some(item => item.code === code)))
      .map(warning => <p key={warning.code} role={warning.state === "blocked" ? "alert" : "status"}>{warning.detail}</p>)}
    {!readOnly && row.replaceable && row.current_booking_id ? <>
      <button type="button" className="desk-button w-fit" aria-expanded={replacing} onClick={() => setReplacing(value => !value)}>
        {replacing ? t`Hide replacement` : t`Replace this machine booking`}</button>
      {replacing ? <EventVenueReplacement makerspaceId={makerspaceId} eventId={eventId} expectedBookingId={row.current_booking_id}
        currentWindow={row.booking_window ?? eventWindow} request={request} queryKey={[...queryKey, row.link_id]}
        workshopLinkId={row.link_id} onReplaced={onReplaced} /> : null}
    </> : null}
    {unlinkControls}
  </div>;
}

function LinkMachine({ makerspaceId, path, eventWindow, request, queryKey, linked, onLinked }: {
  makerspaceId: number; path: string; eventWindow: Window; request: Request; queryKey: readonly unknown[];
  linked: number[]; onLinked: () => Promise<void>;
}) {
  const [spacePage, setSpacePage] = useState(1);
  const [spaceId, setSpaceId] = useState(0);
  const [bookingId, setBookingId] = useState(0);
  const [candidate, setCandidate] = useState(0);
  const [creating, setCreating] = useState(false);
  const [pending, setPending] = useState(false);
  const [message, setMessage] = useState("");
  const spaces = useQuery({ queryKey: [...queryKey, "spaces", spacePage], retry: false, gcTime: 0,
    queryFn: ({ signal }) => request<Paginated<BookableSpace>>(`/admin/makerspaces/${makerspaceId}/spaces/?page=${spacePage}`, { signal }) });
  const machines = spaces.isError ? [] : (spaces.data?.results ?? []).filter(space => space.makerspace_id === makerspaceId &&
    space.is_active && space.machine != null && bookingAccess(space).reservations);
  const space = machines.find(row => row.id === spaceId);
  const bookings = useQuery({ queryKey: [...queryKey, "bookings", spaceId], enabled: Boolean(space), retry: false, gcTime: 0,
    queryFn: ({ signal }) => request<Paginated<Booking>>(`/admin/spaces/${spaceId}/bookings/?page=1&ordering=starts_at`, { signal }) });
  const choices = bookings.isError ? [] : (bookings.data?.results ?? []).filter(booking => booking.space_id === spaceId &&
    ["pending", "confirmed"].includes(booking.status) && !linked.includes(booking.id));
  const target = choices.some(booking => booking.id === bookingId) ? bookingId : (candidate && space ? candidate : 0);
  const reset = () => { setBookingId(0); setCandidate(0); setCreating(false); setMessage(""); };

  async function link() {
    if (!target || pending) return;
    setPending(true); setMessage("");
    try {
      await request(path, { method: "POST", body: JSON.stringify({ booking_id: target }) });
      setSpaceId(0); reset();
      await onLinked();
    } catch (error) {
      const code = error instanceof StructuredApiError ? error.code : undefined;
      setMessage(machineAccessText(error) !== null
        ? machineAccessText(error) ?? ""
        : code === "machine_under_repair" ? t`This machine is out of service for repair at that time.`
          : t`The machine booking could not be linked. Check the booking and your access, then try again.`);
    } finally {
      setPending(false);
    }
  }

  return <fieldset className="grid gap-2" disabled={pending}>
    <legend>{t`Link a machine booking`}</legend>
    <p className="text-sm text-muted">{t`The machine booking keeps its own machine-time charge. Linking adds no venue or room charge.`}</p>
    <label className="grid gap-1 text-sm">{t`Machine`}<select className="desk-input" value={spaceId}
      onChange={event => { setSpaceId(Number(event.target.value)); reset(); }}>
      <option value={0}>{spaces.isPending ? t`Loading machines…` : t`Select a machine`}</option>
      {machines.map(row => <option key={row.id} value={row.id}>{row.name}</option>)}
    </select></label>
    <PagePager page={spacePage} setPage={next => { setSpacePage(next); setSpaceId(0); reset(); }} next={spaces.data?.next} />
    {spaces.isSuccess && !machines.length ? <p className="text-sm text-muted">{t`No active machine here takes staff reservations.`}</p> : null}
    {space ? <>
      <label className="grid gap-1 text-sm">{t`Booking`}<select className="desk-input" value={bookingId}
        onChange={event => { setBookingId(Number(event.target.value)); setCandidate(0); }}>
        <option value={0}>{t`Select a booking`}</option>
        {choices.map(booking => <option key={booking.id} value={booking.id}>#{booking.id} · {span(booking)} · {booking.status === "pending" ? t`Pending` : t`Confirmed`}</option>)}
      </select></label>
      <button type="button" className="desk-button w-fit" aria-expanded={creating} onClick={() => setCreating(value => !value)}>
        {creating ? t`Hide new booking` : t`Book this machine for a member`}</button>
      {creating ? <StaffBookingForm makerspaceId={makerspaceId} space={space} initialWindow={eventWindow} onSingleCreated={id => {
        setCandidate(id); setBookingId(0); setCreating(false);
      }} /> : null}
      {candidate ? <p role="status">{t`Booking #${candidate} was created. It is not linked to this event until you link it below.`}</p> : null}
    </> : null}
    {spaces.isError || bookings.isError ? <p role="alert">{t`Booking choices are unavailable.`}</p> : null}
    {message ? <p role="alert">{message}</p> : null}
    <button type="button" className="desk-button w-fit" disabled={!target} onClick={() => { void link(); }}>{t`Link machine booking`}</button>
  </fieldset>;
}
