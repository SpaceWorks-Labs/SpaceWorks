import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { getAccessToken, memberRequest, refreshAccessToken, StructuredApiError, tenantMemberRequest } from "../../lib/api";
import { MemberAuthPanel } from "../members/MemberAuthPanel";
import { EventRegistrationForm } from "../inventory/EventRegistrationForm";
import { EventConsentRepairForm } from "./EventConsentRepairForm";
import type { PublicEventDetail } from "./eventTicketTypes";

import type { EventEligibility } from "../../generated/api";
export type { EventEligibility } from "../../generated/api";

export const organizationEligibilityKey = (slug: string, token: string, accountId?: number) =>
  ["event-organization-eligibility", slug, token, accountId] as const;

export function OrganizationEventAdmission({ event, makerspaceSlug }: {
  event: PublicEventDetail; makerspaceSlug: string;
}) {
  const [checking, setChecking] = useState(false);
  // Event lists mount one admission per card. Only an explicit interaction starts requests.
  return checking ? <OrganizationAdmissionCheck event={event} makerspaceSlug={makerspaceSlug} /> :
    <div>{!event.registration_open ? <p>Registration is closed.</p> : null}
      <button className="desk-button mt-3" type="button" onClick={() => setChecking(true)}>
        {event.registration_open ? "Check registration eligibility" : "Review registration consent"}
      </button></div>;
}

function OrganizationAdmissionCheck({ event, makerspaceSlug }: {
  event: PublicEventDetail; makerspaceSlug: string;
}) {
  const queryClient = useQueryClient();
  const [restoring, setRestoring] = useState(!getAccessToken());
  const [open, setOpen] = useState(false);
  const [repaired, setRepaired] = useState(false);
  useEffect(() => {
    if (!restoring) return;
    void refreshAccessToken().then(async restored => {
      if (restored) await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["public-event", makerspaceSlug] }),
        queryClient.invalidateQueries({ queryKey: ["public-events", makerspaceSlug] }),
      ]);
    }).finally(() => setRestoring(false));
  }, [queryClient, makerspaceSlug, restoring]);
  const account = useQuery({
    queryKey: ["member", "event-audience-account"],
    queryFn: () => memberRequest<{ id: number }>("/auth/me"),
    enabled: !restoring, retry: false, staleTime: 0, gcTime: 0, refetchOnMount: "always",
  });
  const eligibility = useQuery({
    queryKey: organizationEligibilityKey(makerspaceSlug, event.public_token, account.data?.id),
    queryFn: () => tenantMemberRequest<EventEligibility>(makerspaceSlug,
      `/public/${encodeURIComponent(makerspaceSlug)}/events/${encodeURIComponent(event.public_token)}/eligibility/`),
    enabled: !account.error && Boolean(account.data?.id),
    // Submission rechecks admission on the server; idle cards need no recurring requests.
    retry: false, staleTime: 0, gcTime: 0, refetchOnMount: "always",
    refetchOnWindowFocus: false, refetchOnReconnect: false,
  });
  if (restoring || account.isLoading || eligibility.isLoading) return <p role="status">Checking organization eligibility…</p>;
  const signIn = [account.error, eligibility.error].some(error => error instanceof StructuredApiError && error.status === 401);
  if (signIn) return <div className="mt-3"><p>Sign in to check your membership in a participating organization.</p><MemberAuthPanel makerspaceSlug={makerspaceSlug} onAuthenticated={() => {
    void account.refetch();
    void queryClient.invalidateQueries({ queryKey: ["event-organization-eligibility", makerspaceSlug, event.public_token] });
    void queryClient.invalidateQueries({ queryKey: ["public-event", makerspaceSlug] });
    void queryClient.invalidateQueries({ queryKey: ["public-events", makerspaceSlug] });
  }} /></div>;
  if (account.error || eligibility.error) return <div className="mt-3"><p role="alert">Unable to check organization eligibility.</p><button className="desk-button" type="button" onClick={() => { void account.refetch(); void eligibility.refetch(); }}>Retry</button></div>;
  if (repaired) return <p role="status">Your registration consent has been updated.</p>;
  if (eligibility.data?.consent_repair_required && eligibility.data.host_waiver) return <EventConsentRepairForm
    makerspaceSlug={makerspaceSlug} publicToken={event.public_token} waiver={eligibility.data.host_waiver}
    onRepaired={() => setRepaired(true)} />;
  if (eligibility.data?.reason === "registration_closed" || !event.registration_open) return <p>Registration is closed.</p>;
  if (!eligibility.data?.eligible) return <p className="mt-3 text-sm text-muted">{eligibility.data?.reason === "organization_audience_not_ready" ? "Staff must review this event’s local audience before registration opens." : "Registration requires active membership in a participating organization or one of its owned makerspaces."}</p>;
  return <div className="mt-3">
    <button className="desk-button-secondary" type="button" aria-expanded={open} onClick={() => setOpen(!open)}>{open ? "Close form" : event.registration_requires_approval ? "Apply" : event.availability === "Full" ? "Join waitlist" : "Register"}</button>
    {open ? <EventRegistrationForm makerspaceSlug={makerspaceSlug} publicToken={event.public_token}
      waitlist={event.availability === "Full"} approvalRequired={event.registration_requires_approval}
      customForm={event.custom_form} audience={event.registration_audience} tickets={event.ticket_types}
      ticketRequired={event.ticket_selection_required} promoEnabled={event.promo_codes_enabled}
      currency={event.currency} hostWaiver={eligibility.data.host_waiver} /> : null}
  </div>;
}
