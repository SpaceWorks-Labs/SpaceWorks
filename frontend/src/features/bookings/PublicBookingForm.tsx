import { t } from "@lingui/core/macro";
import { useEffect, useRef, useState, type FormEvent } from "react";

import { Field } from "../../components/ui";
import { StructuredApiError } from "../../lib/api";
import { eligibilityMessage } from "../../lib/eligibilityCopy";
import { CustomFormFields } from "../forms/CustomFormFields";
import {
  customAnswerErrors,
  validateCustomAnswers,
  type CustomAnswers,
} from "../forms/customFormTypes";
import { BookingConfirmation } from "./BookingConfirmation";
import { AvailabilityCalendar } from "./AvailabilityCalendar";
import { useSubmitPublicBooking, type PublicBookableSpace } from "./publicBookingsApi";
import { PayNextStep } from "../payments/PayNextStep";
import { PricePreview } from "../payments/PricePreview";
import { tenantPath, useOptionalTenant } from "../../lib/tenant";
import { isPriceChanged, PriceChangedNotice } from "../payments/PriceChangedNotice";
import { isoTime } from "../payments/usePriceQuote";

type StandardErrors = Partial<Record<"starts_at" | "ends_at", string>>;

function apiFieldError(error: StructuredApiError | null, field: keyof StandardErrors) {
  const value = error?.body[field];
  if (typeof value === "string") return value;
  if (Array.isArray(value)) return value.filter((item): item is string => typeof item === "string").join(" ");
  return "";
}

function failureMessage(error: StructuredApiError | null) {
  if (!error) return t`The booking could not be submitted. Please try again.`;
  if (error.status === 409) return t`That time now overlaps a confirmed booking. Choose another slot and try again.`;
  if (error.status === 429) return t`Too many booking attempts were made. Please wait before trying again.`;
  if (error.status === 401) return t`Sign in to submit a booking.`;
  const eligibility = eligibilityMessage(error);
  if (eligibility) return eligibility;
  if (error.status === 400) return error.detail ?? t`Review the highlighted fields and try again.`;
  return error.detail ?? t`The booking service is unavailable. Please try again.`;
}

