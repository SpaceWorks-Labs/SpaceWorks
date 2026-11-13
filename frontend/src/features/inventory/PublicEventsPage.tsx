import { formatLocale } from "../../lib/format";
import { t } from "@lingui/core/macro";
import { PublicLayout } from "../../components/layouts";
import { publicPageChrome } from "./PublicPageChrome";
import { downloadEventCalendar } from "../events/eventCalendar";
import { useTenantBranding } from "../../lib/useTenantBranding";
import { PageMetadata } from "../../components/PageMetadata";
import { DiscoveryControls } from "../discovery/DiscoveryControls";
import { MonthCalendar } from "../discovery/MonthCalendar";
import { monthWindow, useDiscoveryState } from "../discovery/useDiscoveryState";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useLocation, useParams } from "react-router-dom";

import { EmptyState } from "../../components/ui";
import type { ApiPath } from "../../generated/api";
import { StructuredApiError, tenantPublicRequest } from "../../lib/api";
import { useTenant, useTenantPath } from "../../lib/tenant";
import { chargesOn } from "../../lib/charges";
import { PublicEventCard } from "./PublicEventCard";
import { publicErrorState } from "./publicErrorState";
import { formatSlug } from "./PublicInventoryParts";
import { useTenantBootstrap } from "./usePublicInventory";

import type { PublicEventDetail as PublicEvent } from "../events/eventTicketTypes";

const PUBLIC_EVENTS_PATH: ApiPath = "/api/v1/public/{makerspace_slug}/events/";

function publicEventsPath(slug: string) {
  return PUBLIC_EVENTS_PATH.replace("/api/v1", "").replace("{makerspace_slug}", encodeURIComponent(slug));
}

function eventTime(event: PublicEvent, timeZone: string) {
  const options: Intl.DateTimeFormatOptions = { dateStyle: "medium", timeStyle: "short", timeZone };
  return `${new Date(event.starts_at).toLocaleString(formatLocale(), options)} – ${new Date(event.ends_at).toLocaleString(formatLocale(), options)}`;
}

