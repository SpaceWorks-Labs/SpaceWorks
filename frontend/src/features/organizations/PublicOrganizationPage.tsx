import { useState } from "react";
import { useParams } from "react-router-dom";
import { PublicLayout } from "../../components/layouts";
import { ThemeToggle } from "../../components/ThemeToggle";
import { EmptyState, ErrorBlock, ListRow, Pagination, Skeleton, StatusPill } from "../../components/ui";
import { StructuredApiError } from "../../lib/api";
import { EventPrice } from "../events/EventPrice";
import { usePublicOrganization, usePublicOrganizationEvents, type OrganizationPublicEvent } from "./publicOrganizationsApi";

function dateRange(event: OrganizationPublicEvent) {
  const options: Intl.DateTimeFormatOptions = { dateStyle: "medium", timeStyle: "short" };
  return `${new Date(event.starts_at).toLocaleString(undefined, options)} – ${new Date(event.ends_at).toLocaleString(undefined, options)}`;
}

export function PublicOrganizationPage() {
  const { organizationSlug = "" } = useParams();
  const [page, setPage] = useState(1);
  const organization = usePublicOrganization(organizationSlug);
  const events = usePublicOrganizationEvents(organizationSlug, page);
  const missing = organization.error instanceof StructuredApiError && organization.error.status === 404;

  return <PublicLayout makerspace={{ name: organization.data?.name ?? "Space Works", logo: organization.data?.logo_url || undefined, slug: "", homeHref: "/" }}
    nav={[{ label: "Directory", href: "/" }]} headerAction={{ label: "Sign in", href: "/member" }} liveStatus={<ThemeToggle />}
    header={{ eyebrow: "Organization", title: organization.data?.name ?? "Public organization", subtitle: organization.data?.description || "Upcoming events across community spaces.",
      secondary: organization.data?.website ? { label: "Visit website ↗", href: organization.data.website, external: true } : undefined }}
    state={organization.isLoading ? { status: "loading" } : organization.error ? { status: "error", error: missing ? "This organization doesn't have a public page." : "Couldn't load this organization. Try again.", onRetry: () => { void organization.refetch(); } } : { status: "ready" }}
    footer={{ credit: "Powered by Space Works", links: [{ label: "About", href: "/about" }, { label: "Staff sign-in", href: "/admin" }] }}>
    <section aria-labelledby="organization-events-heading" className="grid gap-4">
      <h2 className="title-panel" id="organization-events-heading">Upcoming events</h2>
      {events.isLoading ? <div aria-label="Loading organization events" className="grid gap-4">{[0, 1, 2].map(item => <Skeleton key={item} className="h-24" />)}</div> : null}
      {events.error ? <ErrorBlock error={new Error("Couldn't load events. Try again.")} onRetry={() => { void events.refetch(); }} /> : null}
      {events.data && !events.data.results.length ? <EmptyState message="No upcoming events. Check back for the next gathering." /> : null}
      {events.data?.results.map(event => <ListRow key={event.public_token} title={event.title} identity={{ kind: "date", date: event.starts_at }}
        meta={<><span>Hosted by {event.host.name} · <time dateTime={event.starts_at}>{dateRange(event)}</time>{event.location ? ` · ${event.location}` : ""}</span>{event.description ? <span className="mt-1 block line-clamp-2">{event.description}</span> : null}</>}
        right={<div className="flex flex-wrap items-center gap-3"><dl className="text-sm"><EventPrice amount={event.payment_amount} currency={event.currency} /></dl>
          <StatusPill label={event.availability} tone={event.availability === "Full" ? "warn" : "success"} />
          <a className="desk-button-brand" href={`/m/${event.host.slug}/events`}>Register at {event.host.name}</a></div>} />)}
      {events.data ? <Pagination page={page} pageSize={24} count={events.data.count} totalPages={Math.ceil(events.data.count / 24)} onChange={setPage} /> : null}
    </section>
  </PublicLayout>;
}
