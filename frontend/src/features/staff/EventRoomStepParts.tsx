import { LogoLoader } from "../../components/LogoLoader";
import { t } from "@lingui/core/macro";
import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";

import { staffRequest } from "../../lib/api";
import { formatLocale } from "../../lib/format";
import type { BookableSpace, Booking, Paginated } from "./bookingsApi";
import type { RoomChoice } from "./EventRoomStep";
import { previewStaffBookingPrice, useBookingEligibleMembers, type StaffBookingQuote } from "./staffBookingApi";
import { StaffPriceConfirmation } from "./StaffPriceConfirmation";
import { PagePager } from "../../components/ui";
import { BoxArt } from "../../components/BoxSpinner";

function span(row: { starts_at: string; ends_at: string }) {
  const format = (value: string) => new Date(value).toLocaleString(formatLocale(), { dateStyle: "medium", timeStyle: "short" });
  return `${format(row.starts_at)} – ${format(row.ends_at)}`;
}

/** "Book for a member": pick the booker, then confirm the room price the server will charge (decision 216). */
export function EventRoomMemberPrice({ space, startsAt, endsAt, value, onChange }: {
  space: BookableSpace; startsAt: string; endsAt: string; value: RoomChoice; onChange: (patch: Partial<RoomChoice>) => void;
}) {
  const [page, setPage] = useState(1);
  const members = useBookingEligibleMembers(space.id, page);
  const [quote, setQuote] = useState<StaffBookingQuote | null>(null);
  const [error, setError] = useState("");
  const [checking, setChecking] = useState(false);
  const ticket = useRef(0);
  // The confirmation is bound to room, member and window: a changed input needs a fresh review.
  const key = `${space.id}:${value.member_id}:${startsAt}:${endsAt}`;
  const bound = useRef(key);
  useEffect(() => {
    if (bound.current === key) return;
    bound.current = key; ticket.current += 1; setQuote(null); setChecking(false);
    if (value.price_confirmation) onChange({ price_confirmation: "" });
  }, [key]); // eslint-disable-line react-hooks/exhaustive-deps
  const review = async () => {
    const mine = ++ticket.current;
    setChecking(true); setError("");
    try {
      const result = await previewStaffBookingPrice(space.id, { member_id: value.member_id, starts_at: startsAt, ends_at: endsAt });
      if (mine !== ticket.current) return;
      setQuote(result); onChange({ price_confirmation: result.price_confirmation });
    } catch (caught) {
      if (mine === ticket.current) setError(caught instanceof Error ? caught.message : t`The room price is unavailable.`);
    } finally {
      if (mine === ticket.current) setChecking(false);
    }
  };
  return <div className="grid gap-2">
    <label className="grid gap-1">{t`Member who books the room`}
      <select className="desk-input" value={value.member_id} onChange={change => onChange({ member_id: Number(change.target.value), price_confirmation: "" })}>
        <option value={0}>{members.isPending ? t`Loading members…` : t`Select a member`}</option>
        {members.data?.results.map(member => <option key={member.member_id} value={member.member_id}>{member.display_name}</option>)}
      </select></label>
    <PagePager page={page} setPage={setPage} next={members.data?.next} />
    {value.member_id && !value.price_confirmation ? <button type="button" className="desk-button w-fit" disabled={checking} onClick={() => { void review(); }}>
      {checking ? <><BoxArt size={16} mono />{t`Checking price…`}</> : t`Review room price`}</button> : null}
    {quote && value.price_confirmation ? <StaffPriceConfirmation confirmation={quote} approval={space.approval_mode === "approve"} /> : null}
    {members.error || error ? <p role="alert" className="text-danger">{error || members.error?.message}</p> : null}
  </div>;
}

/** "Link an existing booking": only live bookings of the room that cover the whole event window. */
export function EventRoomBookingChoices({ spaceId, startsAt, endsAt, value, onChange }: {
  spaceId: number; startsAt: string; endsAt: string; value: number; onChange: (bookingId: number) => void;
}) {
  // The list filter keeps bookings STARTING after `starts_at`, so look back a week for one that covers the event.
  const since = new Date(new Date(startsAt).getTime() - 7 * 86400000).toISOString();
  const query = new URLSearchParams({ page: "1", ordering: "starts_at", starts_at: since });
  const bookings = useQuery({ queryKey: ["booking-space", spaceId, "bookings", "event-room-step", startsAt, endsAt], retry: false,
    queryFn: () => staffRequest<Paginated<Booking>>(`/admin/spaces/${spaceId}/bookings/?${query}`) });
  const covering = (bookings.data?.results ?? []).filter(row => ["pending", "confirmed"].includes(row.status)
    && row.starts_at <= startsAt && row.ends_at >= endsAt && !row.linked_event);
  if (bookings.isPending) return <LogoLoader label={t`Loading bookings…`} />;
  if (bookings.isError) return <p role="alert">{t`Bookings for this room are unavailable.`}</p>;
  if (!covering.length) return <p>{t`No free booking of this room covers the whole event. Choose another option.`}</p>;
  return <label className="grid gap-1">{t`Booking`}
    <select className="desk-input" value={value} onChange={change => onChange(Number(change.target.value))}>
      <option value={0}>{t`Select a booking`}</option>
      {covering.map(row => <option key={row.id} value={row.id}>#{row.id} · {row.name} · {span(row)} · {row.status === "pending" ? t`Pending` : t`Confirmed`}</option>)}
    </select></label>;
}
