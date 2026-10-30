import { AppShell } from "../../components/shell";
import { CalendarDays } from "lucide-react";
import { saveCalendarBlob } from "./eventCalendar";
import { useEffect, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useParams } from "react-router-dom";

import { CenteredCardLayout } from "../../components/layouts";
import { ErrorText, Icon, StatusBadge, TicketCard } from "../../components/ui";
import { RouteLink } from "../../components/ui/RouteLink";
import { getAccessToken, memberRequest, memberRequestBlob, refreshAccessToken, StructuredApiError } from "../../lib/api";
import { useTenant, useTenantPath } from "../../lib/tenant";
import { useTenantBootstrap } from "../inventory/usePublicInventory";
import { MemberAuthPanel } from "../members/MemberAuthPanel";
import { googleCalendarUrl, saveTicketBlob, type CalendarFields } from "./eventConfirmation";
import { LiveTicketState } from "./eventPresentation/LiveTicketState";
import { PhotoChoice } from "./eventPresentation/PhotoChoice";

export type MemberEventTicket = Omit<import('../../generated/api').ProgrammeTicket, 'event'> & {
  event: CalendarFields & { id?: number; public_token: string; timezone_name: string; status: string };
  // L1 (G3, X1): the join link only for a confirmed registrant, and the venue map link.
  delivery_mode?: "in_person" | "online" | "hybrid" | null; join_url?: string | null; map_url?: string | null;
};

const confirmed = (status: string) => ["registered", "attended"].includes(status);

export function MemberEventTicketPage() {
  const { slug, registrationId = "" } = useParams();
  const tenant = useTenant();
  const makerspaceSlug = tenant.mode === "single" ? tenant.slug : slug ?? "";
  const tenantPath = useTenantPath(makerspaceSlug);
  const bootstrap = useTenantBootstrap(makerspaceSlug, tenant.mode === "central");
  const makerspaceId = tenant.mode === "single" ? tenant.makerspaceId : bootstrap.data?.makerspace.id;
  const space = tenant.mode === "single" ? tenant.bootstrap : bootstrap.data;
  const spaceName = space?.branding?.display_name || space?.makerspace.name || "Makerspace";
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
    refetchInterval: (query) => !query.state.error && query.state.data && confirmed(query.state.data.status) ? 5000 : false,
    refetchOnWindowFocus: true,
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
  // The sign-in screen is a whole page of its own; nesting it would give this page two h1s.
  if (unauthenticated) return <MemberAuthPanel makerspaceSlug={makerspaceSlug}
    tenantBrand={space ? { name: spaceName, logo: space.branding?.logo_url || space.makerspace.logo_url || undefined } : undefined}
    onAuthenticated={() => { void identity.refetch(); }} />;
  const canDownload = Boolean(current?.ticket_png_available && confirmed(current.status));
  const allEvents = { label: "All events", href: tenantPath("events") };
  return <AppShell variant="member" compactNav="drawer" activeKey="ticket" nav={[{ key: 'events', items: [
    { key: 'events', label: 'Events', href: tenantPath('events'), icon: CalendarDays },
    { key: 'ticket', label: 'Tickets and certificates', href: tenantPath('member/events/history'), icon: CalendarDays },
  ] }]} user={{ name: 'Your account', menu: [{ label: 'Account', href: tenantPath('member/account') }] }}><CenteredCardLayout standalone={false} width={480} eyebrow={spaceName} title="Your event ticket"
    state={restoring || identity.isLoading || ticket.isLoading || bootstrap.isLoading ? { status: "loading" } : { status: "ready" }}
    body={!current ? "This ticket is not available right now."
      : canDownload ? "Download your ticket and bring it to event check-in." : "A ticket download is available once your registration is confirmed."}
    content={<div className="grid gap-4">
      {authError ? <ErrorText message={authError instanceof StructuredApiError && authError.status === 404 ? "Ticket not found." : authError.message} /> : null}
      {bootstrap.error ? <ErrorText message="Unable to load this makerspace." /> : null}
      {current ? <>
        <LiveTicketState status={current.status} attendedAt={current.attended_at} />
        <TicketCard organisation={spaceName} title={current.event.title}
          fields={[
            { label: "When", value: <time dateTime={current.event.starts_at}>{new Date(current.event.starts_at).toLocaleString()}</time> },
            ...(current.event.location || current.map_url ? [{ label: "Where", value: <span className="grid gap-1">
              {current.event.location ? <span>{current.event.location}</span> : null}
              {current.map_url ? <a className="text-brand-ink underline" href={current.map_url} target="_blank" rel="noopener noreferrer">Open the map<span className="sr-only"> (opens in a new tab)</span></a> : null}
            </span> }] : []),
            ...(current.join_url ? [{ label: "Join online", value: <a className="break-all text-brand-ink underline" href={current.join_url} target="_blank" rel="noopener noreferrer">{current.join_url}</a> }] : []),
            { label: "Status", value: <StatusBadge status={current.status} /> },
            { label: "Registration", value: `#${current.registration_id}` },
          ]}
          qr={<div className={`grid h-full place-items-center rounded-xl ${canDownload ? "bg-success-soft text-success-ink" : "bg-warn-soft text-warn-ink"}`}>
            <Icon name={canDownload ? "CheckCircle" : "Clock"} className="h-16 w-16" /></div>}
          caption={canDownload ? "Your check-in code is on the downloadable ticket." : "Your check-in code appears once the makerspace confirms your place."} />
        <div className="flex flex-wrap gap-2">
          {confirmed(current.status) && ["published", "completed"].includes(current.event.status) ? <a className="desk-button flex-1" href={googleCalendarUrl(current.event)} target="_blank" rel="noopener noreferrer">Add to Google Calendar</a> : null}
          <button className="desk-button flex-1" type="button" disabled={calendar.isPending} onClick={() => calendar.mutate()}>Download registration calendar</button>
        </div>
        <RouteLink className="desk-button" href={tenantPath("member/events/history")}>Your event history</RouteLink>
        {current.event.id && makerspaceId ? <PhotoChoice actorId={identity.data?.id} makerspaceId={makerspaceId} eventId={current.event.id} eventName={current.event.title} /> : null}
        {calendar.error ? <ErrorText message="Could not download this calendar." /> : null}
        {download.error ? <ErrorText message={download.error.message} /> : null}
      </> : null}
    </div>}
    primary={canDownload ? { label: "Download ticket PNG", pending: download.isPending, pendingLabel: "Preparing ticket...", onClick: () => download.mutate() } : allEvents}
    escape={canDownload ? allEvents : undefined} /></AppShell>;
}
