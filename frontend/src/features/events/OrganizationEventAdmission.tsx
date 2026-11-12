import { t } from "@lingui/core/macro";
import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { Callout, ErrorText } from "../../components/ui";
import { getAccessToken, memberRequest, refreshAccessToken, StructuredApiError, tenantMemberRequest } from "../../lib/api";
import { MemberAuthPanel } from "../members/MemberAuthPanel";
import { EventRegistrationForm } from "../inventory/EventRegistrationForm";
import { EventConsentRepairForm } from "./EventConsentRepairForm";
import type { PublicEventDetail } from "./eventTicketTypes";

import type { EventEligibility } from "../../generated/api";
import { LogoLoader } from "../../components/LogoLoader";
export type { EventEligibility } from "../../generated/api";

export const organizationEligibilityKey = (slug: string, token: string, accountId?: number) =>
  ["event-organization-eligibility", slug, token, accountId] as const;

type AdmissionProps = { event: PublicEventDetail; makerspaceSlug: string; organisation?: string };
const note = "text-sm text-muted";

export function OrganizationEventAdmission({ event, makerspaceSlug, organisation }: AdmissionProps) {
  const [checking, setChecking] = useState(false);
  // Event lists mount one admission per card. Only an explicit interaction starts requests.
  return checking ? <OrganizationAdmissionCheck event={event} makerspaceSlug={makerspaceSlug} organisation={organisation} /> :
    <div className="grid gap-3">{!event.registration_open ? <p className={note}>{t`Registration is closed.`}</p> : null}
      <button className={`${event.registration_open ? "desk-button-brand" : "desk-button"} w-full`} type="button" onClick={() => setChecking(true)}>
        {event.registration_open ? t`Check registration eligibility` : t`Review registration consent`}
      </button></div>;
}

function OrganizationAdmissionCheck({ event, makerspaceSlug, organisation }: AdmissionProps) {
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
  if (restoring || account.isLoading || eligibility.isLoading) return <LogoLoader label={t`Checking organization eligibility…`} size={48} className="min-h-16 py-3" />;
  const signIn = [account.error, eligibility.error].some(error => error instanceof StructuredApiError && error.status === 401);
  if (signIn) return <MemberAuthPanel embedded context={<p className={note}>{t`Sign in to check your membership in a participating organization.`}</p>} makerspaceSlug={makerspaceSlug} onAuthenticated={() => {
    void account.refetch();
    void queryClient.invalidateQueries({ queryKey: ["event-organization-eligibility", makerspaceSlug, event.public_token] });
    void queryClient.invalidateQueries({ queryKey: ["public-event", makerspaceSlug] });
    void queryClient.invalidateQueries({ queryKey: ["public-events", makerspaceSlug] });
  }} />;
  if (account.error || eligibility.error) return <ErrorText message={t`Unable to check organization eligibility.`}
    onRetry={() => { void account.refetch(); void eligibility.refetch(); }} />;
  if (repaired) return <div role="status"><Callout size="inline" tone="success" lead="Your registration consent has been updated." /></div>;
  if (eligibility.data?.consent_repair_required && eligibility.data.host_waiver) return <EventConsentRepairForm
    makerspaceSlug={makerspaceSlug} publicToken={event.public_token} waiver={eligibility.data.host_waiver}
    onRepaired={() => setRepaired(true)} />;
  if (eligibility.data?.reason === "registration_closed" || !event.registration_open) return <p className={note}>{t`Registration is closed.`}</p>;
  if (!eligibility.data?.eligible) return <p className={note}>{eligibility.data?.reason === "organization_audience_not_ready" ? t`Staff must review this event’s local audience before registration opens.` : t`Registration requires active membership in a participating organization or one of its owned makerspaces.`}</p>;
  return <div className="grid gap-4">
    <button className={`${open ? "desk-button" : "desk-button-brand"} w-full`} type="button" aria-expanded={open} onClick={() => setOpen(!open)}>{open ? t`Close form` : event.registration_requires_approval ? t`Apply` : event.availability === "Full" ? t`Join waitlist` : t`Register`}</button>
    {open ? <EventRegistrationForm makerspaceSlug={makerspaceSlug} publicToken={event.public_token}
      waitlist={event.availability === "Full"} approvalRequired={event.registration_requires_approval}
      customForm={event.custom_form} audience={event.registration_audience} tickets={event.ticket_types}
      ticketRequired={event.ticket_selection_required} promoEnabled={event.promo_codes_enabled}
      currency={event.currency} hostWaiver={eligibility.data.host_waiver} organisation={organisation} /> : null}
  </div>;
}
