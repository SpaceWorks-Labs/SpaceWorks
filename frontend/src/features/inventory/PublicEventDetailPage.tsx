import { PublicProgrammeEntry } from '../events/programme/PublicProgrammeEntry';
import { PublicVolunteerCards } from '../events/contributions/PublicVolunteerCards';
import { programmeHref } from '../events/programme/routeNames';
import { CenteredCardLayout, PublicLayout, PublicDetailLayout } from "../../components/layouts";
import { publicPageChrome } from "./PublicPageChrome";
import { PublicEventWebsite } from "../events/PublicEventWebsite";
import { PublicWebsiteImage } from "../../components/PublicWebsiteImage";
import { OrganizationEventAdmission } from "../events/OrganizationEventAdmission";
import { useState } from "react";
import { downloadEventCalendar } from "../events/eventCalendar";
import { useMutation, useQuery } from "@tanstack/react-query";
import { surfaceOf } from "../events/publicSurface";
import { useLocation, useParams } from "react-router-dom";
import { StatusPill } from "../../components/ui";
import { useTenantBranding } from "../../lib/useTenantBranding";
import { eventCapacityLabel } from "./PublicEventCard";
import { formatSlug } from "./PublicInventoryParts";
import { publicErrorState } from "./publicErrorState";
import { useTenantBootstrap } from "./usePublicInventory";
import { PageMetadata } from "../../components/PageMetadata";
import { StructuredApiError, tenantPublicRequest } from "../../lib/api";
import { useTenant, useTenantPath } from "../../lib/tenant";
import { EventRegistrationEntry } from "./EventRegistrationEntry";
import { EventPrice } from "../events/EventPrice";
import type { PublicEventDetail } from "../events/eventTicketTypes";
import { useEventVenueSection } from "../bookings/EventVenueBlock";
import { PageShare } from "../publicPages/PageShare";