export function PublicBookingForm({ makerspaceSlug, space, showCalendar = true }: {
  makerspaceSlug: string;
  space: PublicBookableSpace;
  showCalendar?: boolean;
}) {
  const [startsAt, setStartsAt] = useState("");
  const [endsAt, setEndsAt] = useState("");
  const [answers, setAnswers] = useState<CustomAnswers>({});
  const [website, setWebsite] = useState("");
  const [quoteDigest, setQuoteDigest] = useState("");
  // Set only by a live quote, which PricePreview fetches only while booking charges are on (#184).
  const [owes, setOwes] = useState(false);
  const paymentsHref = tenantPath(useOptionalTenant()?.mode ?? "central", makerspaceSlug, "member/payments");
  const [standardErrors, setStandardErrors] = useState<StandardErrors>({});
  const [answerErrors, setAnswerErrors] = useState<Record<string, string>>({});
  const successRef = useRef<HTMLDivElement>(null);
  const booking = useSubmitPublicBooking(makerspaceSlug, space.public_token);
  const apiError = booking.error instanceof StructuredApiError ? booking.error : null;
  const serverAnswerErrors = customAnswerErrors(apiError?.body.custom_answers);

  useEffect(() => {
    if (booking.data) successRef.current?.focus();
  }, [booking.data]);

  if (booking.data) {
    const pending = booking.data.status === "pending";
    return (
      <div data-replay-block ref={successRef} className={`rounded-lg border ${pending ? "border-warn bg-warn-soft" : "border-success bg-success-soft"} p-4 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus`} role="status" tabIndex={-1}>
        <h3 className="title-section">{pending ? t`Booking request received` : t`Space booked`}</h3>
        <p className="mt-1 text-sm text-muted">
          {pending ? t`Staff must approve this request before the slot is confirmed.` : t`Your selected slot is confirmed and booked.`}
        </p>
        {/* The server's recorded amount wins over the client's live quote when it sent one. */}
        {(booking.data.amount_due === undefined ? owes : Number(booking.data.amount_due ?? 0) > 0) ? <PayNextStep paymentsHref={paymentsHref} pending={pending} /> : null}
        {booking.data.public_token && booking.data.confirmation_available ? <BookingConfirmation slug={makerspaceSlug} token={booking.data.public_token} /> : null}
      </div>
    );
  }

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (booking.isPending) return;
    const nextStandard: StandardErrors = {};
    if (!startsAt) nextStandard.starts_at = "Choose a start time.";
    if (!endsAt) nextStandard.ends_at = "Choose an end time.";
    if (startsAt && endsAt && new Date(endsAt) <= new Date(startsAt)) nextStandard.ends_at = "End time must be after start time.";
    if (endsAt && new Date(endsAt) <= new Date()) nextStandard.ends_at = "End time must be in the future.";
    const nextAnswers = validateCustomAnswers(space.custom_form, answers);
    setStandardErrors(nextStandard);
    setAnswerErrors(nextAnswers);
    if (Object.keys(nextStandard).length || Object.keys(nextAnswers).length) return;

    booking.mutate({
      starts_at: new Date(startsAt).toISOString(),
      ends_at: new Date(endsAt).toISOString(),
      custom_answers: Object.keys(answers).length ? answers : null,
      website,
      ...(quoteDigest ? { quote_digest: quoteDigest } : {}),
    });
  };
  const errorFor = (field: keyof StandardErrors) => standardErrors[field] || apiFieldError(apiError, field);

  return (
    <div data-replay-block className="grid gap-4">
      {showCalendar ? <AvailabilityCalendar makerspaceSlug={makerspaceSlug} publicToken={space.public_token} /> : null}
      <form className="@container grid min-w-0 gap-4 rounded-lg border border-brand bg-bg p-4" onSubmit={submit} noValidate>
        <div>
          <h3 className="title-section">{t`Request this space`}</h3>
          <p className="mt-1 text-sm text-muted">{t`Times are shown in your device timezone.`}</p>
        </div>
        {/* Sized by the form, not the viewport: in the narrow desktop action card two
            datetime pickers side by side would each be too cramped to read. */}
        <div className="grid gap-3 @lg:grid-cols-2">
          <Field label={t`Starts`} error={errorFor("starts_at")}><input className="desk-input w-full min-w-0" type="datetime-local" value={startsAt} onChange={(event) => setStartsAt(event.target.value)} required /></Field>
          <Field label={t`Ends`} error={errorFor("ends_at")}><input className="desk-input w-full min-w-0" type="datetime-local" value={endsAt} onChange={(event) => setEndsAt(event.target.value)} required /></Field>
        </div>
        <CustomFormFields schema={space.custom_form} answers={answers} onChange={setAnswers} errors={{ ...answerErrors, ...serverAnswerErrors }} disabled={booking.isPending} />
        <label className="absolute left-[-10000px] top-auto h-px w-px overflow-hidden" aria-hidden="true">{t`Website`}<input name="website" tabIndex={-1} autoComplete="off" value={website} onChange={(event) => setWebsite(event.target.value)} />
        </label>
        <PricePreview makerspaceSlug={makerspaceSlug} request={{ domain: "bookings", space_token: space.public_token, starts_at: isoTime(startsAt), ends_at: isoTime(endsAt) }} onDigest={setQuoteDigest} onOwes={setOwes} />
        {isPriceChanged(booking.error) ? <PriceChangedNotice makerspaceSlug={makerspaceSlug} error={booking.error} />
          : booking.error ? <p className="text-sm text-danger" role="alert">{failureMessage(apiError)}</p> : null}
        <button className="desk-button-brand" type="submit" disabled={booking.isPending}>
          {booking.isPending ? t`Submitting...` : space.approval_mode === "approve" ? t`Submit booking request` : t`Book this slot`}
        </button>
      </form>
    </div>
  );
}