export function PublicEventsPage() {
  const { slug } = useParams();
  const tenant = useTenant();
  const makerspaceSlug = tenant.mode === "single" ? tenant.slug : slug ?? "";
  const tenantPath = useTenantPath(makerspaceSlug);
  const location = useLocation();
  const canonicalPath = location.pathname.replace(/\/$/, "") === tenantPath().replace(/\/$/, "") ? tenantPath() : tenantPath("events");
  const bootstrapQuery = useTenantBootstrap(makerspaceSlug, tenant.mode === "central");
  const bootstrap = tenant.mode === "single" ? tenant.bootstrap : bootstrapQuery.data;
  const brandStyle = useTenantBranding(bootstrap);
  const showPrice = chargesOn(bootstrap, "events");
  const discovery = useDiscoveryState(bootstrap?.makerspace.timezone);
  const [category, setCategory] = useState("");
  const [tag, setTag] = useState("");
  const [calendarToken, setCalendarToken] = useState<string | null>(null);
  const [calendarError, setCalendarError] = useState<{ token: string; message: string } | null>(null);
  const events = useQuery({
    queryKey: ["public-events", makerspaceSlug],
    staleTime: 0, gcTime: 0, refetchOnMount: "always",
    queryFn: () => tenantPublicRequest<PublicEvent[]>(makerspaceSlug, publicEventsPath(makerspaceSlug)),
    retry: (count, error) => !(error instanceof StructuredApiError && error.status < 500) && count < 2,
  });
  const displayName = bootstrap?.branding.display_name || bootstrap?.makerspace.name || formatSlug(makerspaceSlug) || "Makerspace";
  const visibleEvents = (events.error ? [] : events.data ?? []).filter((item) => {
    const text = `${item.title} ${item.description} ${item.location} ${item.series?.title ?? ""}`.toLowerCase();
    if (!text.includes(discovery.query.trim().toLowerCase())) return false;
    if (category && item.category?.slug !== category) return false;
    if (tag && !item.tags?.includes(tag)) return false;
    // #184: with event charges off every event is free, so the "Free events" facet keeps them all.
    if (discovery.facet === "free" && showPrice && item.ticket_selection_required && !item.ticket_types?.length) return false;
    if (discovery.facet === "free" && showPrice && (item.ticket_types?.length ? item.ticket_types.every((ticket) => Number(ticket.amount) !== 0) : Number(item.payment_amount) !== 0)) return false;
    if (discovery.facet === "open" && !item.registration_open) return false;
    if (discovery.month) {
      const { start, end } = monthWindow(discovery.month, discovery.timeZone);
      return new Date(item.starts_at) < end && new Date(item.ends_at) > start;
    }
    return true;
  }).sort((a, b) => Date.parse(a.starts_at) - Date.parse(b.starts_at));
  const groupedEvents = visibleEvents.reduce<Array<{
    key: string; title: string | null; items: PublicEvent[];
  }>>((groups, item) => {
    const key = item.series?.public_token ?? item.public_token;
    const group = groups.find((candidate) => candidate.key === key);
    if (group) group.items.push(item);
    else groups.push({ key, title: item.series?.title ?? null, items: [item] });
    return groups;
  }, []);

  async function downloadCalendar(item: PublicEvent) {
    setCalendarToken(item.public_token);
    setCalendarError(null);
    try {
      await downloadEventCalendar(makerspaceSlug, item);
    } catch (cause) {
      setCalendarError({ token: item.public_token, message: cause instanceof Error ? cause.message : t`Could not download this calendar.` });
    } finally {
      setCalendarToken(null);
    }
  }

  return <div style={brandStyle}>
    <PageMetadata title={t`Events · ${displayName}`} description={t`Upcoming public workshops, meetups and community events at ${displayName}.`} path={canonicalPath} image={bootstrap?.makerspace.cover_image_url || bootstrap?.makerspace.logo_url} siteName={displayName} />
    <PublicLayout {...publicPageChrome(makerspaceSlug, displayName, tenantPath, bootstrap)}
      header={{ title: t`Upcoming events`, subtitle: t`What's on at ${displayName}`, primary: { label: t`My events`, href: tenantPath("member/events") },
        ...(tenant.mode === "central" ? { secondary: { label: t`Discover across makerspaces`, href: "/discover" } } : {}) }}
      state={events.isLoading ? { status: "loading" } : events.error ? publicErrorState(events.error, { surface: "events" }, () => { void events.refetch(); }) : { status: "ready" }}>
      <DiscoveryControls state={discovery} searchLabel="Search events" filters={[...(showPrice ? [{ value: "free", label: t`Free events` }] : []), { value: "open", label: t`Registration open` }]} />
      <div className="mb-5 flex flex-wrap gap-3"><label className="grid min-w-0 flex-1 basis-48 gap-1 text-sm font-semibold sm:max-w-xs">{t`Category`}<select className="desk-input w-full font-normal" value={category} onChange={e => setCategory(e.target.value)}><option value="">{t`All categories`}</option>{[...new Map((events.data ?? []).flatMap(item => item.category ? [[item.category.slug, item.category] as const] : [])).values()].map(row => <option key={row.slug} value={row.slug}>{row.name}</option>)}</select></label>
      <label className="grid min-w-0 flex-1 basis-48 gap-1 text-sm font-semibold sm:max-w-xs">{t`Tag`}<select className="desk-input w-full font-normal" value={tag} onChange={e => setTag(e.target.value)}><option value="">{t`All tags`}</option>{[...new Set((events.data ?? []).flatMap(item => item.tags ?? []))].sort().map(value => <option key={value}>{value}</option>)}</select></label></div>
      <p role="status" className="mb-4 text-sm text-muted">{t`${visibleEvents.length} matching event(s)`}</p>
      {discovery.view === "calendar" && discovery.month ? <MonthCalendar month={discovery.month} timeZone={discovery.timeZone} label={t`Upcoming public events`} entries={visibleEvents.map(item => ({ id: item.public_token, startsAt: item.starts_at, endsAt: item.ends_at, label: item.title, href: `#event-${item.public_token}` }))} /> : null}
      {!visibleEvents.length ? <EmptyState message={events.data?.length ? t`No matching events. Try another search, filter or month.` : t`No upcoming events. Check back soon.`} /> : null}
      <div className="grid gap-7">{groupedEvents.map(group => <section key={group.key} aria-label={group.title ?? undefined}>
        {group.title ? <div className="mb-3"><p className="text-sm text-muted">{t`Recurring series`}</p><h2 className="title-panel">{group.title}</h2>
          {showPrice && group.items[0]?.series?.id && group.items[0].series.passes_enabled ? <a className="mt-2 inline-flex text-sm font-semibold text-brand-ink underline"
            href={tenantPath(`member/series/${group.items[0].series.id}/passes`)}>{t`Buy a series pass`}</a> : null}</div> : null}
        <div className="grid gap-5">{group.items.map(item => <PublicEventCard key={item.public_token} event={item} href={tenantPath(`events/${item.public_token}`)}
          time={eventTime(item, discovery.timeZone)} calendarPending={calendarToken === item.public_token} onCalendar={() => downloadCalendar(item)}
          calendarError={calendarError?.token === item.public_token ? calendarError.message : undefined} showPrice={showPrice} />)}</div>
      </section>)}</div>
    </PublicLayout>
  </div>;
}