/** WP2 mounts this component on both central and tenant-domain event routes. */
export function PublicEventDetailPage({ resolvedSlug, resolvedToken, canonicalUrl }: { resolvedSlug?: string; resolvedToken?: string; canonicalUrl?: string } = {}) {
  const { slug, publicToken: routeToken } = useParams();
  const publicToken = resolvedToken ?? routeToken;
  const tenant = useTenant();
  const makerspaceSlug = resolvedSlug ?? (tenant.mode === "single" ? tenant.slug : slug ?? "");
  const tenantPath = useTenantPath(makerspaceSlug);
  const location = useLocation();
  // Central routes load the tenant bootstrap themselves so the header carries the brand and programme nav.
  const bootstrapQuery = useTenantBootstrap(makerspaceSlug, tenant.mode === "central");
  const bootstrap = tenant.mode === "single" ? tenant.bootstrap : bootstrapQuery.data;
  const brandStyle = useTenantBranding(bootstrap);
  const [shareError, setShareError] = useState("");
  const calendar = useMutation({ mutationFn: (item: PublicEventDetail) => downloadEventCalendar(makerspaceSlug, item) });
  const eventQuery = useQuery({
    queryKey: ["public-event", makerspaceSlug, publicToken],
    staleTime: 0, gcTime: 0, refetchOnMount: "always",
    // Keep live programme delays current while the page is open.
    refetchInterval: 30_000, refetchIntervalInBackground: false, refetchOnWindowFocus: true,
    queryFn: () => tenantPublicRequest<PublicEventDetail>(makerspaceSlug, `/public/${encodeURIComponent(makerspaceSlug)}/events/${encodeURIComponent(publicToken ?? "")}/`),
    enabled: Boolean(makerspaceSlug && publicToken),
    retry: (count, error) => !(error instanceof StructuredApiError && error.status < 500) && count < 2,
  });
  const event = eventQuery.error ? undefined : eventQuery.data;
  const venueSection = useEventVenueSection(makerspaceSlug, event?.public_token, (token) => tenantPath(`bookings/${token}`));
  const error = eventQuery.error instanceof StructuredApiError ? eventQuery.error : null;
  const name = bootstrap?.branding.display_name || bootstrap?.makerspace.name || formatSlug(makerspaceSlug) || "Makerspace";
  const state = eventQuery.isLoading ? { status: "loading" as const } : eventQuery.error
    ? publicErrorState(eventQuery.error, { noun: "Events" }, () => { void eventQuery.refetch(); }) : { status: "ready" as const };
  const organizationAudience = event?.registration_audience === "participating_organizations";
  const showCount = event?.show_registration_count !== false && event?.registration_count != null;
  const cutoff = event?.effective_registration_cutoff_at ? `Closed ${new Date(event.effective_registration_cutoff_at).toLocaleString()}.` : "";
  // A closed organization event keeps its admission form: an owned registration may still need its consent renewed.
  // That form says "Registration is closed." itself, so the card note only adds when it closed.
  const closedNote = organizationAudience ? cutoff || undefined : `Registration is closed.${cutoff ? ` ${cutoff}` : ""}`;
  if (error?.status === 404) return <CenteredCardLayout state={{ status: "ready" }} title="Event not found" body="This event is no longer available." primary={{ label: "All events", href: tenantPath("events") }} />;
  return <div style={brandStyle}>
    {event ? <PageMetadata title={event.title} description={event.description.slice(0, 300)} path={canonicalUrl ?? location.pathname} image={event.website && "cover" in event.website ? event.website.cover?.url : event.image_url} imageAlt={event.website?.cover?.alt} noindex={surfaceOf(event).indexable === false} /> : null}
    <PublicLayout {...publicPageChrome(makerspaceSlug, name, tenantPath, bootstrap)} state={state}
      breadcrumb={[{ label: "All events", href: tenantPath("events") }, { label: event?.title ?? "Event" }]}>
      <PublicDetailLayout title={event?.title ?? "Event"} state={state}
        cover={event?.image_url && !(event.website && "cover" in event.website) ? { src: event.image_url, alt: "" } : undefined}
        chips={[...(event?.audience_label ? [{ label: event.audience_label, tone: "info" as const }] : []), ...(event?.category ? [{ label: event.category.name }] : []), ...(event?.tags ?? []).map(label => ({ label }))]}
        facts={event ? [{ identity: { kind: "date", date: event.starts_at }, primary: new Date(event.starts_at).toLocaleString(), secondary: `Until ${new Date(event.ends_at).toLocaleString()}` },
          ...(event.location ? [{ identity: { kind: "icon" as const, icon: "Info" as const, tone: "neutral" as const }, primary: event.location }] : [])] : []}
        sections={event ? [{ id: "about", label: "About", content: <p className="whitespace-pre-wrap leading-7">{event.description}</p> },
          ...(canonicalUrl ? [{ id: "share", label: "Share", content: <PageShare title={event.title} description={event.description} canonicalUrl={canonicalUrl} /> }] : []),
          ...(event.website ? [{ id: "website", label: "Event details", content: <PublicEventWebsite website={event.website}
            links={{ schedule: tenantPath(`events/${event.public_token}/schedule`), speaker: (value: string) => tenantPath(`events/${event.public_token}/speakers/${encodeURIComponent(value)}`), session: (value: string) => tenantPath(`events/${event.public_token}/sessions/${encodeURIComponent(value)}`) }}
            image={(url: string, alt: string) => <PublicWebsiteImage makerspaceSlug={makerspaceSlug} url={url} alt={alt} />} /> }] : []),
          ...(bootstrap?.features.includes('events.volunteering') ? [{ id: 'volunteers', label: 'Volunteers needed', content: <PublicVolunteerCards publicToken={event.public_token} onApply={id => window.location.assign(programmeHref(event.public_token, `roles/${id}`, makerspaceSlug))} /> }] : []),
          ...(bootstrap?.features.includes('events.project_gallery') ? [{ id: 'projects', label: 'Projects and results', content: <div className="flex flex-wrap gap-3"><a className="desk-button" href={tenantPath(`events/${event.public_token}/gallery`)}>Project gallery</a><a className="desk-button" href={tenantPath(`events/${event.public_token}/results`)}>Results</a></div> }] : []), ...venueSection] : []}
        actionCard={{ title: event?.registration_requires_approval ? "Apply to join" : event?.availability === "Full" ? "Join waitlist" : "Join this event",
          state: event?.registration_open || organizationAudience ? "open" : "closed", note: event?.registration_open ? undefined : closedNote,
          summary: event ? <div className="flex flex-wrap items-end gap-6">
            <EventPrice amount={event.payment_amount} currency={event.currency} tickets={event.ticket_types} ticketRequired={event.ticket_selection_required} />
            <dl><dt className="eyebrow">Capacity</dt><dd className="font-semibold tabular-nums text-ink">{eventCapacityLabel(event.capacity)}</dd></dl>
            {showCount ? <dl><dt className="eyebrow">Registered</dt><dd className="font-semibold tabular-nums text-ink">{event.registration_count}</dd></dl> : null}
            <StatusPill label={event.availability} tone={event.availability === "Full" ? "warn" : "success"} />
          </div> : null,
          form: event ? <PublicProgrammeEntry publicToken={event.public_token} slug={makerspaceSlug} features={bootstrap?.features} versionedForm={Boolean(event.custom_form && !Array.isArray(event.custom_form))}>
            {event && organizationAudience ? <OrganizationEventAdmission key={`${makerspaceSlug}:${event.public_token}`} event={event} makerspaceSlug={makerspaceSlug} organisation={name} />
            : event?.registration_open ? <EventRegistrationEntry key={`${makerspaceSlug}:${event.public_token}`} event={event} makerspaceSlug={makerspaceSlug} organisation={name} ordersEnabled={Boolean(bootstrap?.features.includes("events.orders"))} /> : null}</PublicProgrammeEntry> : null,
          secondary: event ? [{ label: "Add to calendar", pending: calendar.isPending, onClick: () => calendar.mutate(event) }, { label: "Share event", onClick: async () => {
            setShareError(""); try { if (navigator.share) await navigator.share({ title: event.title, url: canonicalUrl ?? window.location.href }); else await navigator.clipboard.writeText(canonicalUrl ?? window.location.href); } catch { setShareError("Could not share this event."); }
          } }] : [],
          mobileBar: { summary: event?.title ?? "Event", label: event?.registration_open ? "Register" : "View event" },
          doneContent: <>{calendar.error ? <p role="alert">Could not download this calendar.</p> : null}{shareError ? <p role="alert">{shareError}</p> : null}</> }} />
    </PublicLayout>
    {calendar.error || shareError ? <div role="alert" className="sw-layout p-4 text-danger">{shareError || "Could not download this calendar."}</div> : null}
  </div>;
}
