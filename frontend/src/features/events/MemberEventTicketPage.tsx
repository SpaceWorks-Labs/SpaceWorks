import { saveCalendarBlob } from "./eventCalendar";
import { useEffect, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";

import { SkipLink } from "../../components/SkipLink";
import { StatusBadge } from "../../components/ui";
import { getAccessToken, memberRequest, memberRequestBlob, refreshAccessToken, StructuredApiError } from "../../lib/api";
import { useTenant, useTenantPath } from "../../lib/tenant";
import { useTenantBootstrap } from "../inventory/usePublicInventory";
import { MemberAuthPanel } from "../members/MemberAuthPanel";
import { googleCalendarUrl, saveTicketBlob, type CalendarFields } from "./eventConfirmation";

export type MemberEventTicket = {
  registration_id: number; status: string; ticket_png_available: boolean;
  event: CalendarFields & { public_token: string; timezone_name: string; status: string };
};

export function MemberEventTicketPage() {
  const { slug, registrationId = "" } = useParams();
  const tenant = useTenant();
  const makerspaceSlug = tenant.mode === "single" ? tenant.slug : slug ?? "";
  const tenantPath = useTenantPath(makerspaceSlug);
  const bootstrap = useTenantBootstrap(makerspaceSlug, tenant.mode === "central");
  const makerspaceId = tenant.mode === "single" ? tenant.makerspaceId : bootstrap.data?.makerspace.id;
  const [restoring, setRestoring] = useState(!getAccessToken());
  useEffect(() => { if (restoring) refreshAccessToken().finally(() => setRestoring(false)); }, []);
  const identity = useQuery({
    queryKey: ["member", "ticket-account"], queryFn: () => memberRequest<{ id: number }>("/auth/me"),
    enabled: !restoring, retry: false, staleTime: 0, gcTime: 0, refetchOnMount: "always",
  });
  const base = `/member/makerspaces/${makerspaceId}/event-registrations/${registrationId}`;
  const ticket = useQuery({
    queryKey: ["event-ticket", makerspaceId, identity.data?.id, registrationId],
    queryFn: () => memberRequest<MemberEventTicket>(`${base}/ticket/`),
    enabled: !restoring && !identity.error && Boolean(identity.data?.id && makerspaceId) && /^\d+$/.test(registrationId),
    retry: false, staleTime: 0, gcTime: 0, refetchOnMount: "always",
  });
  const download = useMutation({ mutationFn: async () => {
    const blob = await memberRequestBlob(`${base}/ticket.png`);
    saveTicketBlob(blob, ticket.data?.event.title ?? "event");
  } });
  const calendar = useMutation({ mutationFn: async () => {
    const blob = await memberRequestBlob(`${base}/calendar.ics`);
    saveCalendarBlob(blob, "registration");
  } });
  const authError = identity.error || ticket.error;
  const unauthenticated = authError instanceof StructuredApiError && authError.status === 401;
  const current = authError ? undefined : ticket.data;
  return <main className="desk-shell min-h-screen p-5">
    <SkipLink />
    <section id="main-content" className="desk-panel mx-auto grid max-w-2xl gap-4 p-5" tabIndex={-1}>
      <Link className="desk-button w-fit" to={tenantPath("events")}>All events</Link>
      <h1 className="title-page">Your event ticket</h1>
      {restoring || identity.isLoading || ticket.isLoading || bootstrap.isLoading ? <p role="status">Loading ticket...</p> : null}
      {unauthenticated ? <><p>Sign in with the account that registered for this event.</p><MemberAuthPanel makerspaceSlug={makerspaceSlug} onAuthenticated={() => { void identity.refetch(); }} /></> : null}
      {authError && !unauthenticated ? <p role="alert" className="text-danger">{authError instanceof StructuredApiError && authError.status === 404 ? "Ticket not found." : authError.message}</p> : null}
      {bootstrap.error ? <p role="alert" className="text-danger">Unable to load this makerspace.</p> : null}
      {current ? <>
        <h2 className="title-panel">{current.event.title}</h2><StatusBadge status={current.status} />
        <p><time dateTime={current.event.starts_at}>{new Date(current.event.starts_at).toLocaleString()}</time>{current.event.location ? ` · ${current.event.location}` : ""}</p>
        {current.ticket_png_available && ["registered", "attended"].includes(current.status) ? <button className="desk-button-primary w-fit" type="button" disabled={download.isPending} onClick={() => download.mutate()}>{download.isPending ? "Preparing ticket..." : "Download ticket PNG"}</button> : <p className="text-sm text-muted">A ticket download is available once your registration is confirmed.</p>}
        {["registered", "attended"].includes(current.status) && ["published", "completed"].includes(current.event.status) ? <a className="desk-button w-fit" href={googleCalendarUrl(current.event)} target="_blank" rel="noopener noreferrer">Add to Google Calendar</a> : null}
        <button className="desk-button w-fit" type="button" disabled={calendar.isPending} onClick={() => calendar.mutate()}>Download registration calendar</button>
        {calendar.error ? <p role="alert" className="text-danger">Could not download this calendar.</p> : null}
        {download.error ? <p role="alert" className="text-danger">{download.error.message}</p> : null}
      </> : null}
    </section>
  </main>;
}
