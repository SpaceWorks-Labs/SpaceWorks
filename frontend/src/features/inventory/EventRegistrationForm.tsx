import { t } from "@lingui/core/macro";
import { Icon, TicketCard } from "../../components/ui";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import type { ApiPath } from "../../generated/api";
import { EventContactFallback } from "../events/EventContactFallback";
import { EventTicketPicker } from "../events/EventTicketPicker";
import type { EventTicket } from "../events/eventTicketTypes";
import { StructuredApiError, tenantMemberRequest } from "../../lib/api";
import { useChargesOn } from "../../lib/charges";
import { eligibilityMessage } from "../../lib/eligibilityCopy";
import { CustomFormFields } from "../forms/CustomFormFields";
import { PayNextStep } from "../payments/PayNextStep";
import { PricePreview } from "../payments/PricePreview";
import { isPriceChanged, PriceChangedNotice } from "../payments/PriceChangedNotice";
import {
  customAnswerErrors,
  validateCustomAnswers,
  type CustomAnswers,
  type CustomFormSchema,
} from "../forms/customFormTypes";
import { BoxArt } from "../../components/BoxSpinner";

type RegistrationResult = { status: "pending_approval" | "registered" | "waitlisted" };

const REGISTER_PATH: ApiPath = "/api/v1/public/{makerspace_slug}/events/{public_token}/register/";

function registerPath(slug: string, token: string) {
  return REGISTER_PATH.replace("/api/v1", "")
    .replace("{makerspace_slug}", encodeURIComponent(slug))
    .replace("{public_token}", encodeURIComponent(token));
}

function failureMessage(error: StructuredApiError | null) {
  if (!error) return t`The registration could not be submitted.`;
  if (error.status === 401) return t`Sign in to register for this event.`;
  const eligibility = eligibilityMessage(error);
  if (eligibility) return eligibility;
  if (error.status === 429) return t`Too many registration attempts. Please wait and try again.`;
  if (error.status === 409 && error.code === "registration_closed") return t`Registration for this event is closed.`;
  if (error.status === 409 && error.code === "registration_rejected") return t`Your application was not approved and cannot be resubmitted.`;
  return error.detail ?? error.message;
}

