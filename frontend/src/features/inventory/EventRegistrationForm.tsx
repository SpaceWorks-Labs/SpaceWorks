import { useEffect, useRef, useState, type FormEvent } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import type { ApiPath } from "../../generated/api";
import { EventContactFallback } from "../events/EventContactFallback";
import { EventTicketPicker } from "../events/EventTicketPicker";
import type { EventTicket } from "../events/eventTicketTypes";
import { StructuredApiError, tenantPublicRequest } from "../../lib/api";
import { CustomFormFields } from "../forms/CustomFormFields";
import {
  customAnswerErrors,
  validateCustomAnswers,
  type CustomAnswers,
  type CustomFormSchema,
} from "../forms/customFormTypes";

type RegistrationResult = { status: "pending_approval" | "registered" | "waitlisted" };

const REGISTER_PATH: ApiPath = "/api/v1/public/{makerspace_slug}/events/{public_token}/register/";

function registerPath(slug: string, token: string) {
  return REGISTER_PATH.replace("/api/v1", "")
    .replace("{makerspace_slug}", encodeURIComponent(slug))
    .replace("{public_token}", encodeURIComponent(token));
}

function failureMessage(error: StructuredApiError | null) {
  if (!error) return "The registration could not be submitted.";
  if (error.status === 401) return "Sign in to register for this event.";
  if (error.status === 403 && error.code === "membership_required") return "Join this makerspace before registering.";
  if (error.status === 403 && error.code === "waiver_acceptance_required") return "Accept the current waiver before registering.";
  if (error.status === 403 && error.code === "presence_required") return "Start a presence session before registering.";
  if (error.status === 429) return "Too many registration attempts. Please wait and try again.";
  if (error.status === 409 && error.code === "registration_closed") return "Registration for this event is closed.";
  if (error.status === 409 && error.code === "registration_rejected") return "Your application was not approved and cannot be resubmitted.";
  return error.detail ?? error.message;
}

export function EventRegistrationForm({ makerspaceSlug, publicToken, waitlist, approvalRequired, customForm, audience = "members", tickets = [], promoEnabled = false, ticketRequired = false, currency = "", hostWaiver = null }: {
  makerspaceSlug: string; publicToken: string; waitlist: boolean; approvalRequired: boolean;
  customForm: CustomFormSchema; audience?: "members" | "accounts" | "invite" | "participating_organizations";
  hostWaiver?: { id: number; version: string; body: string } | null;
  tickets?: EventTicket[]; promoEnabled?: boolean; ticketRequired?: boolean; currency?: string;
}) {
  const queryClient = useQueryClient();
  const [waiverAccepted, setWaiverAccepted] = useState(false);
  useEffect(() => { setWaiverAccepted(false); }, [hostWaiver?.id, hostWaiver?.version]);
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");
  const [needsPhone, setNeedsPhone] = useState(false);
  const [needsEmail, setNeedsEmail] = useState(false);
  const [inviteCode, setInviteCode] = useState("");
  const [promoCode, setPromoCode] = useState("");
  const [ticketId, setTicketId] = useState<number | null>(null);
  const [website, setWebsite] = useState("");
  const [answers, setAnswers] = useState<CustomAnswers>({});
  const [clientErrors, setClientErrors] = useState<Record<string, string>>({});
  const successRef = useRef<HTMLDivElement>(null);
  const registration = useMutation({
    mutationFn: async () => {
      const rawTransportBody = { ...(hostWaiver ? { host_waiver_id: hostWaiver.id, host_waiver_version: hostWaiver.version, host_waiver_accepted: waiverAccepted } : {}), ...(phone.trim() ? { phone: phone.trim() } : {}), ...(email.trim() ? { email: email.trim() } : {}), website, custom_answers: answers, ...(inviteCode ? { invite_code: inviteCode } : {}), ...(promoCode ? { promo_code: promoCode } : {}), ...(ticketId !== null ? { ticket_type_id: ticketId } : {}) };
      return tenantPublicRequest<RegistrationResult>(makerspaceSlug, registerPath(makerspaceSlug, publicToken), {
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
    return <div ref={successRef} className="rounded-lg border border-line bg-surface p-4 outline-none" role="status" tabIndex={-1}>
      <h3 className="title-section">{registration.data.status === "pending_approval" ? "Application awaiting approval" : registration.data.status === "waitlisted" ? "You’re on the waitlist" : "Registration received"}</h3>
      <p className="mt-1 text-sm text-muted">{registration.data.status === "pending_approval" ? "You will only be charged if a place is confirmed." : registration.data.status === "waitlisted" ? "The makerspace has recorded your waitlist request." : "The makerspace has recorded your registration."}</p>
    </div>;
  }

  if (ticketRequired && !tickets.length) return <p role="status">No tickets are available for this account. Sign in or contact the organizers.</p>;

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
    <h3 className="title-section">{approvalRequired ? "Apply" : waitlist ? "Join the waitlist" : "Register"}</h3>
    <label className="absolute left-[-10000px] top-auto h-px w-px overflow-hidden" aria-hidden="true">Website
      <input name="website" tabIndex={-1} autoComplete="off" value={website} onChange={(e) => setWebsite(e.target.value)} />
    </label>
    <EventContactFallback needsPhone={needsPhone} needsEmail={needsEmail} phone={phone} email={email} onPhone={setPhone} onEmail={setEmail} disabled={registration.isPending} />
    <EventTicketPicker tickets={tickets} value={ticketId} onChange={setTicketId} currency={currency} disabled={registration.isPending} />
    {audience === "invite" ? <><label className="grid gap-1 text-sm">Invitation code<input className="desk-input" maxLength={128} autoComplete="off" value={inviteCode} onChange={(e) => setInviteCode(e.target.value)} /></label><p className="text-sm text-muted">Leave blank if your verified account email was invited.</p></> : null}
    {hostWaiver ? <fieldset className="rounded-lg border border-line p-3"><legend>Host waiver</legend><p className="whitespace-pre-wrap text-sm">{hostWaiver.body}</p><label className="mt-2 flex gap-2"><input type="checkbox" checked={waiverAccepted} onChange={(e) => setWaiverAccepted(e.target.checked)} />I accept this host waiver (version {hostWaiver.version}).</label>{clientErrors.waiver ? <p role="alert">{clientErrors.waiver}</p> : null}</fieldset> : null}
    {promoEnabled ? <label className="grid gap-1 text-sm">Promo code (optional)<input className="desk-input" maxLength={128} autoComplete="off" value={promoCode} onChange={(e) => setPromoCode(e.target.value)} /></label> : null}
    {clientErrors.ticket || clientErrors.invite ? <p role="alert">{clientErrors.ticket || clientErrors.invite}</p> : null}
    <CustomFormFields schema={customForm} answers={answers} onChange={setAnswers} errors={{ ...serverErrors, ...clientErrors }} />
    {registration.error ? <p className="text-sm text-danger" role="alert">{failureMessage(apiError)}</p> : null}
    <button className="desk-button-secondary" type="submit" disabled={registration.isPending}>
      {registration.isPending ? "Submitting..." : approvalRequired ? "Apply" : waitlist ? "Join waitlist" : "Register"}
    </button>
  </form>;
}
