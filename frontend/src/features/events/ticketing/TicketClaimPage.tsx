import { formatDateTime } from "../../../lib/format";
import { t } from "@lingui/core/macro";
import { useEffect, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useParams } from "react-router-dom";

import { CenteredCardLayout } from "../../../components/layouts";
import { ErrorText } from "../../../components/ui";
import { getAccessToken, refreshAccessToken, StructuredApiError } from "../../../lib/api";
import { useTenant, useTenantPath } from "../../../lib/tenant";
import { MemberAuthPanel } from "../../members/MemberAuthPanel";
import { acceptClaim, previewClaim, ticketingKeys } from "./ticketingApi";

const COPY = {
  claim: { title: t`Claim your ticket`, verb: t`Claim my place`, done: t`Your place is confirmed.` },
  transfer: { title: t`Accept a ticket`, verb: t`Accept the ticket`, done: t`The ticket is now yours.` },
};

function errorText(error: unknown) {
  if (!(error instanceof StructuredApiError)) return t`Something went wrong. Try again.`;
  if (error.code === "claim_invalid") return t`This link is not valid any more. Ask the sender for a new one.`;
  if (error.code === "claim_email_mismatch") return t`Sign in with the verified email address this ticket was sent to.`;
  if (error.code === "already_registered") return t`You already have a place at this event.`;
  return error.detail ?? error.message;
}

/** G27/G32: an attendee claims a seat someone bought them, or accepts a transferred ticket.
 * Nobody is registered without signing in: an unauthenticated visitor gets the sign-in panel. */
export function TicketClaimPage({ kind }: { kind: "claim" | "transfer" }) {
  const { token = "", slug } = useParams();
  const tenant = useTenant();
  const makerspaceSlug = tenant.mode === "single" ? tenant.slug : slug ?? "";
  const tenantPath = useTenantPath(makerspaceSlug);
  const [restoring, setRestoring] = useState(!getAccessToken());
  // eslint-disable-next-line react-hooks/exhaustive-deps -- restoring is read only as its mount-time value: one token restore per mount, and re-running after setRestoring(false) would refresh the token again
  useEffect(() => { if (restoring) refreshAccessToken().finally(() => setRestoring(false)); }, []);
  const preview = useQuery({ queryKey: ticketingKeys.claim(kind, token), queryFn: () => previewClaim(kind, token),
    enabled: !restoring && Boolean(token), retry: false });
  const accept = useMutation({ mutationFn: () => acceptClaim(kind, token) });
  const copy = COPY[kind];
  if (preview.error instanceof StructuredApiError && preview.error.status === 401) {
    return <MemberAuthPanel makerspaceSlug={makerspaceSlug} onAuthenticated={() => { void preview.refetch(); }} />;
  }
  const data = preview.data;
  const done = accept.data;
  return <CenteredCardLayout width={480} eyebrow={t`Event ticket`} title={copy.title}
    state={restoring || preview.isLoading ? { status: "loading" } : { status: "ready" }}
    body={done ? copy.done : data ? <>{t`${data.from_name} has a ${data.ticket_type ? `${data.ticket_type} ` : ""}ticket for you to`}<strong className="text-ink"> {data.event_title}</strong> on {formatDateTime(data.starts_at)}.</>
      : t`This ticket link could not be opened.`}
    content={<div className="grid gap-3">
      {preview.error ? <ErrorText message={errorText(preview.error)} /> : null}
      {data && !data.email_matches && !done ? <ErrorText message={t`You are signed in with a different email address than the one this ticket was sent to.`} /> : null}
      {accept.error ? <ErrorText message={errorText(accept.error)} /> : null}
    </div>}
    primary={done ? { label: t`View my ticket`, href: tenantPath(`member/events/${done.registration_id}/ticket`) }
      : { label: accept.isPending ? t`Working…` : copy.verb, onClick: () => accept.mutate(),
        disabled: !data || !data.email_matches || accept.isPending, disabledReason: "Sign in with the address the ticket was sent to." }}
    escape={{ label: t`All events`, href: tenantPath("events") }} />;
}