export function EventRegistrationForm({ makerspaceSlug, publicToken, waitlist, approvalRequired, customForm, audience = "members", tickets = [], promoEnabled = false, ticketRequired = false, currency = "", hostWaiver = null, organisation = "", paymentsHref = "" }: {
  makerspaceSlug: string; publicToken: string; waitlist: boolean; approvalRequired: boolean;
  customForm: CustomFormSchema; audience?: "members" | "accounts" | "invite" | "participating_organizations";
  hostWaiver?: { id: number; version: string; body: string } | null;
  tickets?: EventTicket[]; promoEnabled?: boolean; ticketRequired?: boolean; currency?: string;
  /** The hosting makerspace's name, printed on the confirmation ticket. */
  organisation?: string;
  /** Member-area Payments link, set only for a paid event: the fee is paid there, online
   * when the space has a rail, otherwise at the space against a staff receipt. */
  paymentsHref?: string;
}) {
  const queryClient = useQueryClient();
  const showPrice = useChargesOn("events", makerspaceSlug); // #184: free events show no money at all
  const [waiverAccepted, setWaiverAccepted] = useState(false);
  useEffect(() => { setWaiverAccepted(false); }, [hostWaiver?.id, hostWaiver?.version]);
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");
  const [needsPhone, setNeedsPhone] = useState(false);
  const [needsEmail, setNeedsEmail] = useState(false);
  const [inviteCode, setInviteCode] = useState("");
  const [promoCode, setPromoCode] = useState("");
  const [ticketId, setTicketId] = useState<number | null>(null);
  const [quoteDigest, setQuoteDigest] = useState("");
  // What the last quote said is owed; unknown (no quote) falls back to "the event is paid".
  const [owes, setOwes] = useState<boolean | undefined>(undefined);
  const [website, setWebsite] = useState("");
  const [answers, setAnswers] = useState<CustomAnswers>({});
  const [clientErrors, setClientErrors] = useState<Record<string, string>>({});
  const successRef = useRef<HTMLDivElement>(null);
  const registration = useMutation({
    mutationFn: async () => {
      const rawTransportBody = { ...(hostWaiver ? { host_waiver_id: hostWaiver.id, host_waiver_version: hostWaiver.version, host_waiver_accepted: waiverAccepted } : {}), ...(phone.trim() ? { phone: phone.trim() } : {}), ...(email.trim() ? { email: email.trim() } : {}), website, custom_answers: answers, ...(inviteCode ? { invite_code: inviteCode } : {}), ...(promoCode ? { promo_code: promoCode } : {}), ...(ticketId !== null ? { ticket_type_id: ticketId } : {}), ...(quoteDigest ? { quote_digest: quoteDigest } : {}) };
      return tenantMemberRequest<RegistrationResult>(makerspaceSlug, registerPath(makerspaceSlug, publicToken), {
        method: "POST", body: JSON.stringify(rawTransportBody),
      });
    },
    onError: async (error) => {
      if (!(error instanceof StructuredApiError)) return;
      if (error.body.phone) setNeedsPhone(true);
      if (error.body.email) setNeedsEmail(true);
      if (error.code === "host_waiver_required") {
        setWaiverAccepted(false);
        await queryClient.invalidateQueries({ queryKey: ["event-organization-eligibility", makerspaceSlug, publicToken] });
      }
    },
    onSuccess: async () => { await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["event-organization-eligibility", makerspaceSlug, publicToken] }),
      queryClient.invalidateQueries({ queryKey: ["public-events", makerspaceSlug] }),
      queryClient.invalidateQueries({ queryKey: ["public-event", makerspaceSlug, publicToken] }),
      queryClient.invalidateQueries({ queryKey: ["member", makerspaceSlug, "activity"] }),
    ]); },
  });
  useEffect(() => { if (registration.data) successRef.current?.focus(); }, [registration.data]);

  if (registration.data) {
    const pending = registration.data.status === "pending_approval";
    const waitlisted = registration.data.status === "waitlisted";
    return <div ref={successRef} role="status" tabIndex={-1} className="focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus">
      <TicketCard organisation={organisation} title={pending ? t`Application awaiting approval` : waitlisted ? t`You’re on the waitlist` : t`Registration received`}
        fields={[{ label: t`Status`, value: pending ? t`Pending review` : waitlisted ? t`Waitlisted` : t`Registered` }, { label: t`Next step`, value: pending ? t`Wait for confirmation` : waitlisted ? t`Wait for a place` : t`See you there` }]}
        qr={<div className="grid h-full place-items-center rounded-xl bg-success-soft text-success-ink"><Icon name="CheckCircle" className="h-16 w-16" /></div>}
        caption={pending ? t`You will only be charged if a place is confirmed.` : waitlisted ? t`The makerspace has recorded your waitlist request.` : t`The makerspace has recorded your registration.`} />
      {paymentsHref && showPrice && owes !== false && registration.data.status === "registered" ? <PayNextStep paymentsHref={paymentsHref} /> : null}
    </div>;
  }

  if (ticketRequired && !tickets.length) return <p role="status">{t`No tickets are available for this account. Sign in or contact the organizers.`}</p>;

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const errors = validateCustomAnswers(customForm, answers);
    setClientErrors(errors);
    if (hostWaiver && !waiverAccepted) { setClientErrors({ waiver: "Accept the current host waiver." }); return; }
    if (tickets.length && ticketId === null) { setClientErrors({ ticket: "Choose a ticket type." }); return; }
    if (Object.keys(errors).length) return;
    if (!registration.isPending) registration.mutate();
  };
  const apiError = registration.error instanceof StructuredApiError ? registration.error : null;
  const serverErrors = customAnswerErrors(apiError?.body.custom_answers);

  return <form className="grid gap-3 rounded-lg border border-line bg-bg p-4" onSubmit={submit} noValidate>
    <h3 className="title-section">{approvalRequired ? t`Apply` : waitlist ? t`Join the waitlist` : t`Register`}</h3>
    <label className="absolute left-[-10000px] top-auto h-px w-px overflow-hidden" aria-hidden="true">{t`Website`}<input name="website" tabIndex={-1} autoComplete="off" value={website} onChange={(e) => setWebsite(e.target.value)} />
    </label>
    <EventContactFallback needsPhone={needsPhone} needsEmail={needsEmail} phone={phone} email={email} onPhone={setPhone} onEmail={setEmail} disabled={registration.isPending} />
    <EventTicketPicker tickets={tickets} value={ticketId} onChange={setTicketId} currency={currency} disabled={registration.isPending} showPrice={showPrice} />
    {audience === "invite" ? <><label className="grid gap-1 text-sm">{t`Invitation code`}<input className="desk-input" maxLength={128} autoComplete="off" value={inviteCode} onChange={(e) => setInviteCode(e.target.value)} /></label><p className="text-sm text-muted">{t`Leave blank if your verified account email was invited.`}</p></> : null}
    {hostWaiver ? <fieldset className="grid gap-2 rounded-xl border border-line bg-panel p-3"><legend className="px-1 text-sm font-semibold">{t`Host waiver`}</legend><p className="whitespace-pre-wrap text-sm leading-6">{hostWaiver.body}</p><label className="flex min-h-11 items-center gap-2 text-sm"><input type="checkbox" checked={waiverAccepted} onChange={(e) => setWaiverAccepted(e.target.checked)} />{t`I accept this host waiver (version ${hostWaiver.version}).`}</label>{clientErrors.waiver ? <p className="text-sm text-danger" role="alert">{clientErrors.waiver}</p> : null}</fieldset> : null}
    {promoEnabled ? <label className="grid gap-1 text-sm">{t`Promo code (optional)`}<input className="desk-input" maxLength={128} autoComplete="off" value={promoCode} onChange={(e) => setPromoCode(e.target.value)} /></label> : null}
    {clientErrors.ticket || clientErrors.invite ? <p className="text-sm text-danger" role="alert">{clientErrors.ticket || clientErrors.invite}</p> : null}
    <CustomFormFields schema={customForm} answers={answers} onChange={setAnswers} errors={{ ...serverErrors, ...clientErrors }} />
    {!tickets.length || ticketId !== null ? <PricePreview makerspaceSlug={makerspaceSlug} request={{ domain: "events", event_token: publicToken, ticket_type_id: ticketId ?? undefined }} onDigest={setQuoteDigest} onOwes={setOwes} /> : null}
    {isPriceChanged(registration.error) ? <PriceChangedNotice makerspaceSlug={makerspaceSlug} error={registration.error} />
      : registration.error ? <p className="text-sm text-danger" role="alert">{failureMessage(apiError)}</p> : null}
    <button className="desk-button-brand" type="submit" disabled={registration.isPending}>
      {registration.isPending ? <><BoxArt size={16} mono />{t`Submitting...`}</> : approvalRequired ? t`Apply` : waitlist ? t`Join waitlist` : t`Register`}
    </button>
  </form>;
}
