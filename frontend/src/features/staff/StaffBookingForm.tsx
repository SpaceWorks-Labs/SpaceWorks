import { formatLocale } from "../../lib/format";
import { t } from "@lingui/core/macro";
import { useRef, useState, type FormEvent } from "react";

import { StructuredApiError } from "../../lib/api";
import { CustomFormFields } from "../forms/CustomFormFields";
import { customAnswerErrors, validateCustomAnswers, type CustomAnswers } from "../forms/customFormTypes";
import type { BookableSpace } from "./bookingsApi";
import { previewStaffBookingPrice, useBookingEligibleMembers, useStaffCreateBooking, type StaffBookingQuote } from "./staffBookingApi";
import { changedConfirmation, StaffPriceConfirmation } from "./StaffPriceConfirmation";
import { StaffBookingReadiness } from "./BookingReadiness";
import { StaffBookingAvailability, toLocalInput } from "./StaffBookingAvailability";
import { PagePager } from "../../components/ui";

export function StaffBookingForm({ makerspaceId, space, recurringEnabled = false, onSingleCreated, initialWindow }: {
  makerspaceId: number; space: BookableSpace; recurringEnabled?: boolean;
  onSingleCreated?: (bookingId: number) => void;
  /** Prefill (e.g. an event's start/end); staff may still change it. */
  initialWindow?: { starts_at: string; ends_at: string } | null;
}) {
  const [repeat, setRepeat] = useState(false);
  const [count, setCount] = useState(8);
  const [intervalWeeks, setIntervalWeeks] = useState(1);
  const [memberId, setMemberId] = useState("");
  // Decision 223 (h): a house booking has no member booker, is never priced and is confirmed at once.
  const [house, setHouse] = useState(false);
  const [page, setPage] = useState(1);
  const [start, setStart] = useState(() => toLocalInput(initialWindow?.starts_at));
  const [end, setEnd] = useState(() => toLocalInput(initialWindow?.ends_at));
  const [note, setNote] = useState("");
  const [reason, setReason] = useState("");
  const [answers, setAnswers] = useState<CustomAnswers>({});
  const [errors, setErrors] = useState<Record<string, string>>({});
  // Decision 216: a single booking charges only a price staff reviewed. The server
  // re-verifies the digest under the booking lock; any input change needs a fresh review.
  const [confirmation, setConfirmation] = useState<StaffBookingQuote | null>(null);
  const [previewing, setPreviewing] = useState(false);
  const [previewError, setPreviewError] = useState("");
  const ticket = useRef(0);
  const single = house || !(repeat && recurringEnabled);
  const unconfirm = () => { ticket.current += 1; setConfirmation(null); setPreviewing(false); setPreviewError(""); };
  const members = useBookingEligibleMembers(space.id, page);
  const create = useStaffCreateBooking(makerspaceId, space.id);
  const slot = () => ({ member_id: Number(memberId), starts_at: new Date(start).toISOString(), ends_at: new Date(end).toISOString() });
  const review = async () => {
    const mine = ++ticket.current;
    setPreviewing(true); setPreviewError("");
    try {
      const result = await previewStaffBookingPrice(space.id, slot());
      if (mine === ticket.current) setConfirmation(result);
    } catch (error) {
      if (mine === ticket.current) setPreviewError(error instanceof Error ? error.message : t`The room price is unavailable.`);
    } finally {
      if (mine === ticket.current) setPreviewing(false);
    }
  };
  const submit = (event: FormEvent) => {
    event.preventDefault();
    const nextErrors = validateCustomAnswers(space.custom_form ?? [], answers);
    setErrors(nextErrors);
    if (Object.keys(nextErrors).length) return;
    if (single && !house && !confirmation) { void review(); return; }
    const { member_id, ...window } = slot();
    create.mutate({
      ...(single ? {} : { count, interval_weeks: intervalWeeks }),
      ...window, note, ...(house ? { house: true } : { member_id }),
      ...(single && !house && confirmation ? { price_confirmation: confirmation.price_confirmation } : {}),
      ...(!house && reason.trim() ? { certification_override_reason: reason.trim() } : {}),
      ...(space.custom_form?.length ? { custom_answers: answers } : {}),
    }, { onError: error => setConfirmation(changedConfirmation(error)), onSuccess: result => {
      setMemberId(""); setHouse(false); setAnswers({}); setReason(""); setNote(""); setConfirmation(null);
      if ("id" in result && Number.isSafeInteger(result.id) && result.id > 0 && result.space_id === space.id) {
        onSingleCreated?.(result.id);
      }
    } });
  };
  return (
    <form className="mb-4 grid gap-3 rounded-lg border border-line p-3" onSubmit={submit}>
      <h4 className="title-section">{house ? t`House booking` : t`Book for a member`}</h4>
      <p className="text-xs text-muted">{house ? t`For the space's own use, such as an event it runs. No member, no charge and no plan hours; confirmed straight away.` : t`Active membership and current waiver are required. Members can book ahead.`}</p>
      <fieldset className="grid gap-3 sm:grid-cols-2" disabled={create.isPending}>
        <label className="flex min-h-11 items-center gap-2 text-sm sm:col-span-2"><input type="checkbox" checked={house} onChange={(event) => { setHouse(event.target.checked); setMemberId(""); setReason(""); unconfirm(); }} />{t`House booking (no member, no charge)`}</label>
        {house ? null : <><label className="grid gap-1 text-sm sm:col-span-2">{t`Member`}<select className="desk-input" required value={memberId} onChange={(event) => { setMemberId(event.target.value); setAnswers({}); setErrors({}); setReason(""); unconfirm(); }}>
            <option value="">{members.isLoading ? t`Loading members…` : t`Select a member`}</option>
            {members.data?.results.map((member) => <option key={member.member_id} value={member.member_id}>{member.display_name}</option>)}
          </select>
        </label>
        <div className="sm:col-span-2"><PagePager page={page} setPage={next => { setPage(next); setMemberId(""); unconfirm(); }} next={members.data?.next} /></div></>}
        <label className="grid gap-1 text-sm">{t`Starts (your local time)`}<input className="desk-input w-full min-w-0" type="datetime-local" required value={start} onChange={(event) => { setStart(event.target.value); unconfirm(); }} /></label>
        <label className="grid gap-1 text-sm">{t`Ends (your local time)`}<input className="desk-input w-full min-w-0" type="datetime-local" required value={end} onChange={(event) => { setEnd(event.target.value); unconfirm(); }} /></label>
        {recurringEnabled && !house ? <div className="grid gap-2 sm:col-span-2"><label className="flex min-h-11 items-center gap-2 text-sm"><input type="checkbox" checked={repeat} onChange={(event) => { setRepeat(event.target.checked); unconfirm(); }} />{t`Repeat weekly in makerspace local time`}</label>{repeat ? <><label className="grid gap-1 text-sm">{t`Occurrences`}<input className="desk-input" type="number" min={2} max={52} value={count} onChange={(event) => setCount(Number(event.target.value))} /></label><label className="grid gap-1 text-sm">{t`Weeks between bookings`}<input className="desk-input" type="number" min={1} max={12} value={intervalWeeks} onChange={(event) => setIntervalWeeks(Number(event.target.value))} /></label><p className="text-xs text-muted">{t`Each occurrence is booked and charged separately. The result lists every conflict.`}</p></> : null}</div> : null}
        <label className="grid gap-1 text-sm sm:col-span-2">{t`Staff note`}<textarea className="desk-input" maxLength={5000} value={note} onChange={(event) => setNote(event.target.value)} /></label>
        {space.machine_type && !house ? <label className="grid gap-1 text-sm sm:col-span-2">{t`Certification override reason (optional)`}<input className="desk-input" maxLength={1000} value={reason} onChange={(event) => setReason(event.target.value)} />
          <span className="text-xs text-muted">{t`Only staff with authority over this machine type may override. Every override is audited.`}</span>
        </label> : null}
      </fieldset>
      <CustomFormFields schema={space.custom_form} answers={answers} onChange={setAnswers} disabled={create.isPending} errors={{ ...errors, ...customAnswerErrors(create.error instanceof StructuredApiError ? create.error.body.custom_answers : undefined) }} />
      <StaffBookingAvailability spaceId={space.id} start={start} end={end} />
      <StaffBookingReadiness spaceId={space.id} memberId={house ? "" : memberId} start={start} end={end} />
      {single && confirmation ? <StaffPriceConfirmation confirmation={confirmation} approval={space.approval_mode === "approve"} /> : null}
      {members.error || create.error || previewError ? <p className="text-sm text-danger" role="alert">{previewError || (create.error ?? members.error)?.message}</p> : null}
      {/* The form scrolls inside its dialog; keep the submit pinned to the dialog's bottom edge. */}
      <div className="sticky bottom-0 z-10 bg-panel py-2"><button className="desk-button-primary w-full sm:w-fit" type="submit" disabled={(!memberId && !house) || create.isPending || previewing}>{create.isPending ? t`Booking…` : previewing ? t`Checking price…` : house ? t`Create house booking` : single && !confirmation ? t`Review price` : single ? t`Confirm price and create booking` : t`Create booking`}</button></div>
      {create.data && "occurrences" in create.data ? <ul className="grid gap-2 text-sm" aria-label={t`Recurring booking results`}>{create.data.occurrences.map((row) => <li key={row.occurrence}>{row.occurrence}: {new Date(row.starts_at).toLocaleString(formatLocale())} — {row.booking_id ? row.status : t`Conflict: ${row.detail}`}</li>)}</ul> : create.isSuccess ? <p className="text-sm text-success-ink" role="status">{t`Booking created.`}</p> : null}
    </form>
  );
}
